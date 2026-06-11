"""
P1 — Modelos de Usuarios y Seguridad.

Tablas en español:
    - ``usuarios``
    - ``vehiculos``
    - ``tokens_recuperacion``
    - ``tokens_revocados``
"""

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.shared.database import Base
from app.modules.p7_seguridad_multitenant.models import Tenant  # Fix para NoReferencedTableError
from app.modules.p3_talleres.models import usuarios_talleres_favoritos


class Usuario(Base):
    """CU1-CU6 · Entidad principal de usuario del sistema."""

    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(
        Integer,
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    nombre = Column(String(200), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    telefono = Column(String(50), nullable=True)
    esta_activo = Column(Boolean, default=True, nullable=False)
    rol = Column(String(20), nullable=False, default="cliente")
    permisos = Column(JSON, nullable=True)
    fcm_token = Column(String(255), nullable=True)

    # ── Lockout & Security ──
    intentos_fallidos = Column(Integer, default=0, nullable=False)
    bloqueado_hasta = Column(DateTime(timezone=True), nullable=True)

    # ── Relaciones ──
    vehiculos = relationship(
        "Vehiculo", back_populates="propietario", cascade="all, delete-orphan"
    )
    tokens_recuperacion = relationship(
        "TokenRecuperacion", back_populates="usuario", cascade="all, delete-orphan"
    )
    talleres_favoritos = relationship(
        "Taller",
        secondary="usuarios_talleres_favoritos",
        backref="usuarios_que_favorecen"
    )


class Vehiculo(Base):
    """CU6 · Vehículo registrado por un cliente."""

    __tablename__ = "vehiculos"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    marca = Column(String(100), nullable=False)
    modelo = Column(String(100), nullable=False)
    placa = Column(String(20), nullable=False, index=True)
    anio = Column(Integer, nullable=True)
    color = Column(String(50), nullable=True)

    # ── Relaciones ──
    propietario = relationship("Usuario", back_populates="vehiculos")


class TokenRecuperacion(Base):
    """CU4 · Token de un solo uso para restablecer contraseña."""

    __tablename__ = "tokens_recuperacion"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(String(64), nullable=False, index=True)
    expira_en = Column(DateTime(timezone=True), nullable=False)
    usado_en = Column(DateTime(timezone=True), nullable=True)

    # ── Relaciones ──
    usuario = relationship("Usuario", back_populates="tokens_recuperacion")


class TokenRevocado(Base):
    """CU2 · JWT revocado al cerrar sesión (blacklist)."""

    __tablename__ = "tokens_revocados"

    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String(64), unique=True, nullable=False, index=True)
    expira_en = Column(DateTime(timezone=True), nullable=False)
    revocado_en = Column(DateTime(timezone=True), nullable=False)
