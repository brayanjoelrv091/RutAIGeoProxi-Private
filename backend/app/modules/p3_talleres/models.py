"""
P3 — Modelos de Gestión de Talleres.

Tablas:
    - ``talleres``               → CU10
    - ``tecnicos``               → CU10 (con GPS)
    - ``solicitudes_servicio``   → CU11, CU12, CU13
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy import Table

from app.shared.database import Base
from app.modules.p4_asignacion.models import Asignacion


usuarios_talleres_favoritos = Table(
    "usuarios_talleres_favoritos",
    Base.metadata,
    Column("usuario_id", Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True),
    Column("taller_id", Integer, ForeignKey("talleres.id", ondelete="CASCADE"), primary_key=True),
    Column("creado_en", DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)),
)


class Taller(Base):
    """CU10 · Taller de servicio mecánico registrado en el sistema."""

    __tablename__ = "talleres"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    usuario_propietario_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nombre = Column(String(200), nullable=False)
    direccion = Column(String(500), nullable=False)
    latitud = Column(Float, nullable=False)
    longitud = Column(Float, nullable=False)
    telefono = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    especialidades = Column(JSON, nullable=True)  # ["mecanico", "electrico", ...]
    esta_activo = Column(Boolean, default=True, nullable=False)
    estado_registro = Column(String(30), default="pendiente_tecnicos", nullable=False)
    ultimo_heartbeat = Column(DateTime(timezone=True), nullable=True)
    calificacion_promedio = Column(Float, default=0.0, nullable=False)
    creado_en = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # ── Relaciones ──
    propietario = relationship("Usuario", backref="talleres")
    tecnicos = relationship(
        "Tecnico", back_populates="taller", cascade="all, delete-orphan"
    )
    solicitudes = relationship(
        "SolicitudServicio", back_populates="taller", cascade="all, delete-orphan"
    )
    asignaciones = relationship(
        "Asignacion", back_populates="taller", cascade="all, delete-orphan"
    )


class Tecnico(Base):
    """CU10 · Técnico vinculado a un taller con ubicación GPS."""

    __tablename__ = "tecnicos"

    id = Column(Integer, primary_key=True, index=True)
    taller_id = Column(
        Integer,
        ForeignKey("talleres.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nombre = Column(String(200), nullable=False)
    telefono = Column(String(50), nullable=True)
    especialidad = Column(String(50), nullable=True)  # mecanico, electrico, etc.
    esta_disponible = Column(Boolean, default=True, nullable=False)
    latitud = Column(Float, nullable=True)   # GPS del técnico
    longitud = Column(Float, nullable=True)  # GPS del técnico

    # ── Relaciones ──
    taller = relationship("Taller", back_populates="tecnicos")
    solicitudes = relationship("SolicitudServicio", back_populates="tecnico")


# ── Estados válidos de solicitud de servicio ──
ESTADOS_SOLICITUD = ("pendiente", "proceso", "atendido", "cancelado")


class SolicitudServicio(Base):
    """CU11-CU13 · Solicitud de servicio de asistencia técnica."""

    __tablename__ = "solicitudes_servicio"

    id = Column(Integer, primary_key=True, index=True)
    incidente_id = Column(
        Integer,
        ForeignKey("incidentes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    taller_id = Column(
        Integer,
        ForeignKey("talleres.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tecnico_id = Column(
        Integer,
        ForeignKey("tecnicos.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    estado = Column(
        String(30),
        nullable=False,
        default="pendiente",
        index=True,
    )  # pendiente | proceso | atendido | cancelado
    notas = Column(Text, nullable=True)
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
    incidente = relationship("Incidente", back_populates="solicitudes")
    taller = relationship("Taller", back_populates="solicitudes")
    tecnico = relationship("Tecnico", back_populates="solicitudes")
