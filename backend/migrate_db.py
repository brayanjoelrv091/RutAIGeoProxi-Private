import sqlite3

def upgrade():
    try:
        conn = sqlite3.connect('rutaigeoproxi.db')
        cursor = conn.cursor()
        
        # Agregamos la columna para CU-32
        cursor.execute("ALTER TABLE incidentes ADD COLUMN tiempo_estimado_reparacion_minutos INTEGER;")
        
        conn.commit()
        print("✅ Migración exitosa: columna 'tiempo_estimado_reparacion_minutos' agregada a SQLite.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("⚠️ La columna ya existe, no es necesario hacer nada.")
        else:
            print(f"❌ Error al migrar: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    upgrade()
