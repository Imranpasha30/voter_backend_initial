"""
WebSocket Connection Manager for Real-time Location Tracking
Handles volunteer → politician WebSocket broadcasting
"""

from typing import Dict, Set
from fastapi import WebSocket
import logging
import json

logger = logging.getLogger(__name__)


class LocationManager:
    """Manages WebSocket connections for real-time location tracking"""
    
    def __init__(self):
        # volunteer_id → WebSocket
        self.volunteer_connections: Dict[int, WebSocket] = {}
        
        # politician_id → Set of WebSocket connections (multiple tabs/devices)
        self.politician_connections: Dict[int, Set[WebSocket]] = {}
    
    async def connect_volunteer(self, volunteer_id: int, websocket: WebSocket):
        """Register volunteer WebSocket connection"""
        # ❌ REMOVED: await websocket.accept()  # Already accepted in endpoint!
        self.volunteer_connections[volunteer_id] = websocket
        logger.info(f"✅ Volunteer {volunteer_id} connected (Total: {len(self.volunteer_connections)})")
    
    def disconnect_volunteer(self, volunteer_id: int):
        """Remove volunteer WebSocket connection"""
        if volunteer_id in self.volunteer_connections:
            del self.volunteer_connections[volunteer_id]
            logger.info(f"🔌 Volunteer {volunteer_id} disconnected (Remaining: {len(self.volunteer_connections)})")
    
    async def connect_politician(self, politician_id: int, websocket: WebSocket):
        """Register politician WebSocket connection (supports multiple concurrent connections)"""
        # ❌ REMOVED: await websocket.accept()  # Already accepted in endpoint!
        
        if politician_id not in self.politician_connections:
            self.politician_connections[politician_id] = set()
        
        self.politician_connections[politician_id].add(websocket)
        logger.info(f"✅ Politician {politician_id} connected (Connections: {len(self.politician_connections[politician_id])})")
    
    def disconnect_politician(self, politician_id: int, websocket: WebSocket):
        """Remove politician WebSocket connection"""
        if politician_id in self.politician_connections:
            self.politician_connections[politician_id].discard(websocket)
            
            if not self.politician_connections[politician_id]:
                del self.politician_connections[politician_id]
                logger.info(f"🔌 Politician {politician_id} fully disconnected")
            else:
                logger.info(f"🔌 Politician {politician_id} one connection closed (Remaining: {len(self.politician_connections[politician_id])})")
    
    async def broadcast_location_to_politician(self, politician_id: int, location_data: dict):
        """
        Broadcast volunteer location update to all politician's connected WebSockets.
        Removes dead connections automatically.
        """
        if politician_id not in self.politician_connections:
            logger.debug(f"⚠️  No active connections for politician {politician_id}")
            return
        
        message = {
            "type": "location_update",
            "data": location_data
        }
        
        dead_connections = set()
        
        for websocket in self.politician_connections[politician_id]:
            try:
                await websocket.send_json(message)
                logger.debug(f"📤 Sent location update to politician {politician_id}")
            except Exception as e:
                logger.error(f"❌ Failed to send to politician {politician_id}: {e}")
                dead_connections.add(websocket)
        
        # Remove dead connections
        for dead_ws in dead_connections:
            self.politician_connections[politician_id].discard(dead_ws)
        
        # Clean up if no connections left
        if not self.politician_connections[politician_id]:
            del self.politician_connections[politician_id]
            logger.warning(f"🗑️  All connections dead for politician {politician_id}")
    
    def get_active_volunteer_count(self) -> int:
        """Get number of currently connected volunteers"""
        return len(self.volunteer_connections)
    
    def get_active_politician_count(self) -> int:
        """Get number of currently connected politicians"""
        return len(self.politician_connections)
    
    def is_volunteer_connected(self, volunteer_id: int) -> bool:
        """Check if volunteer is currently connected"""
        return volunteer_id in self.volunteer_connections
    
    def is_politician_connected(self, politician_id: int) -> bool:
        """Check if politician has any active connections"""
        return politician_id in self.politician_connections


# Global singleton instance
location_manager = LocationManager()
