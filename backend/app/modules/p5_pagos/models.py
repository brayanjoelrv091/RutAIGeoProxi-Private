"""
P5 — Modelos de Pagos y Notificaciones.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Numeric,
    DateTime,
    ForeignKey,
    Text,
    Boolean,
)
from app.shared.database import Base


def _utc_now():
    return datetime.now(timezone.utc)


class Pago(Base):
    """
    CU33 · Registro de transacciones con Stripe.
    """

    __tablename__ = "pagos"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    incidente_id = Column(Integer, ForeignKey("incidentes.id"), nullable=False)
    monto = Column(Numeric(10, 2), nullable=False)
    comision_plataforma = Column(Numeric(10, 2), default=0.00)  # 10% para la empresa
    moneda = Column(String(10), default="USD")
    estado = Column(String(30), default="pendiente")  # pendiente | completado | fallido
    metodo_pago = Column(String(50))  # tarjeta | transferencia | efectivo
    proveedor = Column(String(50), default="stripe")
    stripe_checkout_session_id = Column(String(150), unique=True, index=True, nullable=True)
    transaccion_id = Column(String(100), unique=True, nullable=True)  # ID externo real (PaymentIntent)
    gateway_response = Column(Text, nullable=True) # JSON raw de la respuesta del proveedor
    creado_at = Column(DateTime, default=_utc_now)


class Notificacion(Base):
    """
    CU16 · Historial de notificaciones enviadas.
    """

    __tablename__ = "notificaciones"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    titulo = Column(String(200), nullable=False)
    mensaje = Column(Text, nullable=False)
    leido = Column(Boolean, default=False)  # False: No leido, True: Leido
    tipo = Column(String(50))  # push | email | sistema
    creado_at = Column(DateTime, default=_utc_now)
