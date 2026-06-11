import psycopg2

RENDER_DB_URL = "postgresql://rutai_db_user:tRtlGpIRVZJqeznt5DXpIRnM00b9ly7v@dpg-d7nbd8dckfvc73et4mjg-a.oregon-postgres.render.com/rutai_db"

def add_column_if_not_exists(conn, table_name, column_name, column_type):
    with conn.cursor() as cur:
        # Check if column exists
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name=%s and column_name=%s;
        """, (table_name, column_name))
        
        if not cur.fetchone():
            print(f"Adding column '{column_name}' to '{table_name}'...")
            cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type};")
            conn.commit()
            print("Success.")
        else:
            print(f"Column '{column_name}' already exists in '{table_name}'.")

try:
    conn = psycopg2.connect(RENDER_DB_URL, sslmode='require')
    
    # Columnas nuevas de incidentes
    add_column_if_not_exists(conn, "incidentes", "taller_latitud", "DOUBLE PRECISION NULL")
    add_column_if_not_exists(conn, "incidentes", "taller_longitud", "DOUBLE PRECISION NULL")
    add_column_if_not_exists(conn, "incidentes", "tiempo_llegada_estimado_minutos", "INTEGER NULL")
    add_column_if_not_exists(conn, "incidentes", "codigo_visual", "VARCHAR(20) NULL")
    add_column_if_not_exists(conn, "incidentes", "tiempo_estimado_reparacion_minutos", "INTEGER NULL")
    add_column_if_not_exists(conn, "incidentes", "idempotency_key", "VARCHAR(64) NULL")
    add_column_if_not_exists(conn, "incidentes", "creado_en_local", "TIMESTAMP WITH TIME ZONE NULL")
    
    conn.close()
    print("Migración completada.")
except Exception as e:
    print(f"Error: {e}")
