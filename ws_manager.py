from fastapi import WebSocket
from typing import List, Dict, Any
import json
import logging

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections and websocket in self.active_connections[user_id]:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def broadcast_to_user(self, user_id: str, message: Dict[str, Any]):
        if user_id not in self.active_connections:
            return
            
        msg_str = json.dumps(message)
        dead_connections = []
        for connection in self.active_connections[user_id]:
            try:
                await connection.send_text(msg_str)
            except Exception as e:
                logging.warning(f"Failed to send to websocket for user {user_id}, marking as dead: {e}")
                dead_connections.append(connection)
        
        for dead in dead_connections:
            self.disconnect(dead, user_id)

manager = ConnectionManager()
