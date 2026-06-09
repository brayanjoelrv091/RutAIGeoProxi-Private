import os
import sys

dir_actual = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(dir_actual)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app.shared.database import SessionLocal
from app.modules.p1_usuarios.models import Usuario
from app.modules.p3_talleres.models import Taller

db = SessionLocal()

user = db.query(Usuario).filter(Usuario.email == "admin@ruta.com").first()
if user:
    print("Admin user:", user.email, "tenant_id:", user.tenant_id)
else:
    print("User admin@ruta.com not found")
    
taller = db.query(Taller).filter(Taller.nombre == "Taller Mecánico Centro").first()
if taller:
    print("Taller:", taller.nombre, "tenant_id:", taller.tenant_id)
else:
    print("Taller not found")
