"""
Dependencias compartidas de FastAPI (inyectables vía ``Depends``).

- ``get_db``            → sesión SQLAlchemy por request
- ``get_current_user``  → usuario autenticado desde JWT
- ``require_roles``     → factory de guards por rol
"""

from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.shared.database import SessionLocal
from app.shared.security import jwt_payload_safe

security = HTTPBearer()


# ── Sesión de base de datos ────────────────────────────────────────────
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Token crudo ────────────────────────────────────────────────────────
def get_token_credentials(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    return credentials.credentials


# ── Usuario autenticado ───────────────────────────────────────────────
def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(get_token_credentials),
):
    """Resuelve el usuario que porta el JWT. Importa modelos inline
    para evitar ciclos de importación entre módulos."""
    from app.modules.p1_usuarios.models import TokenRevocado, Usuario

    payload = jwt_payload_safe(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        )

    jti = payload.get("jti")
    if jti and db.query(TokenRevocado).filter(TokenRevocado.jti == jti).first():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión cerrada",
        )

    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        )

    user = db.query(Usuario).filter(Usuario.id == int(sub)).first()
    if not user or not user.esta_activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo",
        )
        
    if user.tenant_id:
        from app.modules.p7_seguridad_multitenant.models import Tenant
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if tenant and not tenant.esta_activo:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tu cuenta de empresa ha sido suspendida. Contacta a soporte para regularizar tu suscripción.",
            )
            
    # CU-28: Inyectar variables en contexto para el filtrado a nivel de ORM
    from app.shared.context import current_tenant_id, is_superadmin
    current_tenant_id.set(user.tenant_id)
    is_superadmin.set(user.rol == "admin" and user.tenant_id is None)
            
    return user


# ── Guard por rol ───────────────────────────────────────────────────
def require_roles(*roles: str):
    """Retorna una dependencia que valida que el usuario tenga alguno
    de los roles indicados."""

    def _dep(user=Depends(get_current_user)):
        if user.rol not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permisos insuficientes",
            )
        return user

    return _dep


# ── Guard por rol operativo ─────────────────────────────────────────
def require_operational_roles(*roles: str):
    """Retorna una dependencia que valida que el usuario tenga alguno
    de los roles indicados Y que no sea un SuperAdmin sin tenant_id, 
    bloqueando su acceso a rutas operativas (talleres, asignaciones, etc)."""

    def _dep(user=Depends(get_current_user)):
        if user.rol not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permisos insuficientes",
            )
        if user.rol == "admin" and user.tenant_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El SuperAdmin no puede realizar acciones operativas.",
            )
        return user

    return _dep


# ── Guard por Tenant ────────────────────────────────────────────────
def get_current_tenant_id(user=Depends(get_current_user)) -> int | None:
    """Extrae el tenant_id del usuario actual. Si es None, es un superadmin sin org."""
    return user.tenant_id

def require_tenant_access(target_tenant_id: int):
    """Valida que el usuario pertenezca al tenant al que intenta acceder o sea superadmin."""
    def _dep(user=Depends(get_current_user)):
        if user.rol == "admin" and user.tenant_id is None:
            return user  # Superadmin global
            
        if user.tenant_id != target_tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No perteneces a esta organización",
            )
        return user
    return _dep


# ── Guard por SuperAdmin Global ─────────────────────────────────────
def get_current_superadmin(user=Depends(get_current_user)):
    """Valida que el usuario sea estrictamente un SuperAdmin Global (sin tenant_id)."""
    if user.rol != "admin" or user.tenant_id is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: Se requieren privilegios de Super-Admin Global."
        )
    return user

