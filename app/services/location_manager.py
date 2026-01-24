"""
WebSocket Connection Manager
PRODUCTION READY - Isolated politician broadcasts
"""

from typing import Dict, Set
from fastapi import WebSocket
import logging

debug_logger = logging.getLogger("websocket_debug")
logger = logging.getLogger(__name__)

class LocationManager:
    """Manages WebSocket connections with strict isolation between politicians"""
    
    def __init__(self):
        self.volunteer_connections: Dict[int, WebSocket] = {}
        self.politician_connections: Dict[int, Set[WebSocket]] = {}
        debug_logger.info("LocationManager initialized")
    
    async def connect_volunteer(self, volunteer_id: int, websocket: WebSocket):
        """Register volunteer WebSocket"""
        self.volunteer_connections[volunteer_id] = websocket
        debug_logger.info(f"Volunteer {volunteer_id} connected (Total: {len(self.volunteer_connections)})")
    
    def disconnect_volunteer(self, volunteer_id: int):
        """Remove volunteer WebSocket"""
        if volunteer_id in self.volunteer_connections:
            del self.volunteer_connections[volunteer_id]
            debug_logger.info(f"Volunteer {volunteer_id} disconnected (Remaining: {len(self.volunteer_connections)})")
    
    async def connect_politician(self, politician_id: int, websocket: WebSocket):
        """Register politician WebSocket (supports multiple tabs)"""
        if politician_id not in self.politician_connections:
            self.politician_connections[politician_id] = set()
        
        self.politician_connections[politician_id].add(websocket)
        debug_logger.info(f"Politician {politician_id} connected (Connections: {len(self.politician_connections[politician_id])})")
        debug_logger.info(f"All connected politicians: {list(self.politician_connections.keys())}")
    
    def disconnect_politician(self, politician_id: int, websocket: WebSocket):
        """Remove politician WebSocket"""
        if politician_id in self.politician_connections:
            self.politician_connections[politician_id].discard(websocket)
            
            if not self.politician_connections[politician_id]:
                del self.politician_connections[politician_id]
                debug_logger.info(f"Politician {politician_id} fully disconnected")
            else:
                debug_logger.info(f"Politician {politician_id} one connection closed (Remaining: {len(self.politician_connections[politician_id])})")
    
    async def broadcast_location_to_politician(self, politician_id: int, location_data: dict):
        """
        Broadcast ONLY to specified politician.
        CRITICAL: Prevents cross-politician data leakage.
        """
        debug_logger.info(f"BROADCAST REQUEST:")
        debug_logger.info(f"   - Target: Politician {politician_id}")
        debug_logger.info(f"   - Volunteer: {location_data.get('volunteer_id')}")
        debug_logger.info(f"   - Status: {location_data.get('status')}")
        debug_logger.info(f"   - All connected politicians: {list(self.politician_connections.keys())}")
        
        # SECURITY CHECK
        other_politicians = [p for p in self.politician_connections.keys() if p != politician_id]
        if other_politicians:
            debug_logger.warning(f"SECURITY: Other politicians connected {other_politicians} - they will NOT receive this")
        
        if politician_id not in self.politician_connections:
            debug_logger.warning(f"Politician {politician_id} not connected - broadcast skipped")
            return
        
        message = {
            "type": "location_update",
            "data": location_data
        }
        
        dead_connections = set()
        success_count = 0
        
        for websocket in self.politician_connections[politician_id]:
            try:
                await websocket.send_json(message)
                success_count += 1
            except Exception as e:
                debug_logger.error(f"Failed to send to politician {politician_id}: {e}")
                dead_connections.add(websocket)
        
        # Cleanup dead connections
        for dead_ws in dead_connections:
            self.politician_connections[politician_id].discard(dead_ws)
        
        if not self.politician_connections[politician_id]:
            del self.politician_connections[politician_id]
        
        debug_logger.info(f"Broadcast complete: {success_count} sent to Politician {politician_id}")
    
    def is_volunteer_connected(self, volunteer_id: int) -> bool:
        """Check if volunteer is connected"""
        return volunteer_id in self.volunteer_connections
    
    def is_politician_connected(self, politician_id: int) -> bool:
        """Check if politician is connected"""
        return politician_id in self.politician_connections

# Global singleton
location_manager = LocationManager()
