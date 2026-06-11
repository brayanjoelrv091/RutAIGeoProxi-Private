"""
P2 — Modelos de Gestión de Incidentes.

Tablas:
    - ``incidentes``               → CU7
    - ``incidente_media``          → CU7 (fotos/audio)
    - ``clasificaciones_incidente`` → CU8 (resultado IA)
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.shared.database import Base
from app.modules.p7_seguridad_multitenant.models import Tenant  # Fix para NoReferencedTableError


class Incidente(Base):
    """CU7 · Reporte de incidente vehicular con ubicación GPS."""

    __tablename__ = "incidentes"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    titulo = Column(String(300), nullable=False)
    descripcion = Column(Text, nullable=True)
    estado = Column(
        String(30),
        nullable=False,
        default="pendiente",
        index=True,
    )  # pendiente | buscando_taller | taller_asignado | en_camino | en_atencion | finalizado | cancelado
    latitud = Column(Float, nullable=False)
    longitud = Column(Float, nullable=False)
    direccion = Column(String(500), nullable=True)
    url_audio = Column(String(1000), nullable=True)
    severidad = Column(String(30), nullable=True)   # leve | moderado | grave | critico
    categoria = Column(String(50), nullable=True)    # mecanico | electrico | carroceria | ...
    tipo_busqueda = Column(String(30), default="general", nullable=False) # general | categoria | preferido
    taller_preferido_id = Column(Integer, ForeignKey("talleres.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # ── Tracking de GPS (Nuevos campos) ──
    taller_latitud = Column(Float, nullable=True)
    taller_longitud = Column(Float, nullable=True)
    tiempo_llegada_estimado_minutos = Column(Integer, nullable=True)
    
    codigo_visual = Column(String(20), nullable=True, index=True)

    tiempo_estimado_reparacion_minutos = Column(Integer, nullable=True) # CU-32: ETA dinámico
    idempotency_key = Column(
        String(64),
        unique=True,
        nullable=True,
        index=True,
    )  # CU-23: UUID generado por el cliente para deduplicación offline
    creado_en_local = Column(
        DateTime(timezone=True),
        nullable=True,
    )  # CU-23: Timestamp generado localmente por el dispositivo offline
    creado_en = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    actualizado_en = Column(
        DateTime(timezone=True),
        nullable=True,
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Relaciones ──
    medios = relationship(
        "IncidenteMedia", back_populates="incidente", cascade="all, delete-orphan"
    )
    clasificacion = relationship(
        "ClasificacionIncidente",
        back_populates="incidente",
        uselist=False,
        cascade="all, delete-orphan",
    )
    # Relaciones cross-module (string refs para evitar imports circulares)
    solicitudes = relationship(
        "SolicitudServicio", back_populates="incidente", cascade="all, delete-orphan"
    )
    asignaciones = relationship(
        "Asignacion", back_populates="incidente", cascade="all, delete-orphan"
    )


class IncidenteMedia(Base):
    """CU7 · Archivo multimedia asociado a un incidente (foto o audio)."""

    __tablename__ = "incidente_media"

    id = Column(Integer, primary_key=True, index=True)
    incidente_id = Column(
        Integer,
        ForeignKey("incidentes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tipo_medio = Column(String(20), nullable=False)  # foto | audio
    url_archivo = Column(String(1000), nullable=False)
    subido_en = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # ── Relaciones ──
    incidente = relationship("Incidente", back_populates="medios")


class ClasificacionIncidente(Base):
    """CU8 · Resultado de la clasificación automática por IA."""

    __tablename__ = "clasificaciones_incidente"

    id = Column(Integer, primary_key=True, index=True)
    incidente_id = Column(
        Integer,
        ForeignKey("incidentes.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    categoria = Column(String(50), nullable=False)
    severidad = Column(String(30), nullable=False)
    confianza = Column(Float, nullable=False)  # 0.0 - 1.0
    razonamiento = Column(Text, nullable=True)
    metodo = Column(String(30), nullable=False, default="reglas")  # reglas | yolo | whisper | combinado
    clasificado_en = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # ── Relaciones ──
    incidente = relationship("Incidente", back_populates="clasificacion")
