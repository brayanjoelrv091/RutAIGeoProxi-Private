"""
P1 — Capa de servicios (lógica de negocio) de Usuarios y Seguridad.

Separa la lógica de negocio de los endpoints para mantener
los routes delgados y la lógica testeable.
"""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.shared.config import settings
from app.shared.security import (
    create_access_token,
    generate_reset_token,
    get_password_hash,
    hash_reset_token,
    verify_password,
)
from app.shared.email import send_reset_email
from app.modules.p1_usuarios.models import (
    TokenRecuperacion,
    TokenRevocado,
    Usuario,
    Vehiculo,
)
from app.modules.p1_usuarios.schemas import (
    AdminUserCreate,
    ChangePasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    PermissionsUpdate,
    ResetPasswordRequest,
    RoleUpdate,
    TokenResponse,
    UserCreate,
    UserProfileUpdate,
    VehicleCreate,
    VehicleUpdate,
)


# ═══════════════════════════════════════════════════════════════════════
# AUTH SERVICE  (CU1, CU2, CU3, CU4)
# ═══════════════════════════════════════════════════════════════════════


async def notify_superadmins_bg(tenant_name: str, plan: str, monto: float, metodo: str, is_upgrade: bool = False):
    from app.shared.database import SessionLocal
    from app.modules.p1_usuarios.models import Usuario
    from app.shared.websocket_manager import manager
    from app.modules.p5_pagos.models import Notificacion
    from datetime import datetime
    db = SessionLocal()
    try:
        superadmins = db.query(Usuario).filter(Usuario.rol == "admin", Usuario.tenant_id.is_(None)).all()
        fecha_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if is_upgrade:
            titulo = "Suscripción Actualizada SaaS"
            message = f"La empresa {tenant_name} ha cambiado su plan a {plan.upper()} por ${monto} con fecha {fecha_str}. Pagado con {metodo}."
        else:
            titulo = "Nuevo Registro SaaS"
            message = f"Un nuevo cliente se ha registrado con el nombre de la web: {tenant_name}. Se suscribió al plan {plan.upper()} de ${monto} con fecha {fecha_str}. Validó su pago con {metodo}."

        payload = {
            "type": "notification",
            "titulo": titulo,
            "mensaje": message,
        }
        for admin in superadmins:
            await manager.send_personal_message(payload, str(admin.id))
            db.add(Notificacion(usuario_id=admin.id, titulo=titulo, mensaje=message, tipo="info"))
            if admin.fcm_token:
                from app.shared.firebase_config import send_push_notification
                send_push_notification(admin.fcm_token, titulo, message, data={"type": "notification"})
        db.commit()
    finally:
        db.close()

class AuthService:
    """Servicio de autenticación y registro."""

    @staticmethod
    def register(db: Session, payload: UserCreate, background_tasks: 'BackgroundTasks' = None) -> Usuario:
        """CU3 — Registrar usuario (público, rol=cliente, taller o admin)."""
        if db.query(Usuario).filter(Usuario.email == payload.email).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El correo ya está registrado",
            )
        user = Usuario(
            nombre=payload.nombre,
            email=payload.email,
            hashed_password=get_password_hash(payload.password),
            rol=payload.rol,
            esta_activo=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # SaaS: Crear Tenant si el rol es 'admin'
        if payload.rol == "admin" and payload.tenant_name and payload.plan:
            from app.modules.p7_seguridad_multitenant.models import Tenant, TenantMembership
            import re
            
            slug = re.sub(r'[^a-z0-9]+', '-', payload.tenant_name.lower()).strip('-')
            base_slug = slug
            counter = 1
            while db.query(Tenant).filter(Tenant.slug == slug).first():
                slug = f"{base_slug}-{counter}"
                counter += 1

            estado_pago = "gratis"
            monto_pago = 0
            metodo_pago = payload.metodo_pago or "ninguno"
            if payload.plan == "gratis":
                fecha_fin = datetime.utcnow() + timedelta(days=30)
            elif payload.plan == "profesional":
                estado_pago = "pendiente" if payload.metodo_pago == "tarjeta" else "pagado"
                monto_pago = 29
                fecha_fin = datetime.utcnow() + timedelta(days=30)
                if not payload.metodo_pago:
                    metodo_pago = "tarjeta"
            elif payload.plan == "empresarial":
                estado_pago = "pendiente" if payload.metodo_pago == "tarjeta" else "pagado"
                monto_pago = 99
                fecha_fin = datetime.utcnow() + timedelta(days=365)
                if not payload.metodo_pago:
                    metodo_pago = "tarjeta"
            else:
                fecha_fin = None

            tenant = Tenant(
                nombre=payload.tenant_name,
                slug=slug,
                esta_activo=True,
                plan=payload.plan,
                estado_pago=estado_pago,
                monto_pago=monto_pago,
                fecha_fin_plan=fecha_fin,
                metodo_pago=metodo_pago
            )
            db.add(tenant)
            db.commit()
            db.refresh(tenant)

            from app.modules.p7_seguridad_multitenant.models import TenantSubscriptionHistory
            nuevo_historial = TenantSubscriptionHistory(
                tenant_id=tenant.id,
                plan=payload.plan,
                estado_pago=estado_pago,
                metodo_pago=metodo_pago,
                monto_pago=monto_pago
            )
            db.add(nuevo_historial)
            db.commit()

            membership = TenantMembership(
                usuario_id=user.id,
                tenant_id=tenant.id,
                rol_en_tenant="owner"
            )
            db.add(membership)
            
            user.tenant_id = tenant.id
            db.commit()

            if background_tasks and estado_pago == "pagado":
                background_tasks.add_task(notify_superadmins_bg, tenant.nombre, payload.plan, monto_pago, metodo_pago)

            # --- STRIPE CHECKOUT ---
            setattr(user, "checkout_url", None)
            if payload.plan != "gratis" and payload.metodo_pago != "qr" and settings.STRIPE_SECRET_KEY:
                try:
                    import stripe
                    stripe.api_key = settings.STRIPE_SECRET_KEY
                    
                    price_data = {
                        "currency": "usd",
                        "product_data": {
                            "name": f"Suscripción {payload.plan.capitalize()} - {payload.tenant_name}",
                        },
                        "unit_amount": monto_pago * 100, # En centavos
                    }
                    
                    # URLs de exito y cancelación apuntan al frontend local o cloud
                    frontend_url = "https://rutaigeoproxi-frontend.onrender.com" if not settings.DEBUG_RESET_TOKEN else "http://localhost:4200"
                    
                    session = stripe.checkout.Session.create(
                        line_items=[{
                            'price_data': price_data,
                            'quantity': 1,
                        }],
                        mode='payment',
                        success_url=f"{frontend_url}/register?payment_success=true&email={payload.email}&plan={payload.plan}&metodo_pago=tarjeta",
                        cancel_url=f"{frontend_url}/register?payment_cancelled=true",
                        client_reference_id=str(tenant.id)
                    )
                    setattr(user, "checkout_url", session.url)
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"Stripe Error: {e}")
                    pass # Falla silenciosamente y permite al usuario registrarse gratis

        return user

    @staticmethod
    def confirm_register_payment(db: Session, email: str, background_tasks: 'BackgroundTasks' = None):
        """Confirma el pago de registro de un usuario"""
        user = db.query(Usuario).filter(Usuario.email == email).first()
        if not user or not user.tenant_id:
            raise HTTPException(status_code=404, detail="Usuario o Tenant no encontrado.")
            
        from app.modules.p7_seguridad_multitenant.models import Tenant
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant no encontrado.")

        if tenant.estado_pago != "pagado":
            tenant.estado_pago = "pagado"
            
            from app.modules.p7_seguridad_multitenant.models import TenantSubscriptionHistory
            historial = db.query(TenantSubscriptionHistory).filter(TenantSubscriptionHistory.tenant_id == tenant.id).order_by(TenantSubscriptionHistory.id.desc()).first()
            if historial:
                historial.estado_pago = "pagado"

            db.commit()
            if background_tasks:
                background_tasks.add_task(notify_superadmins_bg, tenant.nombre, tenant.plan, tenant.monto_pago, tenant.metodo_pago)
        return {"status": "ok"}

    @staticmethod
    def login(db: Session, payload: LoginRequest) -> tuple[TokenResponse, Usuario]:
        """CU1 — Inicio de sesión con JWT y Rate Limiting."""
        user = db.query(Usuario).filter(Usuario.email == payload.email).first()
        now = datetime.now(timezone.utc)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas",
            )

        if not user.esta_activo:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cuenta desactivada permanentemente. Por favor, contacta a soporte@rutaigeoproxi.com",
            )
            
        # Bloqueo SaaS: Si el Tenant está suspendido
        if user.tenant_id:
            from app.modules.p7_seguridad_multitenant.models import Tenant
            tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
            if tenant and not tenant.esta_activo:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Tu cuenta de empresa (SaaS) ha sido suspendida. Por favor, regulariza el pago.",
                )

        if user.bloqueado_hasta:
            bh = user.bloqueado_hasta.replace(tzinfo=timezone.utc) if user.bloqueado_hasta.tzinfo is None else user.bloqueado_hasta
            if bh > now:
                mins_left = int((bh - now).total_seconds() / 60)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Demasiados intentos. Tu cuenta ha sido bloqueada temporalmente por {mins_left or 1} minutos por seguridad.",
                )

        if not verify_password(payload.password, user.hashed_password):
            user.intentos_fallidos += 1
            if user.intentos_fallidos == 3:
                user.bloqueado_hasta = now + timedelta(minutes=5)
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Demasiados intentos fallidos (3). Tu cuenta ha sido bloqueada temporalmente por 5 minutos por seguridad.",
                )
            elif user.intentos_fallidos == 4:
                user.bloqueado_hasta = now + timedelta(minutes=7)
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Demasiados intentos fallidos (4). Cuenta bloqueada temporalmente por 7 minutos.",
                )
            elif user.intentos_fallidos >= 5:
                user.esta_activo = False
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Límite máximo de intentos excedido (5). Tu cuenta ha sido bloqueada permanentemente. Por favor, contacta al administrador para desbloquearla.",
                )
            else:
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Contraseña incorrecta. Recuerda respetar las mayúsculas y minúsculas.",
                )

        # Exito: reset intentos
        user.intentos_fallidos = 0
        user.bloqueado_hasta = None
        
        # Auto-reparación SaaS: Si es dueño de un tenant pero su tenant_id es None (bug antiguo)
        if user.rol == "admin" and user.tenant_id is None:
            from app.modules.p7_seguridad_multitenant.models import TenantMembership
            membership = db.query(TenantMembership).filter(
                TenantMembership.usuario_id == user.id, 
                TenantMembership.rol_en_tenant == "owner"
            ).first()
            if membership:
                user.tenant_id = membership.tenant_id

        db.commit()

        token, _jti, expire = create_access_token(user_id=user.id, role=user.rol)
        expires_in = max(0, int((expire - now).total_seconds()))
        return TokenResponse(access_token=token, expires_in=expires_in), user

    @staticmethod
    def logout(db: Session, _token: str, payload: dict) -> None:
        """CU2 — Cierre de sesión (revoca JWT)."""
        jti = payload.get("jti")
        exp_ts = payload.get("exp")
        if not jti or exp_ts is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido",
            )
        if db.query(TokenRevocado).filter(TokenRevocado.jti == jti).first():
            return
        expires_at = datetime.fromtimestamp(int(exp_ts), tz=timezone.utc)
        db.add(
            TokenRevocado(
                jti=jti,
                expira_en=expires_at,
                revocado_en=datetime.now(timezone.utc),
            )
        )
        db.commit()

    @staticmethod
    def forgot_password(db: Session, email: str) -> ForgotPasswordResponse:
        """CU4a — Solicitar token de recuperación y enviar email vía Brevo."""
        msg = "Si el correo existe en el sistema, recibirás instrucciones para restablecer la contraseña."
        user = db.query(Usuario).filter(Usuario.email == email).first()
        if not user:
            return ForgotPasswordResponse(message=msg, debug_token=None)

        raw = generate_reset_token()
        th = hash_reset_token(raw)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        db.add(
            TokenRecuperacion(
                usuario_id=user.id,
                token_hash=th,
                expira_en=expires_at,
            )
        )
        db.commit()

        # Enviar email
        try:
            send_reset_email(to_email=user.email, token=raw)
        except Exception as e:  # pylint: disable=broad-except
            print("Error email: ", e)

        debug = raw if settings.DEBUG_RESET_TOKEN else None
        return ForgotPasswordResponse(message=msg, debug_token=debug)

    @staticmethod
    def reset_password(db: Session, payload: ResetPasswordRequest) -> None:
        """CU4b — Restablecer contraseña con token válido."""
        th = hash_reset_token(payload.token)
        now = datetime.now(timezone.utc)
        row = (
            db.query(TokenRecuperacion)
            .filter(
                TokenRecuperacion.token_hash == th,
                TokenRecuperacion.usado_en.is_(None),
                TokenRecuperacion.expira_en > now,
            )
            .first()
        )
        if not row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token inválido o expirado",
            )
        user = db.query(Usuario).filter(Usuario.id == row.usuario_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token inválido",
            )
        user.hashed_password = get_password_hash(payload.new_password)
        row.usado_en = now
        db.commit()


# ═══════════════════════════════════════════════════════════════════════
# USER SERVICE  (CU5, CU6)
# ═══════════════════════════════════════════════════════════════════════


class UserService:
    """Servicio de gestión de usuarios (perfil y admin)."""

    @staticmethod
    def get_me(db: Session, user_id: int) -> Usuario:
        """CU6 — Obtener perfil con vehículos."""
        user = (
            db.query(Usuario)
            .options(joinedload(Usuario.vehiculos))
            .filter(Usuario.id == user_id)
            .first()
        )
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )
        
        setattr(user, "tenant_plan", None)
        if user.tenant_id:
            from app.modules.p7_seguridad_multitenant.models import Tenant
            tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
            if tenant:
                setattr(user, "tenant_plan", tenant.plan)

        return user

    @staticmethod
    def update_profile(
        db: Session, user_id: int, payload: UserProfileUpdate
    ) -> Usuario:
        """CU6 — Actualizar nombre/teléfono del perfil."""
        user = (
            db.query(Usuario)
            .options(joinedload(Usuario.vehiculos))
            .filter(Usuario.id == user_id)
            .first()
        )
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )
        data = payload.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(user, k, v)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def list_all(db: Session, tenant_id: int | None = None) -> list[Usuario]:
        """CU5 — Listar todos los usuarios (admin), filtrado por tenant si aplica."""
        from app.modules.p7_seguridad_multitenant.services import TenantFilterService
        query = db.query(Usuario)
        if tenant_id is not None:
            query = TenantFilterService.apply_tenant_filter(query, Usuario, tenant_id)
        return query.order_by(Usuario.id).all()

    @staticmethod
    def admin_create(db: Session, payload: AdminUserCreate) -> Usuario:
        """CU5 — Crear usuario con rol específico (admin)."""
        if db.query(Usuario).filter(Usuario.email == payload.email).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El correo ya está registrado",
            )
        user = Usuario(
            nombre=payload.nombre,
            email=payload.email,
            hashed_password=get_password_hash(payload.password),
            rol=payload.rol,
            esta_activo=True,
            permisos=payload.permisos,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update_role(
        db: Session, user_id: int, payload: RoleUpdate, admin_id: int
    ) -> Usuario:
        """CU5 — Cambiar rol de un usuario (admin)."""
        user = db.query(Usuario).filter(Usuario.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )
        if user.id == admin_id and payload.rol != "admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No puedes quitarte el rol de administrador a ti mismo",
            )
        user.rol = payload.rol
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update_permissions(
        db: Session, user_id: int, payload: PermissionsUpdate
    ) -> Usuario:
        """CU5 — Actualizar permisos de un usuario (admin)."""
        user = db.query(Usuario).filter(Usuario.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )
        user.permisos = payload.permisos
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def change_password(
        db: Session, user_id: int, payload: ChangePasswordRequest
    ) -> dict:
        """Cambio de contraseña interno desde el perfil."""
        user = db.query(Usuario).filter(Usuario.id == user_id).first()
        if not user or not verify_password(
            payload.current_password, user.hashed_password
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La contraseña actual es incorrecta",
            )

        user.hashed_password = get_password_hash(payload.new_password)
        db.commit()
        return {"message": "Contraseña actualizada exitosamente"}


# ═══════════════════════════════════════════════════════════════════════
# VEHICLE SERVICE  (CU6)
# ═══════════════════════════════════════════════════════════════════════


class VehicleService:
    """Servicio de gestión de vehículos del cliente."""

    @staticmethod
    def list_by_user(db: Session, user_id: int) -> list[Vehiculo]:
        return (
            db.query(Vehiculo)
            .filter(Vehiculo.usuario_id == user_id)
            .order_by(Vehiculo.id)
            .all()
        )

    @staticmethod
    def create(db: Session, user_id: int, payload: VehicleCreate) -> Vehiculo:
        v = Vehiculo(
            usuario_id=user_id,
            marca=payload.marca,
            modelo=payload.modelo,
            placa=payload.placa.strip().upper(),
            anio=payload.anio,
            color=payload.color,
        )
        db.add(v)
        db.commit()
        db.refresh(v)
        return v

    @staticmethod
    def update(
        db: Session, vehicle_id: int, user_id: int, payload: VehicleUpdate
    ) -> Vehiculo:
        v = (
            db.query(Vehiculo)
            .filter(Vehiculo.id == vehicle_id, Vehiculo.usuario_id == user_id)
            .first()
        )
        if not v:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vehículo no encontrado",
            )
        data = payload.model_dump(exclude_unset=True)
        if "placa" in data and data["placa"] is not None:
            data["placa"] = data["placa"].strip().upper()
        for k, val in data.items():
            setattr(v, k, val)
        db.commit()
        db.refresh(v)
        return v

    @staticmethod
    def delete(db: Session, vehicle_id: int, user_id: int) -> None:
        v = (
            db.query(Vehiculo)
            .filter(Vehiculo.id == vehicle_id, Vehiculo.usuario_id == user_id)
            .first()
        )
        if not v:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vehículo no encontrado",
            )
        db.delete(v)
        db.commit()
