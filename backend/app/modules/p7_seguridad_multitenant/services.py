"""
P7 — Servicios de Seguridad y Multi-Tenant.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.modules.p7_seguridad_multitenant.models import Tenant, TenantMembership
from app.modules.p7_seguridad_multitenant.schemas import TenantCreate, TenantUpdate, MembershipCreate
import secrets
import string
from app.shared.security import get_password_hash
from app.modules.p1_usuarios.models import Usuario
from app.shared.email import send_tenant_welcome_email

from fastapi import BackgroundTasks

class TenantService:
    @staticmethod
    def create_tenant(db: Session, schema: TenantCreate, background_tasks: BackgroundTasks = None) -> Tenant:
        import re
        from fastapi import BackgroundTasks
        
        # 1. Validación Estricta de Subdominio (CU-29)
        if schema.dominio:
            if not re.match(r"^[a-z0-9\-]+$", schema.dominio):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El dominio solo puede contener letras minúsculas, números y guiones."
                )
            
            # Verificar si ya existe
            existe = db.query(Tenant).filter(Tenant.dominio == schema.dominio).first()
            if existe:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"El dominio '{schema.dominio}' ya está en uso."
                )

        # Extraemos campos que no van al modelo Tenant
        schema_dict = schema.model_dump(exclude={"email_admin", "dominio", "estado", "metodo_pago", "monto_pago"})
        email_admin = schema.email_admin
        
        # Pagos manuales
        estado_pago = "gratis"
        monto_pago = schema.monto_pago or 0
        metodo_pago = schema.metodo_pago or "ninguno"
        
        if schema.plan != "basico" and schema.plan != "gratis":
            if metodo_pago == "tarjeta":
                estado_pago = "pendiente"
            else:
                estado_pago = "pagado" # Asumimos pago manual presencial
            
        schema_dict["estado_pago"] = estado_pago
        schema_dict["monto_pago"] = monto_pago
        schema_dict["metodo_pago"] = metodo_pago
        schema_dict["dominio"] = schema.dominio
        
        db_tenant = Tenant(**schema_dict)
        try:
            db.add(db_tenant)
            db.flush()  # <--- CU-29: Flusheamos para obtener db_tenant.id, NO commit
            
            # Si es pago por tarjeta (Stripe en línea), generar sesión
            if metodo_pago == "tarjeta" and estado_pago == "pendiente":
                from app.shared.config import settings
                import stripe
                
                stripe.api_key = settings.STRIPE_SECRET_KEY
                frontend_url = "https://rutaigeoproxi-frontend.onrender.com" if not settings.DEBUG_RESET_TOKEN else "http://localhost:4200"
                
                success_url = f"{frontend_url}/tenants?payment_success=true&tenant_id={db_tenant.id}&plan={schema.plan}&monto={monto_pago}"
                cancel_url = f"{frontend_url}/tenants?payment_cancelled=true"
                
                try:
                    session = stripe.checkout.Session.create(
                        line_items=[{
                            'price_data': {
                                'currency': 'usd',
                                'product_data': {'name': f"Suscripción {schema.plan.capitalize()} - {db_tenant.nombre}"},
                                'unit_amount': int(monto_pago * 100),
                            },
                            'quantity': 1,
                        }],
                        mode='payment',
                        success_url=success_url,
                        cancel_url=cancel_url,
                        client_reference_id=str(db_tenant.id)
                    )
                    db_tenant.checkout_url = session.url
                    db.flush()
                except Exception as e:
                    print(f"Error en Stripe: {e}")
                    raise HTTPException(status_code=500, detail="Error de conexión con la pasarela de pago.")
            
            # Crear historial si hubo pago manual presencial
            elif estado_pago == "pagado":
                from datetime import datetime, timezone, timedelta
                db_tenant.fecha_fin_plan = datetime.now(timezone.utc) + timedelta(days=30)
                
                from app.modules.p7_seguridad_multitenant.models import TenantSubscriptionHistory
                nuevo_historial = TenantSubscriptionHistory(
                    tenant_id=db_tenant.id,
                    plan=db_tenant.plan,
                    estado_pago=estado_pago,
                    metodo_pago=metodo_pago,
                    monto_pago=monto_pago
                )
                db.add(nuevo_historial)
                db.flush()
                
                # Notificar a superadmins
                try:
                    from app.modules.p1_usuarios.services import notify_superadmins_bg
                    if background_tasks:
                        background_tasks.add_task(notify_superadmins_bg, db_tenant.nombre, db_tenant.plan, monto_pago, metodo_pago)
                except ImportError:
                    pass
            
            # CU-29: Creación de Usuario Atómica
            if email_admin:
                # Generar contraseña segura: 8 caracteres
                alphabet = string.ascii_letters + string.digits
                temp_password = ''.join(secrets.choice(alphabet) for i in range(8)) + "!"
                
                new_admin = Usuario(
                    nombre=f"Admin {db_tenant.nombre}",
                    email=email_admin,
                    hashed_password=get_password_hash(temp_password),
                    rol="admin",
                    esta_activo=True,
                    tenant_id=db_tenant.id
                )
                db.add(new_admin)
                db.flush()
                
                # Asignar membresía
                membership = TenantMembership(
                    tenant_id=db_tenant.id,
                    usuario_id=new_admin.id,
                    rol_en_tenant="admin"
                )
                db.add(membership)
                db.flush()
                
                print(f"==================================================")
                print(f"TENANT CREADO: {db_tenant.nombre}")
                print(f"USUARIO: {email_admin}")
                print(f"CONTRASEÑA TEMPORAL: {temp_password}")
                print(f"==================================================")
                
                # Forzar BackgroundTasks para correos
                if not background_tasks:
                    # En FastAPI podemos instanciarlo si no lo pasan
                    background_tasks = BackgroundTasks()
                
                background_tasks.add_task(send_tenant_welcome_email, email_admin, db_tenant.nombre, temp_password)
                
            # Todo ha salido bien. Guardamos en disco.
            db.commit()
            db.refresh(db_tenant)
            
            return db_tenant
            
        except HTTPException:
            db.rollback()
            raise
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El dominio o el correo electrónico ya existen en la plataforma."
            )
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ocurrió un error inesperado: {str(e)}"
            )

    @staticmethod
    def get_tenants(db: Session, skip: int = 0, limit: int = 100) -> list[Tenant]:
        return db.query(Tenant).offset(skip).limit(limit).all()

    @staticmethod
    def get_tenant_by_id(db: Session, tenant_id: int) -> Tenant:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant no encontrado",
            )
        return tenant

    @staticmethod
    def update_tenant(db: Session, tenant_id: int, schema: TenantUpdate) -> Tenant:
        tenant = TenantService.get_tenant_by_id(db, tenant_id)
        update_data = schema.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(tenant, key, value)
        try:
            db.commit()
            db.refresh(tenant)
            return tenant
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El slug ya existe o hay un conflicto de datos",
            )

    @staticmethod
    def upgrade_tenant(db: Session, tenant_id: int, nuevo_plan: str, metodo_pago: str = None) -> Tenant:
        tenant = TenantService.get_tenant_by_id(db, tenant_id)
        
        precios = {
            "profesional": 29.00,
            "empresarial": 99.00
        }
        
        from app.shared.config import settings
        setattr(tenant, "checkout_url", None)
        
        if nuevo_plan in precios and metodo_pago != "qr" and settings.STRIPE_SECRET_KEY:
            monto = precios[nuevo_plan]
            try:
                import stripe
                stripe.api_key = settings.STRIPE_SECRET_KEY
                
                price_data = {
                    "currency": "usd",
                    "product_data": {
                        "name": f"Suscripción {nuevo_plan.capitalize()} - {tenant.nombre}",
                    },
                    "unit_amount": int(monto * 100),
                }
                
                frontend_url = "https://rutaigeoproxi-frontend.onrender.com" if not settings.DEBUG_RESET_TOKEN else "http://localhost:4200"
                
                session = stripe.checkout.Session.create(
                    line_items=[{
                        'price_data': price_data,
                        'quantity': 1,
                    }],
                    mode='payment',
                    success_url=f"{frontend_url}/dashboard?payment_success=true",
                    cancel_url=f"{frontend_url}/dashboard?payment_cancelled=true",
                    client_reference_id=str(tenant.id)
                )
                
                tenant.checkout_url = session.url
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Stripe Error in Upgrade: {e}")
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=f"Error al generar sesión de Stripe: {e}"
                )
                
        # NOTA: Ya no actualizamos tenant.plan aquí. Eso sucederá en la confirmación.
        # Solo retornamos el tenant para que devuelva la URL
        db.commit()
        return tenant

    @staticmethod
    def confirm_upgrade_tenant(db: Session, tenant_id: int, usuario_id: int, nuevo_plan: str, metodo_pago: str, monto: float) -> Tenant:
        from app.modules.p5_pagos.models import Notificacion
        from app.shared.firebase_config import send_push_notification
        from app.shared.websocket_manager import manager
        from datetime import datetime
        import asyncio

        tenant = TenantService.get_tenant_by_id(db, tenant_id)
        
        # Validar el plan
        precios = {
            "profesional": 29.00,
            "empresarial": 99.00,
            "gratis": 0.00
        }
        if nuevo_plan not in precios:
            raise HTTPException(status_code=400, detail="Plan no válido")

        # Marcar la fecha_fin de la suscripción anterior
        from app.modules.p7_seguridad_multitenant.models import TenantSubscriptionHistory
        from datetime import datetime, timezone

        historial_anterior = db.query(TenantSubscriptionHistory).filter(
            TenantSubscriptionHistory.tenant_id == tenant_id,
            TenantSubscriptionHistory.fecha_fin.is_(None)
        ).first()

        if historial_anterior:
            historial_anterior.fecha_fin = datetime.now(timezone.utc)
            db.commit()

        tenant.plan = nuevo_plan
        tenant.estado_pago = "pagado" if nuevo_plan != "gratis" else "gratis"
        tenant.metodo_pago = metodo_pago
        tenant.monto_pago = int(monto)
        tenant.checkout_url = None
        
        # Actualizar fecha de expiracion a 30 dias desde hoy si es de pago
        from datetime import timedelta
        if nuevo_plan != "gratis":
            tenant.fecha_fin_plan = datetime.now(timezone.utc) + timedelta(days=30)
        else:
            tenant.fecha_fin_plan = None
            
        db.commit()
        db.refresh(tenant)

        # Crear nueva suscripción en el historial
        nuevo_historial = TenantSubscriptionHistory(
            tenant_id=tenant_id,
            plan=nuevo_plan,
            estado_pago=tenant.estado_pago,
            metodo_pago=metodo_pago,
            monto_pago=int(monto)
        )
        db.add(nuevo_historial)
        db.commit()

        # Crear texto de notificación
        if metodo_pago == "tarjeta":
            mensaje_pago = "Tarjeta de crédito (Stripe / POS)"
        elif metodo_pago == "efectivo":
            mensaje_pago = "Efectivo"
        else:
            mensaje_pago = "Transferencia QR"
            
        fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        mensaje = (
            f"Su plan ha sido cambiado exitosamente. "
            f"Ahora es parte de nuestro plan {nuevo_plan.upper()}. "
            f"Monto pagado: ${monto}. "
            f"Pago realizado por: {mensaje_pago}. "
            f"Fecha y Hora: {fecha_hora}"
        )

        # Obtener a los dueños/admins del tenant para notificarles
        from app.modules.p7_seguridad_multitenant.models import TenantMembership
        dueños = db.query(TenantMembership).filter(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.rol_en_tenant.in_(["owner", "admin"])
        ).all()
        
        from app.modules.p1_usuarios.models import Usuario
        import asyncio
        
        for dueño in dueños:
            nueva_notif = Notificacion(
                usuario_id=dueño.usuario_id,
                titulo="Suscripción Actualizada ✅",
                mensaje=mensaje,
                tipo="info",
                leido=False
            )
            db.add(nueva_notif)
            db.commit()

            usuario = db.query(Usuario).filter(Usuario.id == dueño.usuario_id).first()
            if usuario and usuario.fcm_token:
                send_push_notification(
                    token=usuario.fcm_token,
                    title="Suscripción Actualizada ✅",
                    body=mensaje,
                    data={"type": "subscription_update", "plan": nuevo_plan}
                )

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(manager.send_personal_message(str(dueño.usuario_id), {
                        "type": "notification",
                        "title": "Suscripción Actualizada ✅",
                        "message": mensaje,
                        "plan": nuevo_plan
                    }))
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error sending WS notification: {e}")

        return tenant

    @staticmethod
    def superadmin_upgrade_tenant(db: Session, tenant_id: int, superadmin_id: int, nuevo_plan: str, metodo_pago: str, monto: float, background_tasks: BackgroundTasks = None) -> Tenant:
        if metodo_pago == "tarjeta":
            # Si el pago es online por tarjeta, delegamos a Stripe igual que un upgrade normal
            # pero la URL de éxito debe apuntar a la vista de tenants del Superadmin
            tenant = TenantService.get_tenant_by_id(db, tenant_id)
            from app.shared.config import settings
            import stripe
            
            stripe.api_key = settings.STRIPE_SECRET_KEY
            frontend_url = "https://rutaigeoproxi-frontend.onrender.com" if not settings.DEBUG_RESET_TOKEN else "http://localhost:4200"
            
            # Pasamos los datos por URL para confirmarlo a la vuelta
            success_url = f"{frontend_url}/tenants?payment_success=true&tenant_id={tenant_id}&plan={nuevo_plan}&monto={monto}"
            cancel_url = f"{frontend_url}/tenants?payment_cancelled=true"
            
            session = stripe.checkout.Session.create(
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {'name': f"Suscripción {nuevo_plan.capitalize()} - {tenant.nombre}"},
                        'unit_amount': int(monto * 100),
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
                client_reference_id=str(tenant.id)
            )
            tenant.checkout_url = session.url
            db.commit()
            return tenant
            
        # Si es manual (Efectivo / QR), procesamos inmediatamente
        tenant = TenantService.confirm_upgrade_tenant(db, tenant_id, superadmin_id, nuevo_plan, metodo_pago, monto)
        
        # Luego notificamos al superadmin que cobró
        try:
            from app.modules.p1_usuarios.services import notify_superadmins_bg
            if background_tasks:
                background_tasks.add_task(notify_superadmins_bg, tenant.nombre, nuevo_plan, monto, metodo_pago, True)
        except ImportError:
            pass
            
        return tenant

    @staticmethod
    def add_member(db: Session, tenant_id: int, schema: MembershipCreate) -> TenantMembership:
        # Validar que no exista ya
        existing = db.query(TenantMembership).filter(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.usuario_id == schema.usuario_id
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El usuario ya es miembro de este tenant",
            )
            
        membership = TenantMembership(
            tenant_id=tenant_id,
            usuario_id=schema.usuario_id,
            rol_en_tenant=schema.rol_en_tenant
        )
        try:
            db.add(membership)
            db.commit()
            db.refresh(membership)
            
            # Asignar el tenant_id actual al usuario
            from app.modules.p1_usuarios.models import Usuario
            usuario = db.query(Usuario).filter(Usuario.id == schema.usuario_id).first()
            if usuario:
                usuario.tenant_id = tenant_id
                db.commit()
                
            return membership
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error al agregar miembro. ¿Usuario existe?",
            )

    @staticmethod
    def remove_member(db: Session, tenant_id: int, usuario_id: int):
        membership = db.query(TenantMembership).filter(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.usuario_id == usuario_id
        ).first()
        
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Miembro no encontrado",
            )
            
        db.delete(membership)
        
        # Remover tenant_id del usuario si lo tenía
        from app.modules.p1_usuarios.models import Usuario
        usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
        if usuario and usuario.tenant_id == tenant_id:
            usuario.tenant_id = None
            
        db.commit()

    @staticmethod
    def list_members(db: Session, tenant_id: int) -> list[TenantMembership]:
        return db.query(TenantMembership).filter(TenantMembership.tenant_id == tenant_id).all()


class TenantFilterService:
    """Lógica para aplicar row-level security / filtros automáticos."""
    
    @staticmethod
    def apply_tenant_filter(query, model, tenant_id: int | None):
        """Filtra una query de SQLAlchemy para retornar solo registros del tenant_id especificado."""
        if tenant_id is None:
            # Si no hay tenant_id, podríamos restringir a 0 resultados o dejar que un superadmin vea todo.
            # Por seguridad, si tenant_id es None (usuario no asignado a org), no debería ver datos de otras orgs.
            # Vamos a retornar los que tienen tenant_id IS NULL.
            return query.filter(model.tenant_id.is_(None))
        
        return query.filter(model.tenant_id == tenant_id)
