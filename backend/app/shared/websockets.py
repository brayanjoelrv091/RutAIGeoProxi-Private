from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        # Mapea un identificador de sala (ej. incident_id) a una lista de WebSockets activos
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_connections:
            if websocket in self.active_connections[room_id]:
                self.active_connections[room_id].remove(websocket)
            if not self.active_connections[room_id]:
                # Limpiar memoria si la sala queda vacía
                del self.active_connections[room_id]

    async def send_personal_message(self, message: dict, target):
        if isinstance(target, str):
            await self.broadcast_to_room(message, target)
        else:
            await target.send_json(message)

    async def broadcast_to_room(self, message: dict, room_id: str):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    # Si falla el envío (ej. conexión rota no detectada), lo ignoramos aquí,
                    # el ciclo de receive() del websocket se encargará de llamar a disconnect()
                    pass

# Instancia global (Singleton) para toda la app
manager = ConnectionManager()
