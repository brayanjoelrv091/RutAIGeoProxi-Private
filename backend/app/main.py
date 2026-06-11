"""
RutAIGeoProxi — API Backend (Monolito Modular).

Entry point que registra todos los módulos y configura el servidor.

Arquitectura:
    P1 · Usuarios y Seguridad           (CU1-CU6)    ✅ Implementado
    P2 · Gestión de Incidentes           (CU7-CU9)    ✅ Implementado
    P3 · Gestión de Talleres             (CU10-CU13)  ✅ Implementado
    P4 · Asignación y Logística          (CU14-CU15)  ✅ Implementado
    P5 · Pagos y Notificaciones          (CU16-CU18)  ✅ Implementado
    P6 · Reportes                        (CU19-CU20)  ✅ Implementado
    P7 · Seguridad y Multi-Tenant        (Ciclo 5)    ✅ Implementado
    P8 · Conectividad Resiliente y RT    (CU21-CU26)  ✅ Implementado (Ciclo 4)
    P9 · Analítica Operacional           (Ciclo 5)    ✅ Implementado
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.shared.config import settings
from app.shared.database import Base, SessionLocal, engine
from app.shared.security import get_password_hash

# ── Importar modelos de TODOS los módulos para que SQLAlchemy los registre ──
from app.modules.p1_usuarios.models import (  # noqa: F401
    TokenRecuperacion,
    TokenRevocado,
    Usuario,
    Vehiculo,
)
from app.modules.p2_incidentes.models import (  # noqa: F401
    ClasificacionIncidente,
    Incidente,
    IncidenteMedia,
)
from app.modules.p3_talleres.models import (  # noqa: F401
    SolicitudServicio,
    Taller,
    Tecnico,
)
from app.modules.p4_asignacion.models import Asignacion  # noqa: F401
from app.modules.p5_pagos.models import Pago, Notificacion  # noqa: F401
from app.modules.p6_reportes.models import ReporteGenerado  # noqa: F401
from app.modules.p6_auditoria.models import Bitacora  # noqa: F401
# P7 — Seguridad Multi-Tenant (Ciclo 5)
from app.modules.p7_seguridad_multitenant.models import Tenant, TenantMembership  # noqa: F401
# P8 — Conectividad Resiliente y Tiempo Real (Ciclo 4)
from app.modules.p8_realtime.models import EventoEstado, TrackingGPS  # noqa: F401
# P9 — Analítica y Operaciones (Ciclo 5)
from app.modules.p9_analitica.models import KPISnapshot, Cotizacion, CotizacionItem  # noqa: F401

# ── Importar routers de módulos ──
from app.modules.p1_usuarios.routes import admin_router, auth_router, profile_router
from app.modules.p2_incidentes.routes import router as incidents_router
from app.modules.p2_incidentes.ws_routes import ws_router
from app.modules.p3_talleres.routes import router as workshops_router
from app.modules.p4_asignacion.routes import router as assignments_router
from app.modules.p5_pagos.routes import router as payments_router
from app.modules.p6_reportes.routes import router as reports_router
from app.modules.p6_auditoria.routes import router as audit_router
from app.modules.p7_seguridad_multitenant.routes import router as tenant_router
from app.modules.p7_seguridad_multitenant.saas_routes import router as saas_router
from app.modules.p8_realtime.routes import router as realtime_router
from app.modules.p9_analitica.routes import router as analytics_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# LIFESPAN (startup / shutdown)
# ═══════════════════════════════════════════════════════════════════════


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Crea tablas y seed del admin al iniciar."""
    logger.info("🚀 Creando tablas en la base de datos...")
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Tablas creadas/verificadas")

    # --- PARCHE DE MIGRACIÓN PARA LA TABLA BITACORA ---
    # Removido porque generaba fallos de UndefinedColumn en PostgreSQL al estar sin Isolation Level 
    # autocommit explícito y ya no se usa tenant_secuencia.
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE reportes_generados ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE;"))
            conn.commit()
            logger.info("✅ Columna tenant_id inyectada en reportes.")
    except Exception as e:
        logger.error(f"Error al inyectar columnas multi-tenant: {e}")
        pass
    # ----------------------------------------------------

    # Firebase Admin SDK es opcional — solo para notificaciones push.
    # Si el paquete no está instalado o las credenciales no están configuradas,
    # el servidor sigue funcionando con normalidad.
    try:
        from app.shared.firebase_config import init_firebase
        init_firebase()
    except ModuleNotFoundError:
        logger.warning("⚠️  firebase_admin no instalado — notificaciones push desactivadas.")
    except Exception as e:
        logger.warning(f"⚠️  Firebase no inicializado (no crítico): {e}")

    # Seed del administrador — no crítico: si falla, el servidor sigue en pie.
    if settings.ADMIN_EMAIL and settings.ADMIN_PASSWORD:
        db = SessionLocal()
        try:
            if (
                not db.query(Usuario)
                .filter(Usuario.email == settings.ADMIN_EMAIL)
                .first()
            ):
                db.add(
                    Usuario(
                        nombre="Administrador",
                        email=settings.ADMIN_EMAIL,
                        hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
                        rol="admin",
                        esta_activo=True,
                    )
                )
                db.commit()
                logger.info(f"👤 Admin seed creado: {settings.ADMIN_EMAIL}")
        except Exception as seed_err:
            db.rollback()
            logger.warning(f"⚠️  Admin seed omitido (no crítico): {seed_err}")
        finally:
            db.close()

    # Crear directorio de uploads si no existe
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    yield
    logger.info("🛑 Servidor detenido")


# ═══════════════════════════════════════════════════════════════════════
# APP
# ═══════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="RutAIGeoProxi API",
    description=(
        "Red de Asistencia Técnica Vehicular Inteligente — Monolito Modular. "
        "Ciclo 4: Conectividad Resiliente, WebSockets y Tracking GPS en vivo."
    ),
    version="3.0.0",
    lifespan=lifespan,
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.responses import JSONResponse
from fastapi import Request
import traceback

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_msg = f"{type(exc).__name__}: {str(exc)}"
    tb = traceback.format_exc()
    logger.error(f"Global 500 en {request.url}: {error_msg}\n{tb}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"INTERNAL_ERROR: {error_msg}\nTRACE:\n{tb}"}
    )



# ── Security & Cache Headers ──
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Agrega headers de seguridad y cache recomendados por Lighthouse/webhint."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        # Evitar MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Cache-Control para API responses (no cachear datos dinámicos)
        if "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        # Remover header deprecated que causa warnings
        if "X-XSS-Protection" in response.headers:
            del response.headers["X-XSS-Protection"]
        return response


app.add_middleware(SecurityHeadersMiddleware)

# ── Servir archivos estáticos (uploads locales) ──
if settings.UPLOAD_DIR.exists():
    app.mount(
        "/uploads", StaticFiles(directory=str(settings.UPLOAD_DIR)), name="uploads"
    )

# ── Registrar routers de módulos ──
# P1: Usuarios y Seguridad
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(profile_router)
# P2: Incidentes
app.include_router(incidents_router)
app.include_router(ws_router)
# P3: Talleres
app.include_router(workshops_router)
# P4: Asignación
app.include_router(assignments_router)
# P5: Pagos y Notificaciones
app.include_router(payments_router)
# P6: Reportes y Auditoría
app.include_router(reports_router)
app.include_router(audit_router)
# P7: Seguridad y Multi-Tenant (Ciclo 5)
app.include_router(tenant_router)
app.include_router(saas_router, prefix="/admin/saas")
# P8: Conectividad Resiliente y Tiempo Real (Ciclo 4)
app.include_router(realtime_router)
# P9: Analítica Operacional (Ciclo 5)
app.include_router(analytics_router)


# ── Endpoints de Mantenimiento / Peligrosos (Comentados por seguridad en producción) ──

# @app.get("/api/v1/seed-cloud-full", tags=["Mantenimiento"])
# def seed_cloud_full(): ...

# @app.get("/api/v1/wipe-database-danger-zona", tags=["Mantenimiento"])
# def wipe_database_danger_zona(): ...

# @app.get("/api/v1/patch-taller-db", tags=["Mantenimiento"])
# def patch_taller_db(): ...

# @app.get("/api/v1/patch-saas-db", tags=["Mantenimiento"])
# def patch_saas_db(): ...

# @app.get("/api/v1/test-email", tags=["Mantenimiento"])
# def test_email(...): ...

# @app.get("/api/v1/bootstrap-superadmin", tags=["Mantenimiento"])
# def bootstrap_superadmin(): ...

# @app.get("/api/v1/fix-tenants", tags=["Mantenimiento"])
# def fix_tenants(): ...


@app.get("/", tags=["Sistema"])
@app.head("/", tags=["Sistema"])
def root():
    """Mapa de la API por ciclo y caso de uso."""
    return {
        "api": "RutAIGeoProxi",
        "version": "3.0.0",
        "arquitectura": "Monolito Modular",
        "modulos": {
            "P1_usuarios_seguridad": {
                "estado": "✅ Implementado",
                "CU1_inicio_sesion": "POST /auth/login",
                "CU2_cierre_sesion": "POST /auth/logout",
                "CU3_registro": "POST /auth/register",
                "CU4_recuperar_password": "POST /auth/forgot-password + /auth/reset-password",
                "CU5_roles_permisos": "GET/POST /admin/users, PATCH /admin/users/{id}/role|permissions",
                "CU6_usuario_vehiculo": "GET/PATCH /me, GET/POST/PATCH/DELETE /me/vehicles",
            },
            "P2_incidentes": {
                "estado": "✅ Implementado",
                "CU7_reportar_incidente": "POST /incidents (multipart: fotos+audio+GPS)",
                "CU8_clasificacion_ia": "POST /incidents/{id}/classify (Groq-LLM+Roboflow+Whisper)",
                "CU9_ficha_incidente": "GET /incidents/{id}",
            },
            "P3_talleres": {
                "estado": "✅ Implementado",
                "CU10_registrar_taller": "POST /workshops + POST /workshops/{id}/technicians",
                "CU11_solicitudes": "GET /workshops/{id}/requests",
                "CU12_actualizar_estado": "PATCH /workshops/requests/{id}/status",
                "CU13_historial": "GET /workshops/{id}/history",
            },
            "P4_asignacion": {
                "estado": "✅ Implementado",
                "CU14_asignacion_automatica": "POST /assignments/auto/{incident_id}",
                "CU15_tracking_ws": "WS /assignments/ws/track/{incident_id}",
            },
            "P5_pagos_notificaciones": {
                "estado": "✅ Implementado",
                "CU18_procesar_pago_simulado": "POST /payments/process",
                "CU16_CU17_notificaciones_ws": "WS /payments/ws/notifications/{user_id}",
            },
            "P6_reportes": {
                "estado": "✅ Implementado",
                "CU19_generacion_datos": "Backend logic",
                "CU20_exportar_pdf_excel": "GET /reports/incidents/pdf | excel",
            },
            "P7_seguridad_multitenant": {
                "estado": "✅ Implementado (Ciclo 5)",
                "CU28_CU29_tenants": "GET/POST/PATCH /tenants",
            },
            "P8_conectividad_realtime": {
                "estado": "✅ Implementado (Ciclo 4)",
                "CU21_offline_registro": "POST /realtime/incidents/offline-sync",
                "CU22_sync_cola": "POST /realtime/incidents/offline-sync (batch)",
                "CU23_deduplicacion": "Idempotency key en sync batch",
                "CU24_websocket_bidireccional": "WS /realtime/ws/incidents/{id} + WS /realtime/ws/notifications/{user_id}",
                "CU25_estado_tiempo_real": "PATCH /realtime/incidents/{id}/state + GET /realtime/incidents/{id}/timeline",
                "CU26_tracking_gps": "GET /realtime/incidents/{id}/tracking + WS location_update",
            },
            "P9_analitica_operacional": {
                "estado": "✅ Implementado (Ciclo 5)",
                "CU27_dashboard": "GET /analytics/dashboard",
                "CU30_cotizacion": "POST /analytics/quotations/{incident_id}",
                "CU32_estimacion": "GET /analytics/estimate/{incident_id}",
            },
        },
        "docs": "/docs",
    }
