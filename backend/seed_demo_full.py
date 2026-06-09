# -*- coding: utf-8 -*-
"""
Seed integral para demo del tribunal -- RutAIGeoProxi.

Crea un escenario completo y realista:
  - 1 admin, 2 clientes, 2 talleres con técnicos
  - Vehículos registrados para los clientes
  - 4 incidentes en distintos estados y clasificaciones
  - Asignaciones de taller
  - Solicitudes de servicio con estados variados
  - 1 pago completado

Es idempotente: se puede re-ejecutar sin duplicar datos.

Uso:
    cd backend
    python seed_demo_full.py
"""

import os
import sys

# Fix encoding para consolas Windows (cp1252) — evita UnicodeEncodeError con tildes/flechas
if hasattr(sys.stdout, 'buffer') and (sys.stdout.encoding or '').upper() not in ('UTF-8', 'UTF8'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv

directorio_actual = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, directorio_actual)
load_dotenv(os.path.join(directorio_actual, ".env"))

from sqlalchemy.orm import Session  # noqa: E402

from app.shared.database import SessionLocal, engine, Base  # noqa: E402
from app.shared.security import get_password_hash  # noqa: E402
from app.modules.p1_usuarios.models import Usuario, Vehiculo  # noqa: E402
from app.modules.p2_incidentes.models import (  # noqa: E402
    Incidente,
    ClasificacionIncidente,
)
from app.modules.p3_talleres.models import (  # noqa: E402
    Taller,
    Tecnico,
    SolicitudServicio,
)
from app.modules.p4_asignacion.models import Asignacion  # noqa: E402
from app.modules.p5_pagos.models import Pago, Notificacion  # noqa: E402



# ── Helpers ────────────────────────────────────────────────────────────────

def get_or_create_user(db: Session, email: str, nombre: str, rol: str, password: str) -> Usuario:
    u = db.query(Usuario).filter(Usuario.email == email).first()
    if not u:
        u = Usuario(
            nombre=nombre,
            email=email,
            hashed_password=get_password_hash(password),
            rol=rol,
            esta_activo=True,
            intentos_fallidos=0,
        )
        db.add(u)
        db.flush()
        print(f"  [OK] Usuario creado: {email} [{rol}]")
    else:
        print(f"  [SKIP]  Usuario ya existe: {email}")
    return u


def get_or_create_vehicle(db: Session, usuario_id: int, placa: str, **kwargs) -> Vehiculo:
    v = db.query(Vehiculo).filter(Vehiculo.placa == placa).first()
    if not v:
        v = Vehiculo(usuario_id=usuario_id, placa=placa, **kwargs)
        db.add(v)
        db.flush()
        print(f"  [OK] Vehículo creado: {placa}")
    return v


def get_or_create_workshop(db: Session, nombre: str, propietario_id: int, **kwargs) -> Taller:
    t = db.query(Taller).filter(Taller.nombre == nombre).first()
    if not t:
        t = Taller(nombre=nombre, usuario_propietario_id=propietario_id, **kwargs)
        db.add(t)
        db.flush()
        print(f"  [OK] Taller creado: {nombre}")
    else:
        print(f"  [SKIP]  Taller ya existe: {nombre}")
    return t


def get_or_create_technician(db: Session, taller_id: int, nombre: str, **kwargs) -> Tecnico:
    t = db.query(Tecnico).filter(
        Tecnico.taller_id == taller_id, Tecnico.nombre == nombre
    ).first()
    if not t:
        t = Tecnico(taller_id=taller_id, nombre=nombre, **kwargs)
        db.add(t)
        db.flush()
        print(f"  [OK] Técnico creado: {nombre}")
    return t


def get_or_create_incident(db: Session, usuario_id: int, titulo: str, **kwargs) -> Incidente:
    i = db.query(Incidente).filter(
        Incidente.usuario_id == usuario_id, Incidente.titulo == titulo
    ).first()
    if not i:
        i = Incidente(usuario_id=usuario_id, titulo=titulo, **kwargs)
        db.add(i)
        db.flush()
        print(f"  [OK] Incidente creado: '{titulo}'")
    else:
        print(f"  [SKIP]  Incidente ya existe: '{titulo}'")
    return i


# ── Seed principal ─────────────────────────────────────────────────────────

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        print("\n[PKG] SEED INTEGRAL — RutAIGeoProxi Demo Tribunal")
        print("=" * 55)

        # ── Usuarios ──────────────────────────────────────────────────
        print("\n[USER] Usuarios:")
        get_or_create_user(db, "admin@ruta.com", "Super Admin Demo", "admin", "Password123")
        cliente1 = get_or_create_user(db, "cliente@ruta.com", "Carlos Mendoza", "cliente", "Password123")
        cliente2 = get_or_create_user(db, "cliente2@ruta.com", "Ana Torres", "cliente", "Password123")
        taller_u1 = get_or_create_user(db, "taller@ruta.com", "Taller Mecánico Centro", "taller", "Password123")
        taller_u2 = get_or_create_user(db, "taller2@ruta.com", "AutoServicios Norte", "taller", "Password123")
        db.commit()

        # ── Vehículos ─────────────────────────────────────────────────
        print("\n[CAR] Vehículos:")
        get_or_create_vehicle(db, cliente1.id, "ABC-123", marca="Toyota", modelo="Corolla", anio=2019, color="Blanco")
        get_or_create_vehicle(db, cliente1.id, "XYZ-789", marca="Chevrolet", modelo="Spark", anio=2021, color="Rojo")
        get_or_create_vehicle(db, cliente2.id, "DEF-456", marca="Kia", modelo="Rio", anio=2020, color="Gris")
        db.commit()

        # ── Talleres ──────────────────────────────────────────────────
        print("\n[TOOL] Talleres:")
        taller1 = get_or_create_workshop(
            db, "Taller Mecánico Centro", taller_u1.id,
            direccion="Av. Libertador 1234, Santiago",
            latitud=-33.4560, longitud=-70.6480,
            telefono="+56912345678",
            email="taller@ruta.com",
            especialidades=["mecanico", "electrico", "neumaticos"],
            esta_activo=True,
            estado_registro="completado",
        )
        taller2 = get_or_create_workshop(
            db, "AutoServicios Norte", taller_u2.id,
            direccion="Calle Las Rosas 890, Providencia",
            latitud=-33.4350, longitud=-70.6250,
            telefono="+56987654321",
            email="taller2@ruta.com",
            especialidades=["carroceria", "mecanico", "emergencia_vial"],
            esta_activo=True,
            estado_registro="completado",
        )
        db.commit()

        # ── Técnicos ──────────────────────────────────────────────────
        print("\n[TECH] Técnicos:")
        tec1 = get_or_create_technician(
            db, taller1.id, "Juan Pérez",
            especialidad="mecanico", esta_disponible=True,
            latitud=-33.4560, longitud=-70.6480,
        )
        tec2 = get_or_create_technician(
            db, taller1.id, "Pedro Soto",
            especialidad="electrico", esta_disponible=True,
            latitud=-33.4562, longitud=-70.6485,
        )
        tec3 = get_or_create_technician(
            db, taller2.id, "María López",
            especialidad="carroceria", esta_disponible=True,
            latitud=-33.4350, longitud=-70.6250,
        )
        db.commit()

        # ── Incidentes ────────────────────────────────────────────────
        print("\n[WARN]  Incidentes:")

        # Incidente 1: nuevo (sin clasificar)
        get_or_create_incident(
            db, cliente1.id,
            "Falla de frenos en Av. Principal",
            descripcion="Pedal de freno blando, posible fuga de líquido de frenos.",
            estado="nuevo",
            latitud=-33.4500, longitud=-70.6600,
            direccion="Av. Principal 500, Santiago",
        )

        # Incidente 2: clasificado con IA
        inc2 = get_or_create_incident(
            db, cliente1.id,
            "Motor recalentado en autopista",
            descripcion="Temperatura del motor subió al máximo, vapor saliendo del capó.",
            estado="clasificado",
            latitud=-33.4400, longitud=-70.6300,
            direccion="Autopista Central km 23",
            severidad="grave",
            categoria="mecanico",
        )

        # Incidente 3: asignado a taller
        inc3 = get_or_create_incident(
            db, cliente2.id,
            "Batería descargada — vehículo sin arranque",
            descripcion="El auto no arranca, posiblemente batería agotada.",
            estado="asignado",
            latitud=-33.4350, longitud=-70.6200,
            direccion="Calle Los Cerezos 45",
            severidad="moderado",
            categoria="electrico",
        )

        # Incidente 4: resuelto y pagado
        inc4 = get_or_create_incident(
            db, cliente2.id,
            "Cambio de neumático pinchado",
            descripcion="Neumático trasero derecho pinchado completamente.",
            estado="resuelto",
            latitud=-33.4600, longitud=-70.6700,
            direccion="Ruta 68 km 10",
            severidad="leve",
            categoria="neumaticos",
        )
        db.commit()

        # ── Clasificaciones ───────────────────────────────────────────
        print("\n[AI] Clasificaciones IA:")
        for inc, cat, sev, conf in [
            (inc2, "mecanico", "grave", 0.92),
            (inc3, "electrico", "moderado", 0.88),
            (inc4, "neumaticos", "leve", 0.95),
        ]:
            existing = db.query(ClasificacionIncidente).filter(
                ClasificacionIncidente.incidente_id == inc.id
            ).first()
            if not existing:
                db.add(ClasificacionIncidente(
                    incidente_id=inc.id,
                    categoria=cat,
                    severidad=sev,
                    confianza=conf,
                    metodo="reglas",
                    razonamiento=f"Clasificado automáticamente como {cat} ({sev}) con confianza {conf:.0%}",
                ))
                print(f"  [OK] Clasificación: incidente #{inc.id} → {cat} / {sev}")

        db.commit()

        # ── Asignaciones ──────────────────────────────────────────────
        print("\n[PIN] Asignaciones:")
        for inc, taller, distancia in [
            (inc3, taller1, 2.3),
            (inc4, taller2, 5.1),
        ]:
            existing = db.query(Asignacion).filter(
                Asignacion.incidente_id == inc.id
            ).first()
            if not existing:
                db.add(Asignacion(
                    incidente_id=inc.id,
                    taller_id=taller.id,
                    distancia_km=distancia,
                    puntaje=round(100 - distancia * 5, 1),
                ))
                print(f"  [OK] Asignación: incidente #{inc.id} → taller #{taller.id} ({distancia} km)")

        db.commit()

        # ── Solicitudes de servicio ───────────────────────────────────
        print("\n[LIST] Solicitudes de servicio:")
        for inc, taller, tec, estado, notas in [
            (inc2, taller1, tec1.id, "proceso", "Diagnóstico inicial: termostato defectuoso."),
            (inc3, taller1, tec2.id, "pendiente", None),
            (inc4, taller2, tec3.id, "atendido", "Neumático reemplazado exitosamente."),
        ]:
            existing = db.query(SolicitudServicio).filter(
                SolicitudServicio.incidente_id == inc.id,
                SolicitudServicio.taller_id == taller.id,
            ).first()
            if not existing:
                db.add(SolicitudServicio(
                    incidente_id=inc.id,
                    taller_id=taller.id,
                    tecnico_id=tec,
                    estado=estado,
                    notas=notas,
                ))
                print(f"  [OK] Solicitud: incidente #{inc.id} → {estado}")

        db.commit()

        # ── Pago ──────────────────────────────────────────────────────
        print("\n[CARD] Pagos:")
        existing_pago = db.query(Pago).filter(Pago.incidente_id == inc4.id).first()
        if not existing_pago:
            db.add(Pago(
                incidente_id=inc4.id,
                monto=45000.0,
                comision_plataforma=4500.0,
                moneda="CLP",
                metodo_pago="tarjeta",
                estado="completado",
                transaccion_id="TXN-DEMO0001",
            ))
            db.add(Notificacion(
                usuario_id=cliente2.id,
                titulo="Pago aprobado",
                mensaje=f"Se procesó el pago del incidente #{inc4.id} por 45000.00 CLP.",
                tipo="push",
            ))
            print(f"  [OK] Pago demo: incidente #{inc4.id} → TXN-DEMO0001")

        db.commit()

        # ── Resumen ───────────────────────────────────────────────────
        print("\n" + "=" * 55)
        print("[OK] SEED COMPLETADO — Sistema listo para demo del tribunal")
        print("=" * 55)
        print("\nCredenciales de acceso:")
        print("  [ADMIN] Admin   : admin@ruta.com / Password123")
        print("  [TOOL] Taller1 : taller@ruta.com / Password123")
        print("  [TOOL] Taller2 : taller2@ruta.com / Password123")
        print("  [USER] Cliente1: cliente@ruta.com / Password123")
        print("  [USER] Cliente2: cliente2@ruta.com / Password123")
        print("\nFlujo sugerido para demo:")
        print("  1. [WEB] Login Admin → ver incidentes → asignar taller #1 (inc1)")
        print("  2. [WEB] Login Taller → ver solicitudes → cambiar estado pendiente→proceso")
        print("  3. [APP] Login Cliente (Flutter) → ver mis incidentes → ir a pago (inc3)")
        print("  4. [WEB] Verificar notificación WS tras pago en el panel web")
        print("  5. [WEB] Admin → exportar reporte PDF/Excel")

    except Exception as e:
        print(f"\n[ERR] Error durante el seed: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
