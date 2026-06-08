import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.shared.database import SessionLocal, engine, Base

# Importar todos los modelos para que Base.metadata los reconozca
import app.modules.p1_usuarios.models
import app.modules.p2_incidentes.models
import app.modules.p3_talleres.models
import app.modules.p4_asignacion.models
import app.modules.p5_pagos.models
import app.modules.p7_seguridad_multitenant.models

def limpiar_seguro():
    db = SessionLocal()
    try:
        # Obtenemos las tablas ordenadas por dependencias (padres primero)
        # Hacemos reversed() para vaciar primero las tablas hijas y evitar errores de Foreign Key
        tables = reversed(Base.metadata.sorted_tables)
        
        print("Iniciando limpieza segura de la base de datos...")
        print("------------------------------------------------")
        
        for table in tables:
            if table.name == "usuarios":
                print(f"Limpiando {table.name} (manteniendo a los Superadmins)...")
                # Borramos solo usuarios que pertenecen a algún tenant
                # (Los superadmins tienen tenant_id = None)
                db.execute(table.delete().where(table.c.tenant_id != None))
            elif table.name == "notificaciones":
                # Las notificaciones tienen foreign key a usuario.
                # Es más seguro vaciarlas todas (no afectan la estructura del superadmin)
                print(f"Limpiando {table.name}...")
                db.execute(table.delete())
            else:
                print(f"Limpiando {table.name}...")
                db.execute(table.delete())
                
        db.commit()
        print("------------------------------------------------")
        print("¡Limpieza exitosa! Todos los talleres y clientes borrados.")
        print("Tu Superadmin sigue vivo y con sus privilegios intactos.")
        
    except Exception as e:
        print(f"Error durante la limpieza: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    limpiar_seguro()
