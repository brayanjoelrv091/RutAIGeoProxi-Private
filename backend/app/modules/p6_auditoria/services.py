"""
P6 — Servicio de Auditoría (Bitácora).
"""

from fastapi import Request
from sqlalchemy.orm import Session
from app.modules.p6_auditoria.models import Bitacora


class AuditService:
    @staticmethod
    def log(
        db: Session,
        accion: str,
        request: Request | None = None,
        usuario_id: int | None = None,
        rol: str | None = None,
    ) -> None:
        """Registra un evento crítico en la bitácora."""
        
        ip_addr = "Desconocida"
        if request and request.client:
            ip_addr = request.client.host
            
        from sqlalchemy import func
        
        # Intentar obtener tenant_id del usuario si existe
        tenant_id = None
        if usuario_id:
            from app.modules.p1_usuarios.models import Usuario
            user = db.query(Usuario).filter(Usuario.id == usuario_id).first()
            if user:
                tenant_id = user.tenant_id

        b = Bitacora(
            usuario_id=usuario_id,
            tenant_id=tenant_id,
            rol=rol,
            accion=accion,
            ip=ip_addr
        )
        db.add(b)
        db.flush()
        if b.id:
            b.codigo_visual = f"BIT-{b.id:04d}" if tenant_id else f"SYS-{b.id:04d}"
        db.commit()
