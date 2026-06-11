from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.shared.database import get_db
from app.shared.deps import require_roles
from app.modules.p1_usuarios.models import Usuario
from app.modules.p6_auditoria.services import AuditService
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/admin/audit", tags=["P6 · Auditoría"])

class BitacoraOut(BaseModel):
    id: int
    codigo_visual: str | None = None
    usuario_id: int | None
    usuario_nombre: str | None = None
    usuario_email: str | None = None
    rol: str | None
    accion: str
    ip: str | None = None
    creado_en: datetime

    model_config = {"from_attributes": True}

@router.get("", response_model=List[BitacoraOut], summary="Listar bitácora de auditoría (Solo Admin)")
def list_audit_logs(
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles("admin"))
):
    """
    Retorna todos los eventos registrados en la bitácora.
    Solo accesible por usuarios con rol 'admin'.
    Filtra por tenant si el admin pertenece a uno específico.
    """
    from app.modules.p6_auditoria.models import Bitacora
    query = db.query(Bitacora)
    
    if current.tenant_id is not None:
        query = query.join(Usuario, Bitacora.usuario_id == Usuario.id).filter(Usuario.tenant_id == current.tenant_id)
    else:
        # A1: Solo ve bitácoras de usuarios sin tenant (SuperAdmins) o del sistema (usuario_id = None)
        query = query.outerjoin(Usuario, Bitacora.usuario_id == Usuario.id).filter(
            (Usuario.tenant_id.is_(None)) | (Bitacora.usuario_id.is_(None))
        )
        
    results = query.order_by(Bitacora.creado_en.desc()).all()
    
    out = []
    for b in results:
        user = db.query(Usuario).filter(Usuario.id == b.usuario_id).first() if b.usuario_id else None
        out.append({
            "id": b.id,
            "codigo_visual": b.codigo_visual,
            "usuario_id": b.usuario_id,
            "usuario_nombre": user.nombre if user else "Sistema",
            "usuario_email": user.email if user else "N/A",
            "rol": b.rol,
            "accion": b.accion,
            "ip": b.ip,
            "creado_en": b.creado_en
        })
    return out
