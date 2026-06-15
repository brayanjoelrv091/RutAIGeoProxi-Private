"""
P8 — Rutas de Conectividad Resiliente y Tiempo Real.

Endpoints REST:
    POST   /realtime/incidents/offline-sync       → CU-21, CU-22 Sync batch offline
    GET    /realtime/incidents/{id}/timeline       → CU-25 Timeline de estados
    PATCH  /realtime/incidents/{id}/state          → CU-25 Cambiar estado
    GET    /realtime/incidents/{id}/tracking       → CU-26 Historial GPS

Endpoints WebSocket:
    WS     /realtime/ws/incidents/{id}             → CU-24, CU-25, CU-26 Canal bidireccional
    WS     /realtime/ws/notifications/{user_id}    → CU-24 Notificaciones en vivo
"""

import json
import logging
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.orm import Session

from app.modules.p1_usuarios.models import Usuario
from app.modules.p2_incidentes.models import Incidente
from app.modules.p8_realtime.schemas import (
    EventoEstadoOut,
    OfflineSyncRequest,
    OfflineSyncResponse,
    StateChangeRequest,
    StateChangeResponse,
    TimelineResponse,
    TrackingGPSPayload,
    TrackingHistoryResponse,
    TrackingPointOut,
)
from app.modules.p8_realtime.services import (
    OfflineSyncService,
    RealtimeStateService,
    TrackingService,
)
from app.modules.p8_realtime.state_machine import IncidentStateMachine
from app.shared.deps import get_current_user, get_db
from app.shared.security import jwt_payload_safe
from app.shared.websocket_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/realtime",
    tags=["P8 · Conectividad Resiliente y Tiempo Real"],
)


# ═══════════════════════════════════════════════════════════════════════
# CU-21, CU-22, CU-23 — Sincronización Offline
# ═══════════════════════════════════════════════════════════════════════


@router.post(
    "/incidents/offline-sync",
    response_model=OfflineSyncResponse,
    status_code=status.HTTP_200_OK,
    summary="CU-21/22/23 · Sincronizar cola de incidentes offline",
)
async def sync_offline_incidents(
    request: OfflineSyncRequest,
    db: Session = Depends(get_db),
    current: Usuario = Depends(get_current_user),
):
    """
    Recibe un batch de incidentes creados offline y los sincroniza.

    Cada ítem incluye un `idempotency_key` para evitar duplicados.
    Los ítems duplicados se reportan con status 'duplicate' pero no causan error.
    """
    return await OfflineSyncService.sync_batch(
        db=db,
        user_id=current.id,
        items=request.items,
    )


# ═══════════════════════════════════════════════════════════════════════
# CU-25 — Estado del Servicio en Tiempo Real
# ═══════════════════════════════════════════════════════════════════════


@router.patch(
    "/incidents/{incident_id}/state",
    response_model=StateChangeResponse,
    summary="CU-25 · Actualizar estado del servicio en tiempo real",
)
async def change_incident_state(
    incident_id: int,
    request: StateChangeRequest,
    db: Session = Depends(get_db),
    current: Usuario = Depends(get_current_user),
):
    """
    Cambia el estado de un incidente validando la máquina de estados.

    Solo permite transiciones válidas. Emite notificación WebSocket
    a todos los suscriptores del incidente.
    """
    try:
        result = RealtimeStateService.transition_state(
            db=db,
            incident_id=incident_id,
            new_state=request.nuevo_estado,
            actor_id=current.id,
            actor_rol=current.rol,
            notas=request.notas,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    # ── Emitir evento WebSocket a suscriptores del incidente ──
    ws_payload = {
        "type": "state_change",
        "incident_id": incident_id,
        "estado_anterior": result.estado_anterior,
        "estado_nuevo": result.estado_nuevo,
        "label": result.label,
        "actor_id": result.actor_id,
        "actor_rol": result.actor_rol,
        "transiciones_disponibles": result.transiciones_disponibles,
        "timestamp": result.timestamp.isoformat(),
    }
    await manager.send_personal_message(ws_payload, f"incident:{incident_id}")

    return result


@router.get(
    "/incidents/{incident_id}/timeline",
    response_model=TimelineResponse,
    summary="CU-25 · Historial de estados (timeline) del incidente",
)
def get_incident_timeline(
    incident_id: int,
    db: Session = Depends(get_db),
    current: Usuario = Depends(get_current_user),
):
    """
    Retorna el historial completo de transiciones de estado de un incidente,
    incluyendo quién hizo cada cambio y cuándo.
    """
    incidente = db.query(Incidente).filter(Incidente.id == incident_id).first()
    if not incidente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incidente {incident_id} no encontrado.",
        )

    eventos = RealtimeStateService.get_timeline(db, incident_id)

    return TimelineResponse(
        incidente_id=incident_id,
        estado_actual=incidente.estado,
        label_actual=IncidentStateMachine.get_label(incidente.estado),
        es_terminal=IncidentStateMachine.is_terminal(incidente.estado),
        transiciones_disponibles=IncidentStateMachine.get_allowed_transitions(
            incidente.estado
        ),
        eventos=[
            EventoEstadoOut(
                id=e.id,
                estado_anterior=e.estado_anterior,
                estado_nuevo=e.estado_nuevo,
                label_anterior=IncidentStateMachine.get_label(e.estado_anterior),
                label_nuevo=IncidentStateMachine.get_label(e.estado_nuevo),
                actor_id=e.actor_id,
                actor_rol=e.actor_rol,
                notas=e.notas,
                creado_en=e.creado_en,
            )
            for e in eventos
        ],
    )


# ═══════════════════════════════════════════════════════════════════════
# CU-26 — Tracking GPS en Vivo
# ═══════════════════════════════════════════════════════════════════════


@router.get(
    "/incidents/{incident_id}/tracking",
    response_model=TrackingHistoryResponse,
    summary="CU-26 · Historial de tracking GPS del incidente",
)
def get_tracking_history(
    incident_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current: Usuario = Depends(get_current_user),
):
    """Retorna las últimas N posiciones GPS registradas para un incidente."""
    points = TrackingService.get_history(db, incident_id, limit)
    return TrackingHistoryResponse(
        incidente_id=incident_id,
        total_puntos=len(points),
        puntos=[TrackingPointOut.model_validate(p) for p in points],
    )


# ═══════════════════════════════════════════════════════════════════════
# CU-24 — Canal Bidireccional WebSocket
# ═══════════════════════════════════════════════════════════════════════


def _authenticate_ws_token(token: str, db: Session) -> Usuario | None:
    """Autentica un usuario por JWT en el handshake WebSocket."""
    payload = jwt_payload_safe(token)
    if not payload:
        return None

    sub = payload.get("sub")
    if sub is None:
        return None

    user = db.query(Usuario).filter(Usuario.id == int(sub)).first()
    if not user or not user.esta_activo:
        return None

    return user


@router.websocket("/ws/incidents/{incident_id}")
async def ws_incident_channel(
    websocket: WebSocket,
    incident_id: int,
    token: str = Query(default=""),
):
    """
    CU-24/25/26 · Canal bidireccional WebSocket para un incidente.

    Soporta:
        - Recibir actualizaciones de estado (state_change)
        - Recibir posiciones GPS del técnico (location_update)
        - Heartbeat (ping/pong) para detección de desconexiones

    Autenticación:
        Se espera el token JWT como query param: ?token=<jwt>
    """
    # ── Autenticación en handshake ──
    db = next(get_db())
    user = None
    if token:
        user = _authenticate_ws_token(token, db)

    channel_id = f"incident:{incident_id}"
    await manager.connect(websocket, channel_id)

    # Enviar ACK de conexión
    await websocket.send_json({
        "type": "ack",
        "message": "Conectado al canal de incidente",
        "incident_id": incident_id,
        "authenticated": user is not None,
        "user_id": user.id if user else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "JSON inválido",
                })
                continue

            msg_type = data.get("type", "")

            # ── Heartbeat ──
            if msg_type == "heartbeat":
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            # ── Location Update (CU-26) ──
            elif msg_type == "location_update":
                gps_data = {
                    "type": "location_update",
                    "incident_id": incident_id,
                    "lat": data.get("lat"),
                    "lng": data.get("lng"),
                    "precision_m": data.get("precision_m"),
                    "velocidad_kmh": data.get("velocidad_kmh"),
                    "heading": data.get("heading"),
                    "role": data.get("role", "tecnico"),
                    "user_id": user.id if user else None,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                # Persistir punto GPS si está autenticado
                if user and data.get("lat") and data.get("lng"):
                    try:
                        db_fresh = next(get_db())
                        TrackingService.record_position(
                            db=db_fresh,
                            incident_id=incident_id,
                            user_id=user.id,
                            rol=data.get("role", "tecnico"),
                            payload=TrackingGPSPayload(
                                latitud=data["lat"],
                                longitud=data["lng"],
                                precision_m=data.get("precision_m"),
                                velocidad_kmh=data.get("velocidad_kmh"),
                                heading=data.get("heading"),
                            ),
                        )
                    except Exception as gps_err:
                        logger.warning(f"Error guardando GPS: {gps_err}")

                # Broadcast a todos los suscriptores del incidente
                await manager.send_personal_message(gps_data, channel_id)

            # ── State Change Request (CU-25) ──
            elif msg_type == "state_change":
                if not user:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Autenticación requerida para cambiar estado",
                    })
                    continue

                try:
                    db_fresh = next(get_db())
                    result = RealtimeStateService.transition_state(
                        db=db_fresh,
                        incident_id=incident_id,
                        new_state=data.get("nuevo_estado", ""),
                        actor_id=user.id,
                        actor_rol=user.rol,
                        notas=data.get("notas"),
                    )

                    ws_response = {
                        "type": "state_change",
                        "incident_id": incident_id,
                        "estado_anterior": result.estado_anterior,
                        "estado_nuevo": result.estado_nuevo,
                        "label": result.label,
                        "actor_id": result.actor_id,
                        "transiciones_disponibles": result.transiciones_disponibles,
                        "timestamp": result.timestamp.isoformat(),
                    }
                    await manager.send_personal_message(ws_response, channel_id)

                except (ValueError, PermissionError) as state_err:
                    await websocket.send_json({
                        "type": "error",
                        "message": str(state_err),
                    })

            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Tipo de mensaje no reconocido: '{msg_type}'",
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket, channel_id)
        logger.info(f"WS desconectado: canal={channel_id}")
    finally:
        db.close()


@router.websocket("/ws/notifications/{user_id}")
async def ws_user_notifications(
    websocket: WebSocket,
    user_id: int,
    token: str = Query(default=""),
):
    """
    CU-24 · Canal de notificaciones en tiempo real por usuario.

    Recibe notificaciones push de:
        - Taller aceptó/rechazó la solicitud
        - Estado del servicio cambió
        - Técnico en camino
        - Servicio finalizado
    """
    channel_id = f"user:{user_id}"
    await manager.connect(websocket, channel_id)

    await websocket.send_json({
        "type": "ack",
        "message": "Canal de notificaciones conectado",
        "user_id": user_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if data.get("type") == "heartbeat":
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket, channel_id)
        logger.info(f"WS notificaciones desconectado: user={user_id}")
