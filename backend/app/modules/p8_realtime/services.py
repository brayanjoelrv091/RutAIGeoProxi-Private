"""
P8 — Servicios de Conectividad Resiliente y Tiempo Real.

Servicios:
    OfflineSyncService     → CU-21, CU-22, CU-23
    RealtimeStateService   → CU-25
    TrackingService        → CU-26
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.modules.p2_incidentes.models import Incidente
from app.modules.p8_realtime.models import EventoEstado, TrackingGPS
from app.modules.p8_realtime.schemas import (
    OfflineIncidentPayload,
    OfflineSyncItemResult,
    OfflineSyncResponse,
    SyncStatus,
    StateChangeResponse,
    TrackingGPSPayload,
)
from app.modules.p8_realtime.state_machine import IncidentStateMachine

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# CU-21, CU-22, CU-23 — Sincronización Offline
# ═══════════════════════════════════════════════════════════════════════


class OfflineSyncService:
    """
    Procesa la cola de incidentes registrados offline.

    Flujo:
        1. Recibe batch de incidentes con idempotency_keys
        2. Para cada item, verifica si ya existe (deduplicación CU-23)
        3. Si es nuevo, lo crea en BD
        4. Retorna resultado individual por item
    """

    @staticmethod
    async def sync_batch(
        db: Session,
        user_id: int,
        items: list[OfflineIncidentPayload],
    ) -> OfflineSyncResponse:
        """
        Sincroniza un batch de incidentes offline.

        La deduplicación se basa en el campo `idempotency_key` que es
        un UUID generado por el dispositivo al momento de crear el
        incidente offline. Si ya existe un incidente con esa key,
        se retorna como duplicado sin crear uno nuevo.
        """
        results: list[OfflineSyncItemResult] = []
        created_count = 0
        duplicate_count = 0
        error_count = 0

        for item in items:
            try:
                result = await OfflineSyncService._process_item(db, user_id, item)
                results.append(result)

                if result.status == SyncStatus.CREATED:
                    created_count += 1
                elif result.status == SyncStatus.DUPLICATE:
                    duplicate_count += 1
                else:
                    error_count += 1

            except Exception as exc:
                logger.error(
                    f"Error sincronizando item {item.idempotency_key}: {exc}",
                    exc_info=True,
                )
                results.append(
                    OfflineSyncItemResult(
                        idempotency_key=item.idempotency_key,
                        status=SyncStatus.ERROR,
                        message=f"Error interno: {str(exc)[:200]}",
                    )
                )
                error_count += 1

        return OfflineSyncResponse(
            total=len(items),
            created=created_count,
            duplicates=duplicate_count,
            errors=error_count,
            results=results,
        )

    @staticmethod
    async def _process_item(
        db: Session,
        user_id: int,
        item: OfflineIncidentPayload,
    ) -> OfflineSyncItemResult:
        """Procesa un ítem individual con deduplicación."""

        # ── CU-23: Deduplicación por idempotency_key ──
        existing = (
            db.query(Incidente)
            .filter(Incidente.idempotency_key == item.idempotency_key)
            .first()
        )

        if existing:
            logger.info(
                f"Duplicado detectado: idempotency_key={item.idempotency_key}, "
                f"incidente_id={existing.id}"
            )
            return OfflineSyncItemResult(
                idempotency_key=item.idempotency_key,
                status=SyncStatus.DUPLICATE,
                incident_id=existing.id,
                message=f"Incidente ya existe (ID: {existing.id}). No se creó duplicado.",
            )

        # ── Crear nuevo incidente ──
        incidente = Incidente(
            usuario_id=user_id,
            titulo=item.titulo,
            descripcion=item.descripcion,
            latitud=item.latitud,
            longitud=item.longitud,
            direccion=item.direccion,
            estado="pendiente",
            idempotency_key=item.idempotency_key,
        )
        db.add(incidente)
        db.flush()  # Para obtener el ID antes del commit

        # ── Registrar evento de creación ──
        evento = EventoEstado(
            incidente_id=incidente.id,
            estado_anterior="sin_estado",
            estado_nuevo="pendiente",
            actor_id=user_id,
            actor_rol="cliente",
            notas=f"Creado desde modo offline (sync). Key: {item.idempotency_key}",
        )
        db.add(evento)
        db.commit()
        db.refresh(incidente)

        logger.info(
            f"Incidente creado desde offline: id={incidente.id}, "
            f"key={item.idempotency_key}"
        )

        # ── Notificar a los talleres (Simulando push/WS) ──
        try:
            from app.modules.p3_talleres.models import Taller, SolicitudServicio
            from app.shared.websockets import manager
            from app.modules.p1_usuarios.models import Usuario

            # Buscar tenant del cliente
            client = db.query(Usuario).filter(Usuario.id == user_id).first()
            tenant_id = client.tenant_id if client else None

            if tenant_id:
                talleres = db.query(Taller).filter(Taller.tenant_id == tenant_id, Taller.esta_activo == True).all()
            else:
                talleres = db.query(Taller).filter(Taller.esta_activo == True).all()

            ws_payload = {
                "type": "nuevo_incidente",
                "incidente_id": incidente.id,
                "titulo": "¡Nuevo Incidente Reportado (Offline Sync)!",
                "mensaje": f"Un cliente necesita asistencia: {incidente.titulo}"
            }

            for t in talleres:
                solicitud = SolicitudServicio(
                    incidente_id=incidente.id,
                    taller_id=t.id,
                    estado="pendiente",
                    notas="Incidente sincronizado, esperando aceptación."
                )
                db.add(solicitud)
                await manager.send_personal_message(ws_payload, str(t.usuario_propietario_id))
            
            db.commit()
        except Exception as notify_err:
            logger.error(f"Error notificando a talleres sobre incidente offline {incidente.id}: {notify_err}")

        return OfflineSyncItemResult(
            idempotency_key=item.idempotency_key,
            status=SyncStatus.CREATED,
            incident_id=incidente.id,
            message="Incidente creado exitosamente desde cola offline.",
        )


# ═══════════════════════════════════════════════════════════════════════
# CU-25 — Gestión de Estado en Tiempo Real
# ═══════════════════════════════════════════════════════════════════════


class RealtimeStateService:
    """
    Gestiona transiciones de estado validadas por la máquina de estados.

    Cada transición:
        1. Valida contra IncidentStateMachine
        2. Actualiza el incidente en BD
        3. Registra evento en tabla evento_estados
        4. Emite notificación WebSocket (delegado al caller)
    """

    @staticmethod
    def transition_state(
        db: Session,
        incident_id: int,
        new_state: str,
        actor_id: int,
        actor_rol: str,
        notas: Optional[str] = None,
    ) -> StateChangeResponse:
        """
        Ejecuta una transición de estado validada.

        Raises:
            ValueError: Si el incidente no existe o el estado es inválido.
            PermissionError: Si la transición no está permitida.
        """
        incidente = db.query(Incidente).filter(Incidente.id == incident_id).first()
        if not incidente:
            raise ValueError(f"Incidente {incident_id} no encontrado.")

        old_state = incidente.estado

        # ── Validar transición con la máquina de estados ──
        IncidentStateMachine.validate_transition(old_state, new_state)

        # ── Actualizar estado del incidente ──
        incidente.estado = new_state
        incidente.actualizado_en = datetime.now(timezone.utc)

        # ── Registrar evento de transición ──
        evento = EventoEstado(
            incidente_id=incident_id,
            estado_anterior=old_state,
            estado_nuevo=new_state,
            actor_id=actor_id,
            actor_rol=actor_rol,
            notas=notas,
        )
        db.add(evento)
        db.commit()
        db.refresh(incidente)

        logger.info(
            f"Transición de estado: incidente={incident_id}, "
            f"{old_state} → {new_state}, actor={actor_id} ({actor_rol})"
        )

        return StateChangeResponse(
            incidente_id=incident_id,
            estado_anterior=old_state,
            estado_nuevo=new_state,
            label=IncidentStateMachine.get_label(new_state),
            actor_id=actor_id,
            actor_rol=actor_rol,
            transiciones_disponibles=IncidentStateMachine.get_allowed_transitions(new_state),
            timestamp=datetime.now(timezone.utc),
        )

    @staticmethod
    def get_timeline(db: Session, incident_id: int) -> list[EventoEstado]:
        """Obtiene el historial completo de transiciones de un incidente."""
        incidente = db.query(Incidente).filter(Incidente.id == incident_id).first()
        if not incidente:
            raise ValueError(f"Incidente {incident_id} no encontrado.")

        return (
            db.query(EventoEstado)
            .filter(EventoEstado.incidente_id == incident_id)
            .order_by(EventoEstado.creado_en.asc())
            .all()
        )


# ═══════════════════════════════════════════════════════════════════════
# CU-26 — Tracking GPS en Vivo
# ═══════════════════════════════════════════════════════════════════════


class TrackingService:
    """
    Persiste puntos GPS y proporciona historial de tracking.
    La transmisión en tiempo real se hace vía WebSocket en las routes.
    """

    @staticmethod
    def record_position(
        db: Session,
        incident_id: int,
        user_id: int,
        rol: str,
        payload: TrackingGPSPayload,
    ) -> TrackingGPS:
        """Registra un punto GPS en la base de datos."""
        point = TrackingGPS(
            incidente_id=incident_id,
            usuario_id=user_id,
            rol=rol,
            latitud=payload.latitud,
            longitud=payload.longitud,
            precision_m=payload.precision_m,
            velocidad_kmh=payload.velocidad_kmh,
            heading=payload.heading,
        )
        db.add(point)
        db.commit()
        db.refresh(point)
        return point

    @staticmethod
    def get_history(
        db: Session,
        incident_id: int,
        limit: int = 100,
    ) -> list[TrackingGPS]:
        """Obtiene las últimas N posiciones GPS de un incidente."""
        return (
            db.query(TrackingGPS)
            .filter(TrackingGPS.incidente_id == incident_id)
            .order_by(TrackingGPS.registrado_en.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_latest_position(
        db: Session,
        incident_id: int,
        rol: str = "tecnico",
    ) -> Optional[TrackingGPS]:
        """Obtiene la última posición conocida de un rol específico."""
        return (
            db.query(TrackingGPS)
            .filter(
                TrackingGPS.incidente_id == incident_id,
                TrackingGPS.rol == rol,
            )
            .order_by(TrackingGPS.registrado_en.desc())
            .first()
        )
