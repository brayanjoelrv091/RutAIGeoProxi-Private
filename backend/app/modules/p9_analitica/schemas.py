"""
P9 — Schemas Pydantic para Analítica y Cotizaciones.
"""

from datetime import datetime
from pydantic import BaseModel, Field

# ── Analítica ──

class KPIMetric(BaseModel):
    label: str
    value: float | int | str
    tendencia: str | None = None  # up | down | neutral

class DashboardKPIs(BaseModel):
    tenant_id: int | None
    total_incidentes: int
    completados: int
    cancelados: int
    tiempo_promedio_asignacion_min: float
    tiempo_promedio_resolucion_min: float
    tiempo_promedio_llegada_min: float = 0.0
    nivel_cumplimiento_sla: float = 0.0
    incidentes_por_categoria: dict[str, int]
    incidentes_por_severidad: dict[str, int]
    talleres_mas_eficientes: list[dict[str, str | float]] = Field(default_factory=list)
    zonas_calientes: list[dict[str, str | int]] = Field(default_factory=list)

# ── Estimación de Tiempo (CU-32) ──
class TiempoEstimadoOut(BaseModel):
    incidente_id: int
    tiempo_estimado_dias: int
    rango_dias: str
    razonamiento: str

from decimal import Decimal
from pydantic import BaseModel, Field

# ── Cotizaciones (CU-30) ──

class CotizacionItemBase(BaseModel):
    descripcion: str
    cantidad: int = Field(ge=1)
    precio_unitario: Decimal = Field(ge=Decimal("0.0"))

class CotizacionItemCreate(CotizacionItemBase):
    pass

class CotizacionItemOut(CotizacionItemBase):
    id: int
    
    model_config = {"from_attributes": True}

class CotizacionCreateManual(BaseModel):
    incidente_id: int
    notas: str | None = None
    items: list[CotizacionItemCreate] = Field(min_length=1)

class CotizacionCreate(BaseModel):
    incidente_id: int
    notas: str | None = None

class CotizacionUpdate(BaseModel):
    estado: str  # borrador | enviada | aceptada | rechazada
    notas: str | None = None

class CotizacionRespuesta(BaseModel):
    estado: str = Field(..., description="ACEPTADA, RECHAZADA, o AJUSTE_SOLICITADO")
    notas: str | None = None

class CotizacionOut(BaseModel):
    id: int
    incidente_id: int
    tenant_id: int | None
    subtotal: Decimal
    iva: Decimal
    total: Decimal
    estado: str
    notas: str | None
    tiempo_estimado_dias: int | None
    expires_at: datetime | None
    creado_en: datetime
    actualizado_en: datetime | None
    items: list[CotizacionItemOut]

    model_config = {"from_attributes": True}
