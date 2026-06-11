"""
P9 — Rutas de Analítica y Operaciones.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.shared.deps import get_current_user, get_db, get_current_tenant_id, require_roles
from app.modules.p1_usuarios.models import Usuario
from app.modules.p9_analitica.schemas import (
    DashboardKPIs,
    CotizacionOut,
    CotizacionCreateManual,
    CotizacionRespuesta,
    TiempoEstimadoOut
)
from app.modules.p9_analitica.services import DashboardService, CotizacionService, EstimacionService

router = APIRouter(prefix="/analytics", tags=["P9 · Analítica Operacional y Cotizaciones"])

# ── Dashboard KPIs ──

@router.get("/dashboard", response_model=DashboardKPIs, summary="CU27 · Dashboard de KPIs")
def get_dashboard(
    tenant_id: int | None = None, # Opcional: superadmin puede consultar un tenant específico
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Obtiene métricas operacionales del tenant actual."""
    from app.shared.context import current_tenant_id, is_superadmin

    # Si es admin y pide un tenant_id específico, lo usamos. Sino usamos el suyo.
    target_tenant = tenant_id if (current_user.rol == "admin" and tenant_id) else current_user.tenant_id

    # Si es un superadmin consultando un tenant en particular, fíngimos el contexto
    # temporalmente para que el interceptor ORM inyecte el filtro del tenant_id.
    if current_user.rol == "admin" and current_user.tenant_id is None and tenant_id is not None:
        token_tenant = current_tenant_id.set(tenant_id)
        token_admin = is_superadmin.set(False)
        try:
            return DashboardService.get_kpis(db, target_tenant)
        finally:
            current_tenant_id.reset(token_tenant)
            is_superadmin.reset(token_admin)

    return DashboardService.get_kpis(db, target_tenant)


# ── Estimaciones y Cotizaciones ──

@router.get("/estimate/{incident_id}", response_model=TiempoEstimadoOut, summary="CU32 · Calcular tiempo estimado")
def get_estimacion(
    incident_id: int,
    db: Session = Depends(get_db),
    _current: Usuario = Depends(get_current_user),
):
    """Calcula el tiempo estimado de reparación basado en la severidad y categoría del incidente."""
    return EstimacionService.calcular_tiempo_estimado(db, incident_id)


@router.post("/quotations/{incident_id}", response_model=CotizacionOut, status_code=status.HTTP_201_CREATED, summary="Generar Cotización IA")
def generar_cotizacion(
    incident_id: int,
    db: Session = Depends(get_db),
    _current: Usuario = Depends(get_current_user),
):
    """Genera una cotización detallada basándose en el análisis de IA del incidente."""
    return CotizacionService.generar_cotizacion_desde_ia(db, incident_id)

@router.post("/quotations_manual", response_model=CotizacionOut, status_code=status.HTTP_201_CREATED, summary="CU30 · Generar Cotización Manual")
def crear_cotizacion_manual(
    schema: CotizacionCreateManual,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles("taller", "admin")),
):
    """Crea una cotización manual con cálculo financiero estricto y notifica al cliente."""
    return CotizacionService.crear_cotizacion_manual(db, schema, current_user.tenant_id)


@router.patch("/quotations/{cotizacion_id}/respuesta", response_model=CotizacionOut, summary="CU30 · Responder Cotización")
def responder_cotizacion(
    cotizacion_id: int,
    schema: CotizacionRespuesta,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles("cliente", "admin")),
):
    """El cliente acepta, rechaza o solicita ajuste. Valida timeout."""
    return CotizacionService.responder_cotizacion(db, cotizacion_id, schema.estado, schema.notas)


@router.get("/quotations/{cotizacion_id}", response_model=CotizacionOut, summary="Ver detalle de Cotización")
def get_cotizacion(
    cotizacion_id: int,
    db: Session = Depends(get_db),
    _current: Usuario = Depends(get_current_user),
):
    return CotizacionService.get_cotizacion(db, cotizacion_id)
    """Obtiene los detalles y desgloses de una cotización."""
    return CotizacionService.get_cotizacion(db, cotizacion_id)
