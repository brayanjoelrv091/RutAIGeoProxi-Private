"""
P7 — Schemas Pydantic para Seguridad y Multi-Tenant.
"""

from datetime import datetime
from pydantic import BaseModel, Field, model_validator
import re

class TenantBase(BaseModel):
    nombre: str = Field(min_length=2, max_length=200)
    slug: str = Field(default="", max_length=100)
    esta_activo: bool = True
    plan: str = "basico"

class TenantCreate(TenantBase):
    email_admin: str | None = Field(default=None, description="Email del primer administrador del tenant")
    # Campos legacy del frontend viejo (se mapean automáticamente)
    dominio: str | None = None
    estado: str | None = None

    model_config = {"extra": "ignore"}

    @model_validator(mode="before")
    @classmethod
    def map_legacy_fields(cls, values):
        """Compatibilidad: acepta 'dominio' como alias de 'slug' y 'estado' como alias de 'esta_activo'."""
        if isinstance(values, dict):
            # dominio -> slug
            if not values.get("slug") and values.get("dominio"):
                values["slug"] = values["dominio"]
            # estado -> esta_activo
            if "estado" in values and "esta_activo" not in values:
                values["esta_activo"] = values["estado"] in ("activo", True)
            # Auto-generar slug desde nombre si sigue vacío
            if not values.get("slug") and values.get("nombre"):
                values["slug"] = re.sub(r'[^a-z0-9]+', '-', values["nombre"].lower()).strip('-')
        return values

class TenantUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=200)
    slug: str | None = Field(default=None, min_length=2, max_length=100)
    esta_activo: bool | None = None
    plan: str | None = None

class TenantSubscriptionHistoryOut(BaseModel):
    id: int
    plan: str
    estado_pago: str
    metodo_pago: str
    monto_pago: int
    fecha_inicio: datetime
    fecha_fin: datetime | None = None

    model_config = {"from_attributes": True}

class TenantOut(TenantBase):
    id: int
    creado_en: datetime
    fecha_fin_plan: datetime | None = None
    estado_pago: str | None = None
    metodo_pago: str | None = None
    monto_pago: float | None = None
    checkout_url: str | None = None
    historial_suscripciones: list[TenantSubscriptionHistoryOut] = []

    model_config = {"from_attributes": True}

class MembershipCreate(BaseModel):
    usuario_id: int
    rol_en_tenant: str = "miembro"

class MembershipOut(BaseModel):
    id: int
    usuario_id: int
    tenant_id: int
    rol_en_tenant: str

    model_config = {"from_attributes": True}

class TenantUpgradeRequest(BaseModel):
    nuevo_plan: str # "profesional" o "empresarial"
    metodo_pago: str | None = None

class TenantUpgradeConfirmRequest(BaseModel):
    nuevo_plan: str
    metodo_pago: str
    monto: float
