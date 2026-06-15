import os
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from app.shared.database import SessionLocal, engine
from app.modules.p1_usuarios.models import Usuario
from app.modules.p2_incidentes.models import Incidente, ClasificacionIncidente
from app.modules.p3_talleres.models import Taller, Tecnico
from app.modules.p4_asignacion.models import Asignacion
from app.modules.p9_analitica.models import Cotizacion
from app.modules.p7_seguridad_multitenant.models import Tenant

def seed_dashboard(tenant_id=6):
    db: Session = SessionLocal()
    
    print(f"--- Seeding DB for Tenant {tenant_id} ---")
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        tenant = Tenant(id=tenant_id, nombre=f"Tenant Seeded {tenant_id}", slug=f"tenant-{tenant_id}", esta_activo=True, plan="pro")
        db.add(tenant)
        db.commit()
    
    
    # 1. Create a dummy client user if not exists
    client = db.query(Usuario).filter(Usuario.tenant_id == tenant_id, Usuario.rol == 'cliente').first()
    if not client:
        client = Usuario(
            tenant_id=tenant_id,
            nombre="Cliente Seed",
            email=f"clienteseed_{tenant_id}@test.com",
            hashed_password="hash",
            rol="cliente"
        )
        db.add(client)
        db.commit()
        db.refresh(client)
    
    # 2. Create some dummy workshops
    workshops = []
    for i in range(3):
        propietario = db.query(Usuario).filter(Usuario.email == f"tallerseed_{tenant_id}_{i}@test.com").first()
        if not propietario:
            propietario = Usuario(
                tenant_id=tenant_id,
                nombre=f"Propietario Taller {i}",
                email=f"tallerseed_{tenant_id}_{i}@test.com",
                hashed_password="hash",
                rol="taller"
            )
            db.add(propietario)
            db.commit()
            db.refresh(propietario)
            
        taller = db.query(Taller).filter(Taller.usuario_propietario_id == propietario.id).first()
        if not taller:
            taller = Taller(
                tenant_id=tenant_id,
                usuario_propietario_id=propietario.id,
                nombre=f"Taller Mecánico Seed {i+1}",
                direccion=f"Av Seed {i*100}",
                latitud=-16.5 + random.uniform(-0.05, 0.05),
                longitud=-68.1 + random.uniform(-0.05, 0.05),
                esta_activo=True
            )
            db.add(taller)
            db.commit()
            db.refresh(taller)
        workshops.append(taller)

    # 3. Create 30 Incidents
    categorias = ["mecanico", "electrico", "carroceria", "llantas"]
    severidades = ["leve", "moderado", "grave", "critico"]
    estados = ["finalizado"] * 18 + ["pendiente"] * 5 + ["cancelado"] * 4 + ["taller_asignado"] * 3
    
    now = datetime.now(timezone.utc)
    
    for i in range(30):
        # random date in last 30 days
        creado = now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23), minutes=random.randint(0, 59))
        
        estado = estados[i]
        cat = random.choice(categorias)
        sev = random.choice(severidades)
        
        incidente = Incidente(
            tenant_id=tenant_id,
            usuario_id=client.id,
            titulo=f"Incidente de prueba {i}",
            descripcion=f"Descripción sembrada {i}",
            estado=estado,
            categoria=cat,
            severidad=sev,
            latitud=-16.5 + random.uniform(-0.05, 0.05),
            longitud=-68.1 + random.uniform(-0.05, 0.05),
            creado_en=creado,
            actualizado_en=creado + timedelta(minutes=random.randint(10, 120)) if estado != "pendiente" else creado
        )
        db.add(incidente)
        db.flush() # get id
        
        # Classification
        clas = ClasificacionIncidente(
            incidente_id=incidente.id,
            categoria=cat,
            severidad=sev,
            confianza=0.9,
            metodo="reglas",
            clasificado_en=creado + timedelta(seconds=10)
        )
        db.add(clas)
        
        # Assignment if applicable
        if estado in ["finalizado", "taller_asignado"]:
            taller = random.choice(workshops)
            asignado_en = creado + timedelta(minutes=random.randint(5, 30))
            asig = Asignacion(
                incidente_id=incidente.id,
                taller_id=taller.id,
                distancia_km=random.uniform(0.5, 5.0),
                puntaje=random.uniform(80, 100),
                asignado_en=asignado_en
            )
            db.add(asig)
            
            if estado == "finalizado":
                # Create a Cotizacion to test SLA
                cot = Cotizacion(
                    incidente_id=incidente.id,
                    tenant_id=tenant_id,
                    estado="aceptada",
                    tiempo_estimado_dias=random.randint(1, 3),
                    subtotal=100.0,
                    iva=16.0,
                    total=116.0,
                    creado_en=asignado_en + timedelta(minutes=10)
                )
                db.add(cot)
                # Fix Incident date for Resolution time
                # To simulate taking some time to resolve
                incidente.actualizado_en = asignado_en + timedelta(days=random.randint(0, 2), hours=random.randint(1, 10))
                
    db.commit()
    print("--- 30 Incidents Seeded Successfully! ---")

if __name__ == "__main__":
    import sys
    tenant_id = 6
    if len(sys.argv) > 1:
        tenant_id = int(sys.argv[1])
    seed_dashboard(tenant_id)
