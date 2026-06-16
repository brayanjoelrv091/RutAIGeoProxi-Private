from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from app.shared.database import SessionLocal
from app.shared.security import jwt_payload_safe
from app.shared.websocket_manager import manager
import json

ws_router = APIRouter()

@ws_router.websocket("/ws/incidents/{incident_id}")
async def websocket_incident_endpoint(
    websocket: WebSocket,
    incident_id: str,
    token: str = Query(None)
):
    if not token:
        await websocket.close(code=4003, reason="Token is missing")
        return

    # Validar el JWT manualmente porque HTTPBearer tira 403 HTTP y necesitamos cerrar WS limpio
    payload = jwt_payload_safe(token)
    if not payload:
        await websocket.close(code=4003, reason="Token is invalid or expired")
        return
        
    sub = payload.get("sub")
    if not sub:
        await websocket.close(code=4003, reason="Token payload invalid")
        return

    # Obtener el tenant_id del usuario desde la BD y las coordenadas del incidente
    db: Session = SessionLocal()
    from app.modules.p1_usuarios.models import Usuario
    from app.modules.p2_incidentes.models import Incidente
    from app.modules.p8_realtime.models import TrackingGPS
    from app.shared.utils import haversine_distance
    
    try:
        user = db.query(Usuario).filter(Usuario.id == int(sub)).first()
        tenant_id = user.tenant_id if user and user.tenant_id else "global"
        rol = user.rol if user else "desconocido"
        
        incidente = db.query(Incidente).filter(Incidente.id == int(incident_id)).first()
        incidente_lat = incidente.latitud if incidente else 0.0
        incidente_lng = incidente.longitud if incidente else 0.0
    finally:
        db.close()
    
    room_id = f"tenant_{tenant_id}_incidente_{incident_id}"
    await manager.connect(websocket, room_id)
    
    try:
        while True:
            # Recibimos datos (ej. coordenadas GPS)
            data = await websocket.receive_text()
            
            try:
                parsed_data = json.loads(data)
            except json.JSONDecodeError:
                continue

            # Agregar info del remitente
            parsed_data["sender_id"] = sub
            
            # Si es un update GPS, calculamos ETA y guardamos en BD
            if parsed_data.get("type") == "GPS_UPDATE":
                lat = parsed_data.get("lat")
                lng = parsed_data.get("lng")
                if lat is not None and lng is not None and incidente_lat and incidente_lng:
                    distancia_km = haversine_distance(lat, lng, incidente_lat, incidente_lng)
                    # Asumiendo velocidad urbana promedio de 30 km/h
                    velocidad_kmh = 30.0
                    eta_minutos = (distancia_km / velocidad_kmh) * 60
                    
                    parsed_data["eta_minutos"] = round(eta_minutos, 2)
                    parsed_data["distancia_km"] = round(distancia_km, 2)
                    
                    # Persistencia en BD
                    db_session: Session = SessionLocal()
                    try:
                        nuevo_tracking = TrackingGPS(
                            incidente_id=int(incident_id),
                            usuario_id=int(sub),
                            rol=rol,
                            latitud=lat,
                            longitud=lng,
                            velocidad_kmh=velocidad_kmh
                        )
                        db_session.add(nuevo_tracking)
                        db_session.commit()
                    except Exception as e:
                        db_session.rollback()
                        print(f"[WebSocket] Error guardando TrackingGPS: {e}")
                    finally:
                        db_session.close()

            # Re-transmitir a todos en la sala
            await manager.broadcast_to_room(parsed_data, room_id)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
