"""
P6 — Auditoría y Logs.

Tabla para la Bitácora de Auditoría que registra los movimientos importantes
de los usuarios por seguridad normativa.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.shared.database import Base
from app.modules.p7_seguridad_multitenant.models import Tenant  # Fix para NoReferencedTableError


class Bitacora(Base):
    """Auditoría: Quién lo hizo, cuándo, desde dónde y qué hizo."""

    __tablename__ = "bitacora"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    codigo_visual = Column(String(20), nullable=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True) # Puede ser nulo si el usuario fue borrado o no estaba logueado
    rol = Column(String(20), nullable=True)
    accion = Column(Text, nullable=False)
    ip = Column(String(50), nullable=True)
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
