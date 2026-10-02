"""WebSocket connection manager for real-time progress tracking."""

from fastapi import WebSocket
from loguru import logger


class ConnectionManager:
    """Manages active WebSocket connections for tracking jobs."""

    def __init__(self) -> None:
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, job_id: str, websocket: WebSocket) -> None:
        """Accept connection and add to job list."""
        await websocket.accept()
        self.active_connections.setdefault(job_id, []).append(websocket)
        logger.debug(f"WebSocket connected for job: {job_id}")

    def disconnect(self, job_id: str, websocket: WebSocket) -> None:
        """Remove connection from list."""
        if job_id in self.active_connections:
            if websocket in self.active_connections[job_id]:
                self.active_connections[job_id].remove(websocket)
                logger.debug(f"WebSocket disconnected for job: {job_id}")
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]

    async def send_update(self, job_id: str, message: dict) -> None:
        """Broadcast progress update to all listeners of a job."""
        if job_id in self.active_connections:
            connections = list(self.active_connections[job_id])
            for connection in connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.warning(f"Failed to send WS message, removing connection: {e}")
                    self.disconnect(job_id, connection)


manager = ConnectionManager()
