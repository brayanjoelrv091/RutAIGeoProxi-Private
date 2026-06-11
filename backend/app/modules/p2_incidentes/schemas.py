"""
P2 — Schemas Pydantic para Incidentes.
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════
# INCIDENTE  (CU7)
# ═══════════════════════════════════════════════════════════════════════

class IncidentCreate(BaseModel):
    """Payload para crear un incidente (los medios se envían como multipart)."""
    titulo: str = Field(min_length=3, max_length=300)
    descripcion: str | None = Field(default=None, max_length=5000)
    latitud: float = Field(ge=-90, le=90)
    longitud: float = Field(ge=-180, le=180)
    direccion: str | None = Field(default=None, max_length=500)
    tipo_busqueda: str = Field(default="general", max_length=30)
    taller_preferido_id: int | None = Field(default=None)


class EstadoUpdate(BaseModel):
    """Payload para actualizar el estado del incidente."""
    estado: str = Field(..., max_length=30)



class MediaOut(BaseModel):
    id: int
    incidente_id: int
    tipo_medio: str
    url_archivo: str
    subido_en: datetime

    model_config = {"from_attributes": True}


class ClassificationOut(BaseModel):
    id: int
    incidente_id: int
    categoria: str
    severidad: str
    confianza: float
    razonamiento: str | None
    metodo: str
    clasificado_en: datetime

    model_config = {"from_attributes": True}


class IncidentOut(BaseModel):
    id: int
    codigo_visual: str | None = None
    usuario_id: int
    titulo: str
    descripcion: str | None
    estado: str
    latitud: float
    longitud: float
    direccion: str | None
    url_audio: str | None
    severidad: str | None
    categoria: str | None
    tipo_busqueda: str
    taller_preferido_id: int | None
    taller_latitud: float | None = None
    taller_longitud: float | None = None
    tiempo_llegada_estimado_minutos: int | None = None
    tiempo_estimado_reparacion_minutos: int | None = None
    creado_en: datetime
    actualizado_en: datetime | None

    model_config = {"from_attributes": True}


class IncidentDetailOut(IncidentOut):
    """CU9 — Ficha técnica estructurada completa."""
    medios: list[MediaOut] = Field(default_factory=list)
    clasificacion: ClassificationOut | None = None

    model_config = {"from_attributes": True}
