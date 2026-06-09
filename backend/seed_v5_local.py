# -*- coding: utf-8 -*-
import os
import sys

# Imports del proyecto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.shared.database import SessionLocal, Base, engine
from app.shared.security import get_password_hash
from app.modules.p1_usuarios.models import Usuario, Vehiculo
from app.modules.p2_incidentes.models import Incidente, ClasificacionIncidente
from app.modules.p3_talleres.models import Taller, Tecnico, SolicitudServicio
from app.modules.p4_asignacion.models import Asignacion
from app.modules.p5_pagos.models import Pago, Notificacion
from app.modules.p7_seguridad_multitenant.models import Tenant, TenantMembership

def seed_v5_local():
    db = SessionLocal()
    try:
        print("\n[START] INICIANDO SEED LOCAL V5 (MULTITENANT & PAGOS)...")

        pw = "Password123"
        hashed = get_password_hash(pw)

        # 1. Crear Organización (Tenant)
        print("[1] Creando Tenant (Franquicia El Rayo)...")
        tenant = Tenant(nombre="Franquicia El Rayo", slug="franquicia-rayo", plan="premium")
        db.add(tenant)
        db.flush()

        # 2. Crear los 3 usuarios oficiales
        print("[2] Creando los 3 usuarios oficiales...")
        admin = Usuario(nombre="Admin Carlos", email="xdreicarlos@gmail.com", hashed_password=hashed, rol="admin", esta_activo=True)
        taller_u = Usuario(nombre="Dueño El Rayo", email="fitgo61@gmail.com", hashed_password=hashed, rol="taller", esta_activo=True, tenant_id=tenant.id)
        cliente = Usuario(nombre="Brayan Ramos", email="ramosvargabrayan@gmail.com", hashed_password=hashed, rol="cliente", esta_activo=True)
        db.add_all([admin, taller_u, cliente])
        db.flush()

        # Añadir al dueño del taller al tenant
        db.add(TenantMembership(usuario_id=taller_u.id, tenant_id=tenant.id, rol_en_tenant="owner"))

        # 3. Configurar Taller y Técnico
        print("[3] Configurando Taller y Técnico...")
        taller = Taller(
            usuario_propietario_id=taller_u.id,
            tenant_id=tenant.id,
            nombre="Taller El Rayo (Central)",
            direccion="Av. Busch #123",
            latitud=-17.7833, longitud=-63.1821,
            telefono="+59170011223",
            email="fitgo61@gmail.com",
            especialidades=["mecanico", "electrico"],
            estado_registro="completado"
        )
        db.add(taller)
        db.flush()

        tecnico = Tecnico(
            taller_id=taller.id,
            nombre="Roberto 'Turbo' Ramos",
            especialidad="mecanico",
            latitud=-17.7840, longitud=-63.1830,
            esta_disponible=True
        )
        db.add(tecnico)
        db.flush()

        # 4. Vehículo del Cliente
        v = Vehiculo(usuario_id=cliente.id, marca="Toyota", modelo="Hilux", placa="1234-ABC", anio=2022, color="Blanco")
        db.add(v)
        db.flush()

        # 5. ESCENARIO 1: Incidente para Cotizar (P9) y Pagar (P5)
        print("[4] Creando Escenario: Incidente para Cotizar/Pagar...")
        inc1 = Incidente(
            usuario_id=cliente.id,
            tenant_id=tenant.id,
            titulo="Falla de motor en el 2do Anillo",
            descripcion="El auto se detuvo y no enciende.",
            estado="resuelto",
            latitud=-17.7850, longitud=-63.1850,
            direccion="Avenida Cristobal de Mendoza",
            categoria="mecanico", severidad="grave"
        )
        db.add(inc1)
        db.flush()

        clasif = ClasificacionIncidente(
            incidente_id=inc1.id,
            categoria="mecanico",
            severidad="grave",
            confianza=0.95,
            razonamiento="Falla en sistema de inyección o motor. Sugerencia: Remolcar a taller especializado.",
            metodo="reglas"
        )
        db.add(clasif)
        
        db.add(Asignacion(incidente_id=inc1.id, taller_id=taller.id, distancia_km=0.8, puntaje=98.0, metodo="manual"))
        db.add(SolicitudServicio(
            incidente_id=inc1.id, taller_id=taller.id, tecnico_id=tecnico.id,
            estado="completado", notas="Motor revisado."
        ))

        db.commit()
        print("\n" + "="*60)
        print("DEMO V5 LOCAL LISTA")
        print("="*60)
        print("CREDENTIALS (Pass: Password123):")
        print(f" - ADMIN:  {admin.email}")
        print(f" - TALLER: {taller_u.email}")
        print(f" - CLIENTE: {cliente.email}")
    except Exception as e:
        print(f"[ERR] ERROR: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_v5_local()
