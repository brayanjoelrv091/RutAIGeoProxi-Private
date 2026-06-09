from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

RENDER_DB_URL = "postgresql://rutai_db_user:tRtlGpIRVZJqeznt5DXpIRnM00b9ly7v@dpg-d7nbd8dckfvc73et4mjg-a.oregon-postgres.render.com/rutai_db?sslmode=require"

engine = create_engine(RENDER_DB_URL)
Session = sessionmaker(bind=engine)
db = Session()

try:
    print("\n--- TALLERES ---")
    res = db.execute(text("SELECT id, nombre, latitud, longitud FROM talleres")).all()
    for r in res:
        print(f"ID: {r[0]} | Nombre: {r[1]} | Loc: ({r[2]}, {r[3]})")
    
    print("\n--- TÉCNICOS ---")
    res = db.execute(text("SELECT id, nombre, taller_id, esta_disponible FROM tecnicos")).all()
    for r in res:
        print(f"ID: {r[0]} | Nombre: {r[1]} | TallerID: {r[2]} | Disp: {r[3]}")

except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()
