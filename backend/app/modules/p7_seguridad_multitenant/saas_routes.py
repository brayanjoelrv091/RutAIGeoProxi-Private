from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from datetime import datetime

from app.shared.deps import get_db, require_roles
from app.modules.p1_usuarios.models import Usuario
from app.modules.p7_seguridad_multitenant.models import Tenant

router = APIRouter(tags=["P7 · Gestión SaaS (SuperAdmin)"])

class TenantStatusUpdate(BaseModel):
    esta_activo: bool

from app.modules.p7_seguridad_multitenant.schemas import TenantSubscriptionHistoryOut

class TenantOut(BaseModel):
    id: int
    nombre: str
    slug: str
    esta_activo: bool
    plan: str
    creado_en: datetime
    fecha_fin_plan: datetime | None = None
    estado_pago: str = "gratis"
    metodo_pago: str = "ninguno"
    monto_pago: int = 0
    admin_nombre: str | None = None
    admin_email: str | None = None
    historial_suscripciones: List[TenantSubscriptionHistoryOut] = []
    
    class Config:
        from_attributes = True

def require_superadmin(current: Usuario = Depends(require_roles("admin"))):
    """Verifica que sea un admin GLOBAL (sin tenant)."""
    if current.tenant_id is not None:
        raise HTTPException(status_code=403, detail="Acceso denegado. Se requieren privilegios de SuperAdmin del sistema.")
    return current

from fastapi import BackgroundTasks

async def notify_tenant_users_bg(tenant_id: int, is_suspended: bool, tenant_name: str):
    from app.shared.database import SessionLocal
    from app.modules.p1_usuarios.models import Usuario
    from app.modules.p5_pagos.models import Notificacion
    from app.shared.websocket_manager import manager
    from app.shared.firebase_config import send_push_notification
    db = SessionLocal()
    try:
        users = db.query(Usuario).filter(Usuario.tenant_id == tenant_id).all()
        
        if is_suspended:
            titulo = f"Cuenta Suspendida - {tenant_name}"
            mensaje = f"Su cuenta ha sido inactivada debido al vencimiento o falta de pago. De parte del equipo de RutAIGeoProxi."
            payload_type = "tenant_suspended"
        else:
            titulo = f"¡Bienvenido de Nuevo! - {tenant_name}"
            mensaje = "Su cuenta ha sido reactivada. Gracias por confiar en RutAIGeoProxi."
            payload_type = "tenant_reactivated"
            
        payload = {
            "type": payload_type,
            "titulo": titulo,
            "mensaje": mensaje,
        }
        
        for u in users:
            # Insert into database to persist for the dropdown
            db.add(Notificacion(
                usuario_id=u.id,
                titulo=titulo,
                mensaje=mensaje,
                tipo="push"
            ))
            
            # WebSocket Notification
            await manager.send_personal_message(payload, str(u.id))
            # FCM Push Notification
            if u.fcm_token:
                send_push_notification(u.fcm_token, titulo, mensaje)
                
        db.commit()
    finally:
        db.close()

@router.get("/tenants", response_model=List[TenantOut], summary="Listar todos los tenants (Solo SuperAdmin)")
def list_all_tenants(
    db: Session = Depends(get_db),
    _current: Usuario = Depends(require_superadmin)
):
    """Obtiene la lista de todas las suscripciones (empresas) registradas en el sistema."""
    from app.modules.p7_seguridad_multitenant.models import TenantMembership
    from sqlalchemy.orm import joinedload
    tenants = db.query(Tenant).options(joinedload(Tenant.historial_suscripciones)).order_by(Tenant.creado_en.desc()).all()
    for t in tenants:
        membership = db.query(TenantMembership).filter(TenantMembership.tenant_id == t.id, TenantMembership.rol_en_tenant == "owner").first()
        if membership:
            owner = db.query(Usuario).filter(Usuario.id == membership.usuario_id).first()
            setattr(t, "admin_nombre", owner.nombre if owner else "Desconocido")
            setattr(t, "admin_email", owner.email if owner else "Desconocido")
        else:
            setattr(t, "admin_nombre", "Desconocido")
            setattr(t, "admin_email", "Desconocido")
    return tenants

@router.patch("/tenants/{tenant_id}/status", response_model=TenantOut, summary="Activar o suspender un tenant (Solo SuperAdmin)")
def update_tenant_status(
    tenant_id: int,
    payload: TenantStatusUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _current: Usuario = Depends(require_superadmin)
):
    """Permite al SuperAdmin suspender o reactivar una empresa por falta de pago o incumplimiento."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    
    was_active = tenant.esta_activo
    tenant.esta_activo = payload.esta_activo
    db.commit()
    db.refresh(tenant)
    
    # Notify all users if status changed
    if was_active != payload.esta_activo:
        is_suspended = not payload.esta_activo
        background_tasks.add_task(notify_tenant_users_bg, tenant_id, is_suspended, tenant.nombre)
        
    return tenant
