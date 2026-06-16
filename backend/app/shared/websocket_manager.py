from typing import Dict, List
from fastapi import WebSocket

class ConnectionManager:
    """
    Gestiona conexiones WebSocket para notificaciones y tracking en tiempo real.
    """
    def __init__(self):
        # Conexiones activas: { "id_referencia": [lista_de_websockets] }
        # id_referencia puede ser un user_id o un incident_id
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, reference_id: str):
        await websocket.accept()
        if reference_id not in self.active_connections:
            self.active_connections[reference_id] = []
        self.active_connections[reference_id].append(websocket)

    def disconnect(self, websocket: WebSocket, reference_id: str):
        if reference_id in self.active_connections:
            if websocket in self.active_connections[reference_id]:
                self.active_connections[reference_id].remove(websocket)
            if not self.active_connections[reference_id]:
                del self.active_connections[reference_id]

    async def send_personal_message(self, message: dict, reference_id: str):
        await self.broadcast_to_room(message, reference_id)

    async def broadcast_to_room(self, message: dict, room_id: str):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass

    async def broadcast(self, message: dict):
        for connections in self.active_connections.values():
            for connection in connections:
                await connection.send_json(message)

# Instancia global para ser usada en los módulos
manager = ConnectionManager()
