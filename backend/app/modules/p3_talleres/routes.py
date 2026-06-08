"""
P3 — Rutas de Gestión de Talleres (CU10-CU13).

Endpoints:
    POST   /workshops                      → CU10 Registrar taller
    GET    /workshops                      → Listar mis talleres
    GET    /workshops/all                  → Listar activos (público)
    GET    /workshops/{id}                 → Detalle taller
    POST   /workshops/{id}/technicians     → CU10 Agregar técnico
    GET    /workshops/{id}/technicians     → Listar técnicos
    PATCH  /technicians/{id}/availability  → Toggle disponibilidad
    GET    /workshops/{id}/requests        → CU11 Solicitudes pendientes
    PATCH  /requests/{id}/status           → CU12 Actualizar estado
    GET    /workshops/{id}/history         → CU13 Historial
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.shared.deps import get_current_user, get_db, require_roles, require_operational_roles
from app.modules.p1_usuarios.models import Usuario
from app.modules.p3_talleres.schemas import (
    ServiceHistoryOut,
    ServiceRequestOut,
    ServiceStatusUpdate,
    TechnicianAvailabilityUpdate,
    TechnicianCreate,
    TechnicianOut,
    WorkshopCreate,
    WorkshopOut,
    WorkshopProfileOut,
    TallerCercanoOut,
)
from app.modules.p3_talleres.services import WorkshopService

router = APIRouter(prefix="/workshops", tags=["P3 · Talleres"])

# ═══════════════════════════════════════════════════════════════════════
# CU10 — Registrar taller y técnicos
# ═══════════════════════════════════════════════════════════════════════

@router.get(
    "/cercanos",
    response_model=list[TallerCercanoOut],
    summary="CU31 · Buscar talleres cercanos (Geoespacial)",
)
def buscar_talleres_cercanos(
    lat: float,
    lng: float,
    radio_km: float = 50.0,
    db: Session = Depends(get_db),
    _current: Usuario = Depends(get_current_user),
):
    """Busca talleres cercanos usando la fórmula de Haversine."""
    return WorkshopService.buscar_talleres_cercanos(db, lat, lng, radio_km)

@router.post(
    "",
    response_model=WorkshopOut,
    status_code=status.HTTP_201_CREATED,
    summary="CU10 · Registrar taller",
)
def register_workshop(
    payload: WorkshopCreate,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_operational_roles("taller", "admin")),
):
    return WorkshopService.register(db, current.id, payload)


@router.get(
    "",
    response_model=list[WorkshopOut],
    summary="Listar mis talleres",
)
def list_my_workshops(
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_operational_roles("taller", "admin")),
):
    return WorkshopService.list_by_owner(db, current.id)

@router.get(
    "/me/profile",
    response_model=WorkshopProfileOut,
    summary="Obtener perfil completo del taller del usuario",
)
def get_my_workshop_profile(
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_operational_roles("taller", "admin")),
):
    return WorkshopService.get_profile(db, current.id)

@router.post(
    "/me/complete",
    response_model=WorkshopOut,
    summary="Marcar registro del taller como completado",
)
def complete_workshop_registration(
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_operational_roles("taller", "admin")),
):
    return WorkshopService.complete_registration(db, current.id)

@router.post(
    "/heartbeat",
    status_code=status.HTTP_200_OK,
    summary="Actualizar estado online del taller",
)
def update_heartbeat(
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_operational_roles("taller", "admin")),
):
    success = WorkshopService.record_heartbeat(db, current.id)
    if not success:
        return {"status": "error", "message": "No tiene taller registrado"}
    return {"status": "ok"}



@router.post(
    "/disconnect",
    status_code=status.HTTP_200_OK,
    summary="Avisar que el taller se desconecta (cierre de app o pérdida voluntaria)",
)
def report_disconnect(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_operational_roles("taller", "admin")),
):
    # Enviar notificación a los técnicos
    taller = db.query(Taller).filter(Taller.usuario_propietario_id == current.id).first()
    if taller:
        # Marcar heartbeat viejo
        taller.ultimo_heartbeat = None
        db.commit()
        
        # Notificar a los técnicos
        from app.modules.p5_pagos.services import NotificationService
        from app.modules.p1_usuarios.models import Usuario
        
        # Buscar usuarios que tienen rol 'tecnico' y están asignados a este taller
        # El modelo 'Tecnico' no está enlazado 1 a 1 a 'Usuario' en este diseño,
        # pero si lo estuvieran se notificaría ahí. Aquí simplemente dejamos el código
        # preparado para notificar a "técnicos del taller".
        # Asumimos que los técnicos son usuarios con rol tecnico asociados (si existe relación)
        # O simplemente registramos el evento si no hay vinculación de Usuario a Tecnico
        pass

    return {"status": "ok"}


@router.get(
    "/{workshop_id}/online-status",
    summary="Consultar si un taller está online",
)
def get_online_status(
    workshop_id: int,
    db: Session = Depends(get_db),
):
    taller = db.query(Taller).filter(Taller.id == workshop_id).first()
    if not taller:
        raise HTTPException(status_code=404, detail="Taller no encontrado")
    
    en_linea = WorkshopService._is_online(taller)
    return {"id": taller.id, "en_linea": en_linea}

@router.get(
    "/all",
    response_model=list[WorkshopOut],
    summary="Listar todos los talleres activos (público)",
)
def list_all_workshops(
    search: str = None,
    db: Session = Depends(get_db),
):
    return WorkshopService.list_all(db, search_query=search)

@router.get(
    "/active",
    response_model=list[WorkshopOut],
    summary="Listar todos los talleres activos del tenant",
)
def list_active_workshops(
    search: str = None,
    db: Session = Depends(get_db),
    current: Usuario = Depends(get_current_user),
):
    return WorkshopService.list_all_active(db, current.tenant_id, search_query=search)

# ═══════════════════════════════════════════════════════════════════════
# TALLERES FAVORITOS
# ═══════════════════════════════════════════════════════════════════════

@router.post(
    "/{workshop_id}/favorite",
    status_code=status.HTTP_200_OK,
    summary="Añadir taller a favoritos",
)
def add_favorite(
    workshop_id: int,
    db: Session = Depends(get_db),
    current: Usuario = Depends(get_current_user),
):
    WorkshopService.add_favorite(db, current.id, workshop_id)
    return {"message": "Taller añadido a favoritos"}

@router.delete(
    "/{workshop_id}/favorite",
    status_code=status.HTTP_200_OK,
    summary="Quitar taller de favoritos",
)
def remove_favorite(
    workshop_id: int,
    db: Session = Depends(get_db),
    current: Usuario = Depends(get_current_user),
):
    WorkshopService.remove_favorite(db, current.id, workshop_id)
    return {"message": "Taller removido de favoritos"}

@router.get(
    "/me/favorite-workshops",
    response_model=list[WorkshopOut],
    summary="Listar mis talleres favoritos",
)
def list_my_favorites(
    db: Session = Depends(get_db),
    current: Usuario = Depends(get_current_user),
):
    return WorkshopService.list_favorites(db, current.id)


@router.get(
    "/{workshop_id}",
    response_model=WorkshopOut,
    summary="Detalle de un taller",
)
def get_workshop(
    workshop_id: int,
    db: Session = Depends(get_db),
):
    return WorkshopService.get_by_id(db, workshop_id)


@router.post(
    "/{workshop_id}/technicians",
    response_model=TechnicianOut,
    status_code=status.HTTP_201_CREATED,
    summary="CU10 · Agregar técnico al taller",
)
def add_technician(
    workshop_id: int,
    payload: TechnicianCreate,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_operational_roles("taller", "admin")),
):
    return WorkshopService.add_technician(db, workshop_id, current.id, payload)


@router.get(
    "/{workshop_id}/technicians",
    response_model=list[TechnicianOut],
    summary="Listar técnicos del taller",
)
def list_technicians(
    workshop_id: int,
    db: Session = Depends(get_db),
):
    return WorkshopService.list_technicians(db, workshop_id)


# ═══════════════════════════════════════════════════════════════════════
# Disponibilidad de técnicos
# ═══════════════════════════════════════════════════════════════════════

@router.patch(
    "/technicians/{technician_id}/availability",
    response_model=TechnicianOut,
    summary="Toggle disponibilidad de técnico",
)
def update_availability(
    technician_id: int,
    payload: TechnicianAvailabilityUpdate,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_operational_roles("taller", "admin")),
):
    return WorkshopService.update_technician_availability(
        db, technician_id, current.id, payload.esta_disponible
    )


# ═══════════════════════════════════════════════════════════════════════
# CU11 — Recepción de solicitudes
# ═══════════════════════════════════════════════════════════════════════

@router.get(
    "/{workshop_id}/requests",
    response_model=list[ServiceRequestOut],
    summary="CU11 · Solicitudes pendientes del taller",
)
def list_requests(
    workshop_id: int,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_operational_roles("taller", "admin")),
):
    return WorkshopService.list_pending_requests(db, workshop_id, current.id)


# ═══════════════════════════════════════════════════════════════════════
# CU12 — Actualización de estado
# ═══════════════════════════════════════════════════════════════════════

from fastapi import BackgroundTasks

@router.patch(
    "/requests/{request_id}/status",
    response_model=ServiceRequestOut,
    summary="CU12 · Actualizar estado de solicitud",
)
def update_status(
    request_id: int,
    payload: ServiceStatusUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_operational_roles("taller", "admin")),
):
    return WorkshopService.update_service_status(db, request_id, current.id, payload, background_tasks)


# ═══════════════════════════════════════════════════════════════════════
# CU13 — Historial de atenciones
# ═══════════════════════════════════════════════════════════════════════

@router.get(
    "/{workshop_id}/history",
    response_model=list[ServiceHistoryOut],
    summary="CU13 · Historial de atenciones del taller",
)
def get_history(
    workshop_id: int,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_operational_roles("taller", "admin")),
):
    return WorkshopService.get_service_history(db, workshop_id, current.id)
