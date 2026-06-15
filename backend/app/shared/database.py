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
    Intercepta cada consulta enviada por postegre. Si el modelo destino
    tiene la columna 'tenant_id' y el usuario no es un SuperAdmin Global,
    inyecta automáticamente un filtro `.filter(tenant_id == X)`.
    """
    if execute_state.is_select and not execute_state.is_column_load and not execute_state.is_relationship_load:
        from app.shared.context import current_tenant_id, is_superadmin
        
        if is_superadmin.get():
            return

        tenant_id = current_tenant_id.get()
        if tenant_id is None:
            # Si un request llega sin tenant_id y sin ser superadmin, es un endpoint público (login, registro)
            # No inyectamos nada para permitir consultas globales necesarias.
            return

        # Función auxiliar para extraer tablas reales de posibles joins
        def get_tables(from_obj):
            if hasattr(from_obj, 'original'):
                yield from get_tables(from_obj.original)
            elif hasattr(from_obj, 'left') and hasattr(from_obj, 'right'):
                yield from get_tables(from_obj.left)
                yield from get_tables(from_obj.right)
            elif hasattr(from_obj, 'element'):
                yield from get_tables(from_obj.element)
            else:
                yield from_obj

        # Manera moderna en SQLAlchemy 2.0 de interceptar e inyectar un criterio:
        statement = execute_state.statement
        if isinstance(statement, Select):
            for from_obj in statement.get_final_froms():
                for table in get_tables(from_obj):
                    if hasattr(table, 'columns') and "tenant_id" in table.columns:
                        statement = statement.where(table.columns.tenant_id == tenant_id)
            execute_state.statement = statement

