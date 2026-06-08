"""
Configuración de SQLAlchemy: engine, session factory y Base declarativa.

Soporta SQLite (desarrollo local) y PostgreSQL (producción en Render).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.shared.config import settings

# ── Engine adaptado al tipo de base de datos ──
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
else:
    # PostgreSQL en producción (Render)
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=300,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# --- AQUÍ ESTÁ LA FUNCIÓN MÁGICA QUE FALTABA ---
# Función para obtener la sesión de la base de datos en cada petición
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Interceptor ORM para Multi-Tenant (CU-28) ──
from sqlalchemy import event
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

@event.listens_for(Session, "do_orm_execute")
def _add_tenant_filter(execute_state):
    """
    Intercepta cada consulta enviada por SQLAlchemy. Si el modelo destino
    tiene la columna 'tenant_id' y el usuario no es un SuperAdmin Global,
    inyecta automáticamente un filtro `.filter(tenant_id == X)`.
    """
    if execute_state.is_select and not execute_state.is_column_load and not execute_state.is_relationship_load:
        from app.shared.context import current_tenant_id, is_superadmin
        
        # Omitir si es un superadmin operando globalmente
        if is_superadmin.get():
            return

        tenant_id = current_tenant_id.get()
        if tenant_id is None:
            # Si un request llega sin tenant_id y sin ser superadmin, no asume nada
            # (El filtro podría fallar si se requiere org, pero deps.py bloquea tokens sin tenant_id)
            pass

        # Manera moderna en SQLAlchemy 2.0 de interceptar e inyectar un criterio:
        # Aplicamos el filtro a todas las entidades del query que tengan tenant_id
        # execute_state.statement es el Select object
        statement = execute_state.statement
        if isinstance(statement, Select):
            for column in statement.get_final_froms():
                if "tenant_id" in column.columns:
                    # Inyectar el filtro
                    # SQLAlchemy 2.0 syntax para añadir where criteria
                    execute_state.statement = statement.where(column.columns.tenant_id == tenant_id)
