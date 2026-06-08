import os
import sys
from datetime import datetime, timezone, timedelta
from decimal import Decimal

# Añadir el path raíz para importaciones de la app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.shared.database import SessionLocal, Base, engine
from app.shared.context import is_superadmin

# Importar todos los modelos para asegurar que Base conozca las tablas
from app.modules.p1_usuarios.models import Usuario, Vehiculo
from app.modules.p2_incidentes.models import Incidente, ClasificacionIncidente
from app.modules.p3_talleres.models import Taller, Tecnico
from app.modules.p4_asignacion.models import Asignacion
from app.modules.p5_pagos.models import Pago
from app.modules.p7_seguridad_multitenant.models import Tenant, TenantMembership
from app.modules.p8_realtime.models import EventoEstado, TrackingGPS
from app.modules.p9_analitica.models import Cotizacion, CotizacionItem

def get_password_hash(password: str) -> str:
    # Usar un hash precomputado para "12345678" para evitar el crash de passlib/bcrypt en py3.13
    return "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjIQG8INj6"

def seed_database():
    print("[1/6] Recreando la base de datos (Drop & Create)...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    # Habilitar modo superadmin para bypass de Row-Level Security
    is_superadmin.set(True)
    db = SessionLocal()
    
    try:
        print("[2/6] Creando Superadmin y Tenant...")
        
        # 1. Superadmin
        superadmin = Usuario(
            nombre="Super Admin",
            email="superadmin@rutai.com",
            hashed_password=get_password_hash("12345678"),
            rol="superadmin",
            esta_activo=True
        )
        db.add(superadmin)
        db.flush()
        
        # 2. Tenant
        tenant = Tenant(
            nombre="Red Talleres Bolivianos",
            slug="red-talleres-bolivia",
            esta_activo=True,
            plan="profesional"
        )
        db.add(tenant)
        db.flush()
        
        # 3. Admin del Tenant
        admin_tenant = Usuario(
            tenant_id=tenant.id,
            nombre="Admin Red Boliviana",
            email="admin@rutai.com",
            hashed_password=get_password_hash("12345678"),
            rol="admin",
            esta_activo=True
        )
        db.add(admin_tenant)
        db.flush()
        
        membership = TenantMembership(
            usuario_id=admin_tenant.id,
            tenant_id=tenant.id,
            rol_en_tenant="owner"
        )
        db.add(membership)
        
        print("[3/6] Creando Talleres y Tecnicos...")
        
        talleres_data = [
            {"nombre": "Taller SCZ Centro", "lat": -17.7833, "lng": -63.1821, "esp": "general"},
            {"nombre": "MotorTech Norte", "lat": -17.7600, "lng": -63.1700, "esp": "mecanico"},
            {"nombre": "ElectricCar Sur", "lat": -17.8100, "lng": -63.1800, "esp": "electrico"}
        ]
        
        talleres = []
        for index, t_data in enumerate(talleres_data):
            # Usuario Taller (propietario)
            user_taller = Usuario(
                tenant_id=tenant.id,
                nombre=f"Propietario {t_data['nombre']}",
                email=f"taller{index+1}@rutai.com",
                hashed_password=get_password_hash("12345678"),
                rol="taller",
                esta_activo=True
            )
            db.add(user_taller)
            db.flush()
            
            # Entidad Taller
            taller = Taller(
                tenant_id=tenant.id,
                usuario_propietario_id=user_taller.id,
                nombre=t_data['nombre'],
                direccion=f"Av. Principal {index*100}",
                latitud=t_data['lat'],
                longitud=t_data['lng'],
                especialidades={"principal": t_data['esp']},
                esta_activo=True,
                ultimo_heartbeat=datetime.now(timezone.utc)
            )
            db.add(taller)
            db.flush()
            talleres.append(taller)
            
            tecnico = Tecnico(
                taller_id=taller.id,
                nombre=f"Tecnico {index+1}",
                telefono=f"777000{index}",
                especialidad=t_data['esp'],
                esta_disponible=True
            )
            db.add(tecnico)
        
        print("[4/6] Creando Cliente y Vehiculo...")
        
        cliente = Usuario(
            tenant_id=tenant.id,
            nombre="Juan Perez (Cliente)",
            email="cliente@rutai.com",
            hashed_password=get_password_hash("12345678"),
            rol="cliente",
            esta_activo=True
        )
        db.add(cliente)
        db.flush()
        
        vehiculo = Vehiculo(
            usuario_id=cliente.id,
            marca="Toyota",
            modelo="Corolla",
            placa="1234ABC",
            anio=2020,
            color="Blanco"
        )
        db.add(vehiculo)
        
        print("[5/6] Creando Incidentes en varios estados (Timeline & GPS)...")
        
        # Incidente 1: Pendiente
        inc1 = Incidente(
            tenant_id=tenant.id,
            usuario_id=cliente.id,
            titulo="Falla de bateria",
            descripcion="El auto no arranca, parece bateria muerta",
            estado="pendiente",
            latitud=-17.7850,
            longitud=-63.1810,
            severidad="leve",
            categoria="electrico"
        )
        db.add(inc1)
        
        # Incidente 2: Taller Asignado
        inc2 = Incidente(
            tenant_id=tenant.id,
            usuario_id=cliente.id,
            titulo="Llanta pinchada",
            estado="taller_asignado",
            latitud=-17.7880,
            longitud=-63.1850,
            severidad="leve",
            categoria="general"
        )
        db.add(inc2)
        db.flush()
        
        Asignacion(
            incidente_id=inc2.id,
            taller_id=talleres[0].id,
            distancia_km=1.2,
            puntaje=95.5
        )
        db.add(EventoEstado(incidente_id=inc2.id, estado_anterior="pendiente", estado_nuevo="buscando_taller", actor_rol="sistema"))
        db.add(EventoEstado(incidente_id=inc2.id, estado_anterior="buscando_taller", estado_nuevo="taller_asignado", actor_rol="taller", actor_id=talleres[0].usuario_propietario_id, notas="Taller Centro acepto el servicio"))
        
        # Incidente 3: En Camino (Con GPS Tracking)
        inc3 = Incidente(
            tenant_id=tenant.id,
            usuario_id=cliente.id,
            titulo="Recalentamiento Motor",
            estado="en_camino",
            latitud=-17.7650,
            longitud=-63.1750,
            severidad="grave",
            categoria="mecanico"
        )
        db.add(inc3)
        db.flush()
        Asignacion(incidente_id=inc3.id, taller_id=talleres[1].id, distancia_km=2.5, puntaje=88.0)
        
        # Puntos de tracking falsos para inc3
        for i in range(5):
            db.add(TrackingGPS(
                incidente_id=inc3.id,
                usuario_id=tecnico.id,
                rol="tecnico",
                latitud=-17.7600 - (0.001 * i),
                longitud=-63.1700 - (0.001 * i),
                velocidad_kmh=40.0 + i,
                heading=180.0
            ))
            
        # Incidente 4: En Atencion (Con Cotizacion)
        inc4 = Incidente(
            tenant_id=tenant.id,
            usuario_id=cliente.id,
            titulo="Choque frontal leve",
            estado="en_atencion",
            latitud=-17.7900,
            longitud=-63.1900,
            severidad="moderado",
            categoria="carroceria",
            tiempo_estimado_reparacion_minutos=120
        )
        db.add(inc4)
        db.flush()
        Asignacion(incidente_id=inc4.id, taller_id=talleres[0].id, distancia_km=0.8, puntaje=99.0)
        
        cotizacion = Cotizacion(
            incidente_id=inc4.id,
            tenant_id=tenant.id,
            subtotal=Decimal('100.00'),
            iva=Decimal('16.00'),
            total=Decimal('116.00'),
            estado="enviada",
            tiempo_estimado_dias=2,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1)
        )
        db.add(cotizacion)
        db.flush()
        
        db.add(CotizacionItem(cotizacion_id=cotizacion.id, descripcion="Cambio de parachoques", cantidad=1, precio_unitario=Decimal('50.00')))
        db.add(CotizacionItem(cotizacion_id=cotizacion.id, descripcion="Pintura y mano de obra", cantidad=1, precio_unitario=Decimal('50.00')))
        
        # Incidente 5: Finalizado (Con Pago)
        inc5 = Incidente(
            tenant_id=tenant.id,
            usuario_id=cliente.id,
            titulo="Cambio de aceite a domicilio",
            estado="finalizado",
            latitud=-17.7830,
            longitud=-63.1820,
            severidad="leve",
            categoria="mecanico"
        )
        db.add(inc5)
        db.flush()
        Asignacion(incidente_id=inc5.id, taller_id=talleres[0].id, distancia_km=0.5, puntaje=90.0)
        
        pago = Pago(
            tenant_id=tenant.id,
            incidente_id=inc5.id,
            monto=Decimal('35.00'),
            comision_plataforma=Decimal('3.50'),
            moneda="USD",
            metodo_pago="tarjeta_mobile",
            estado="completado",
            stripe_checkout_session_id="cs_test_mock_123456",
            transaccion_id="pi_test_mock_123456"
        )
        db.add(pago)

        db.commit()
        print("[6/6] Poblado de base de datos exitoso!")
        print("-" * 50)
        print("Credenciales de prueba generadas (Contraseña para todos: 12345678):")
        print("Superadmin: superadmin@rutai.com")
        print("Admin: admin@rutai.com")
        print("Cliente: cliente@rutai.com")
        print("Talleres:")
        print(" - taller1@rutai.com")
        print(" - taller2@rutai.com")
        print(" - taller3@rutai.com")
        print("-" * 50)
        
    except Exception as e:
        db.rollback()
        print(f"Error durante el seed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
        is_superadmin.set(False)

if __name__ == "__main__":
    seed_database()
