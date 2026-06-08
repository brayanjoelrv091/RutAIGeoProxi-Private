"""
P9 — Modelos de Analítica y Operaciones (CU-27, CU-30, CU-32).

Tablas:
    - ``kpi_snapshots``
    - ``cotizaciones``
    - ``cotizacion_items``
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Numeric, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.shared.database import Base


class KPISnapshot(Base):
    """CU27 · Snapshot de KPIs para analítica histórica."""

    __tablename__ = "kpi_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    total_incidentes = Column(Integer, nullable=False, default=0)
    tiempo_promedio_asignacion_min = Column(Numeric(10, 2), nullable=False, default=0.0)
    tiempo_promedio_resolucion_min = Column(Numeric(10, 2), nullable=False, default=0.0)
    incidentes_completados = Column(Integer, nullable=False, default=0)
    incidentes_cancelados = Column(Integer, nullable=False, default=0)
    fecha_snapshot = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class Cotizacion(Base):
    """CU30 · Cotización de reparación generada manual o por IA."""

    __tablename__ = "cotizaciones"

    id = Column(Integer, primary_key=True, index=True)
    incidente_id = Column(
        Integer,
        ForeignKey("incidentes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    subtotal = Column(Numeric(10, 2), nullable=False, default=0.0)
    iva = Column(Numeric(10, 2), nullable=False, default=0.0)
    total = Column(Numeric(10, 2), nullable=False, default=0.0)
    estado = Column(String(30), nullable=False, default="borrador")  # borrador | enviada | aceptada | rechazada | ajuste_solicitado
    notas = Column(Text, nullable=True)
    tiempo_estimado_dias = Column(Integer, nullable=True)  # CU-32
    
    # CU-30 Expiración
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
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
    items = relationship("CotizacionItem", back_populates="cotizacion", cascade="all, delete-orphan")


class CotizacionItem(Base):
    """Línea de detalle de una cotización (Repuestos, Mano de obra, etc.)."""

    __tablename__ = "cotizacion_items"

    id = Column(Integer, primary_key=True, index=True)
    cotizacion_id = Column(
        Integer,
        ForeignKey("cotizaciones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    descripcion = Column(String(300), nullable=False)
    cantidad = Column(Integer, nullable=False, default=1)
    precio_unitario = Column(Numeric(10, 2), nullable=False, default=0.0)

    # ── Relaciones ──
    cotizacion = relationship("Cotizacion", back_populates="items")
