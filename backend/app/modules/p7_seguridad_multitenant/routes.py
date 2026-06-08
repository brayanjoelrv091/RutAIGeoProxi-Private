"""
P7 — Rutas de Administración Multi-Tenant.
"""

from fastapi import APIRouter, Depends, status, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.shared.deps import get_current_user, get_db, require_roles, get_current_superadmin
from app.modules.p1_usuarios.models import Usuario
from app.modules.p7_seguridad_multitenant.schemas import (
    TenantCreate,
    TenantUpdate,
    TenantOut,
    MembershipCreate,
    MembershipOut,
    TenantUpgradeRequest,
    TenantUpgradeConfirmRequest
)
from app.modules.p7_seguridad_multitenant.services import TenantService

router = APIRouter(prefix="/tenants", tags=["P7 · Seguridad Multi-Tenant"])

@router.post("", response_model=TenantOut, status_code=status.HTTP_201_CREATED, summary="Crear un nuevo Tenant")
def create_tenant(
    schema: TenantCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _current: Usuario = Depends(get_current_superadmin),
):
    """CU29 · Administrador global crea una nueva organización."""
    return TenantService.create_tenant(db, schema, background_tasks)


@router.get("", response_model=list[TenantOut], summary="Listar todos los Tenants")
def list_tenants(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _current: Usuario = Depends(get_current_superadmin),
):
    return TenantService.get_tenants(db, skip, limit)


@router.get("/{tenant_id}", response_model=TenantOut, summary="Ver detalle de Tenant")
def get_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    _current: Usuario = Depends(get_current_user),
):
    return TenantService.get_tenant_by_id(db, tenant_id)


@router.patch("/{tenant_id}", response_model=TenantOut, summary="Actualizar Tenant")
def update_tenant(
    tenant_id: int,
    schema: TenantUpdate,
    db: Session = Depends(get_db),
    _current: Usuario = Depends(get_current_superadmin),
):
    return TenantService.update_tenant(db, tenant_id, schema)


@router.post("/me/upgrade", response_model=TenantOut, summary="Mejorar plan de SaaS (Procesa Pago Stripe)")
def upgrade_my_tenant(
    schema: TenantUpgradeRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(admin_dep),
):
    """Realiza un upgrade de plan para la organización actual del admin."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="El usuario no tiene una red de talleres asignada.")
        
    return TenantService.upgrade_tenant(db, current_user.tenant_id, schema.nuevo_plan, schema.metodo_pago)


from fastapi import BackgroundTasks

@router.post("/me/upgrade/confirm", response_model=TenantOut, summary="Confirmar mejora de plan de SaaS y enviar notificación")
def confirm_my_tenant_upgrade(
    schema: TenantUpgradeConfirmRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(admin_dep),
):
    """Efectiviza el upgrade de plan y envía notificaciones tras validar el pago."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="El usuario no tiene una red de talleres asignada.")
        
    tenant = TenantService.confirm_upgrade_tenant(
        db, 
        current_user.tenant_id, 
        current_user.id,
        schema.nuevo_plan, 
        schema.metodo_pago,
        schema.monto
    )
    
    from app.modules.p1_usuarios.services import notify_superadmins_bg
    background_tasks.add_task(notify_superadmins_bg, tenant.nombre, schema.nuevo_plan, schema.monto, schema.metodo_pago, True)
    
    return tenant

from app.modules.p7_seguridad_multitenant.schemas import TenantSuperadminUpgradeRequest

@router.post("/{tenant_id}/superadmin-upgrade", response_model=TenantOut, summary="Upgrade manual por el Superadmin (CU-29)")
def superadmin_upgrade_tenant(
    tenant_id: int,
    schema: TenantSuperadminUpgradeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(admin_dep),
):
    """El Superadmin fuerza el upgrade de un tenant y registra el pago manual."""
    # Validación extra: Solo un superadmin puede hacer esto
    if current_user.tenant_id is not None:
        raise HTTPException(status_code=403, detail="Solo el Superadministrador global puede realizar upgrades manuales.")
        
    return TenantService.superadmin_upgrade_tenant(
        db=db,
        tenant_id=tenant_id,
        superadmin_id=current_user.id,
        nuevo_plan=schema.nuevo_plan,
        metodo_pago=schema.metodo_pago,
        monto=schema.monto_pago,
        background_tasks=background_tasks
    )

@router.post("/{tenant_id}/superadmin-upgrade-confirm", response_model=TenantOut, summary="Confirmar Stripe por Superadmin")
def superadmin_upgrade_tenant_confirm(
    tenant_id: int,
    schema: TenantSuperadminUpgradeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(admin_dep),
):
    if current_user.tenant_id is not None:
        raise HTTPException(status_code=403, detail="Solo el Superadministrador global puede realizar upgrades manuales.")
        
    return TenantService.confirm_upgrade_tenant(
        db=db,
        tenant_id=tenant_id,
        usuario_id=current_user.id,
        nuevo_plan=schema.nuevo_plan,
        metodo_pago=schema.metodo_pago,
        monto=schema.monto_pago
    )

@router.post("/{tenant_id}/members", response_model=MembershipOut, summary="Agregar miembro al Tenant")
def add_member(
    tenant_id: int,
    schema: MembershipCreate,
    db: Session = Depends(get_db),
    _current: Usuario = Depends(admin_dep),
):
    return TenantService.add_member(db, tenant_id, schema)


@router.delete("/{tenant_id}/members/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Quitar miembro del Tenant")
def remove_member(
    tenant_id: int,
    usuario_id: int,
    db: Session = Depends(get_db),
    _current: Usuario = Depends(admin_dep),
):
    TenantService.remove_member(db, tenant_id, usuario_id)


@router.get("/{tenant_id}/members", response_model=list[MembershipOut], summary="Listar miembros del Tenant")
def list_members(
    tenant_id: int,
    db: Session = Depends(get_db),
    _current: Usuario = Depends(admin_dep),
):
    return TenantService.list_members(db, tenant_id)
