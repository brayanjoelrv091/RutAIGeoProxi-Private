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

        # Generar secuencia
        tenant_secuencia = None
        codigo_visual = None
        if tenant_id:
            max_sec = db.query(func.max(Bitacora.tenant_secuencia)).filter(Bitacora.tenant_id == tenant_id).scalar() or 0
            tenant_secuencia = int(max_sec) + 1
            codigo_visual = f"BIT-{tenant_secuencia:04d}"
        else:
            max_sec = db.query(func.max(Bitacora.tenant_secuencia)).filter(Bitacora.tenant_id.is_(None)).scalar() or 0
            tenant_secuencia = int(max_sec) + 1
            codigo_visual = f"SYS-{tenant_secuencia:04d}"

        b = Bitacora(
            usuario_id=usuario_id,
            tenant_id=tenant_id,
            tenant_secuencia=tenant_secuencia,
            codigo_visual=codigo_visual,
            rol=rol,
            accion=accion,
            ip=ip_addr
        )
        db.add(b)
        db.commit()
