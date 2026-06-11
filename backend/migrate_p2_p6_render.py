import os
import time
from sqlalchemy import create_engine, text

RENDER_DB_URL = "postgresql://rutai_db_user:tRtlGpIRVZJqeznt5DXpIRnM00b9ly7v@dpg-d7nbd8dckfvc73et4mjg-a.oregon-postgres.render.com/rutai_db?sslmode=require"

def migrate():
    print("Conectando a BD Render...")
    engine = create_engine(RENDER_DB_URL)
    with engine.connect() as conn:
        print("Añadiendo columnas a incidentes...")
        conn.execute(text("ALTER TABLE incidentes ADD COLUMN IF NOT EXISTS tenant_secuencia INTEGER;"))
        conn.execute(text("ALTER TABLE incidentes ADD COLUMN IF NOT EXISTS codigo_visual VARCHAR(20);"))
        
        print("Añadiendo columnas a reportes_generados...")
        conn.execute(text("ALTER TABLE reportes_generados ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE;"))
        
        conn.commit()
        print("Migración de Render completada.")

if __name__ == "__main__":
    migrate()
