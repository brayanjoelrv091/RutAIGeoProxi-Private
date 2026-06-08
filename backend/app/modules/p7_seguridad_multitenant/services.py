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
        # Extraemos campos que no van al modelo Tenant
        schema_dict = schema.model_dump(exclude={"email_admin", "dominio", "estado"})
        email_admin = schema.email_admin
        
        db_tenant = Tenant(**schema_dict)
        try:
            db.add(db_tenant)
            db.commit()
            db.refresh(db_tenant)
            
            # CU-29: Si se envió un correo, crear el usuario administrador automáticamente
            if email_admin:
                # Generar contraseña segura: 8 caracteres (letras, dígitos y un carácter especial)
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
                db.commit()
                db.refresh(new_admin)
                
                # Asignar membresía
                membership = TenantMembership(
                    tenant_id=db_tenant.id,
                    usuario_id=new_admin.id,
                    rol_en_tenant="admin"
                )
                db.add(membership)
                db.commit()
                
                # Para la defensa y pruebas: Imprimir la contraseña en los logs
                print(f"==================================================")
                print(f"TENANT CREADO: {db_tenant.nombre}")
                print(f"USUARIO: {email_admin}")
                print(f"CONTRASEÑA TEMPORAL: {temp_password}")
                print(f"==================================================")
                
                # Enviar correo de credenciales en segundo plano para no bloquear
                if background_tasks:
                    background_tasks.add_task(send_tenant_welcome_email, email_admin, db_tenant.nombre, temp_password)
                else:
                    send_tenant_welcome_email(email_admin, db_tenant.nombre, temp_password)
                
            return db_tenant
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El slug del tenant ya existe",
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
                
                frontend_url = "https://rutaigeoproxi.vercel.app" if not settings.DEBUG_RESET_TOKEN else "http://localhost:4200"
                
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

        # Crear Notificación
        mensaje_pago = "Tarjeta de crédito (Stripe)" if metodo_pago == "tarjeta" else "Transferencia QR"
        fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        mensaje = (
            f"Su plan ha sido cambiado exitosamente. "
            f"Ahora es parte de nuestro plan {nuevo_plan.upper()}. "
            f"Monto pagado: ${monto}. "
            f"Pago realizado por: {mensaje_pago}. "
            f"Fecha y Hora: {fecha_hora}"
        )

        nueva_notif = Notificacion(
            usuario_id=usuario_id,
            titulo="Suscripción Actualizada ✅",
            mensaje=mensaje,
            tipo="info",
            leido=False
        )
        db.add(nueva_notif)
        db.commit()

        # Enviar Notificación Push (Si hay token)
        from app.modules.p1_usuarios.models import Usuario
        usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
        if usuario and usuario.fcm_token:
            send_push_notification(
                token=usuario.fcm_token,
                title="Suscripción Actualizada ✅",
                body=mensaje,
                data={"type": "subscription_update", "plan": nuevo_plan}
            )

        # Enviar Notificación WebSocket
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(manager.send_personal_message(usuario_id, {
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
