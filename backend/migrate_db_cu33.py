import sqlite3

def upgrade():
    try:
        conn = sqlite3.connect('rutaigeoproxi.db')
        cursor = conn.cursor()
        
        # Agregamos columnas para CU-33
        cursor.execute("ALTER TABLE pagos ADD COLUMN tenant_id INTEGER;")
        cursor.execute("ALTER TABLE pagos ADD COLUMN stripe_checkout_session_id VARCHAR(150);")
        
        conn.commit()
        print("✅ Migración exitosa: columnas de Stripe agregadas a pagos.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("⚠️ Alguna columna ya existe, ignorando.")
        else:
            print(f"❌ Error al migrar: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    upgrade()
