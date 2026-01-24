"""
Real-time Location Tracking Endpoints
PRODUCTION READY - with real-time status updates
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
import json
from datetime import datetime, timedelta, timezone
import logging
import sys
import asyncio

from app.db.session import get_db
from app.models.volunteer import Volunteer
from app.models.volunteer_location import VolunteerLocation
from app.models.user import User
from app.services.location_manager import location_manager
from app.api.deps import get_current_user
from app.core.security import decode_access_token
from app.schemas.location import LocationResponse, VolunteerLocationDetail

router = APIRouter()

# ========================================
# CONFIGURE LOGGING
# ========================================

debug_logger = logging.getLogger("websocket_debug")
debug_logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler("debug.log", mode='a', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)

formatter = logging.Formatter(
    '%(asctime)s | %(levelname)-8s | %(funcName)-30s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

debug_logger.addHandler(file_handler)
debug_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)

# ========================================
# CONFIGURATION CONSTANTS
# ========================================

RECENT_LOCATION_WINDOW_MINUTES = 5
STATUS_ONLINE_THRESHOLD_SECONDS = 120  # 2 minutes
STATUS_STALE_THRESHOLD_SECONDS = 300   # 5 minutes
STATUS_CHECK_INTERVAL_SECONDS = 30     # Check every 30 seconds

# ========================================
# HELPER FUNCTIONS
# ========================================

def make_aware(dt: datetime) -> datetime:
    """Convert naive datetime to timezone-aware UTC"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

def determine_volunteer_status(
    location_timestamp: datetime,
    volunteer_id: int,
    current_time: datetime = None
) -> str:
    """
    Determine volunteer status based on WebSocket connection AND last location time.
    WebSocket connection takes priority over timestamp.
    """
    if current_time is None:
        current_time = datetime.now(timezone.utc)
    
    # PRIORITY 1: Check WebSocket connection (most accurate)
    is_connected = location_manager.is_volunteer_connected(volunteer_id)
    
    if is_connected:
        return "online"
    
    # PRIORITY 2: Check timestamp if not connected
    location_timestamp = make_aware(location_timestamp)
    time_diff = (current_time - location_timestamp).total_seconds()
    
    if time_diff < STATUS_ONLINE_THRESHOLD_SECONDS:
        return "online"  # Just disconnected, might reconnect
    elif time_diff < STATUS_STALE_THRESHOLD_SECONDS:
        return "stale"
    else:
        return "offline"

def get_volunteer_current_status(volunteer_id: int, db: Session) -> dict:
    """
    Get current status of a volunteer with latest location.
    Returns status dict with all necessary info.
    """
    volunteer = db.query(Volunteer).filter(Volunteer.id == volunteer_id).first()
    if not volunteer:
        return None
    
    now = datetime.now(timezone.utc)
    recent_threshold = now - timedelta(minutes=RECENT_LOCATION_WINDOW_MINUTES)
    
    # Get latest location within recent window
    recent_location = db.query(VolunteerLocation).filter(
        VolunteerLocation.volunteer_id == volunteer_id,
        VolunteerLocation.timestamp >= recent_threshold
    ).order_by(VolunteerLocation.timestamp.desc()).first()
    
    if recent_location:
        location_timestamp = make_aware(recent_location.timestamp)
        vol_status = determine_volunteer_status(location_timestamp, volunteer_id, now)
        
        return {
            "volunteer_id": volunteer.id,
            "volunteer_name": volunteer.username,
            "volunteer_email": volunteer.email,
            "latitude": float(recent_location.latitude),
            "longitude": float(recent_location.longitude),
            "accuracy": float(recent_location.accuracy) if recent_location.accuracy else None,
            "speed": float(recent_location.speed) if recent_location.speed else None,
            "heading": float(recent_location.heading) if recent_location.heading else None,
            "battery_level": recent_location.battery_level,
            "timestamp": location_timestamp.isoformat(),
            "status": vol_status,
            "is_active": recent_location.is_active
        }
    else:
        # No recent location - offline
        return {
            "volunteer_id": volunteer.id,
            "volunteer_name": volunteer.username,
            "volunteer_email": volunteer.email,
            "latitude": None,
            "longitude": None,
            "accuracy": None,
            "speed": None,
            "heading": None,
            "battery_level": None,
            "timestamp": None,
            "status": "offline",
            "is_active": False
        }

# ========================================
# WEBSOCKET: VOLUNTEER → BACKEND
# ========================================

@router.websocket("/ws/volunteer/{volunteer_id}/location")
async def volunteer_location_stream(
    websocket: WebSocket,
    volunteer_id: int,
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for volunteers to send real-time location updates.
    """
    politician_id = None
    volunteer = None
    
    debug_logger.info("=" * 100)
    debug_logger.info(f"VOLUNTEER WEBSOCKET CONNECTION ATTEMPT")
    debug_logger.info("=" * 100)
    debug_logger.info(f"Volunteer ID: {volunteer_id}")
    debug_logger.info(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    
    try:
        # STEP 1: Verify volunteer exists and is active
        volunteer = db.query(Volunteer).filter(
            Volunteer.id == volunteer_id,
            Volunteer.is_active == True
        ).first()
        
        if not volunteer:
            debug_logger.error(f"Volunteer {volunteer_id} NOT FOUND or INACTIVE")
            await websocket.close(code=4004, reason="Volunteer not found or inactive")
            return
        
        politician_id = volunteer.politician_id
        
        debug_logger.info(f"Volunteer FOUND:")
        debug_logger.info(f"   - Volunteer ID: {volunteer.id}")
        debug_logger.info(f"   - Volunteer Name: {volunteer.username}")
        debug_logger.info(f"   - BELONGS TO POLITICIAN ID: {politician_id}")
        
        # Verify politician is active
        politician = db.query(User).filter(
            User.user_id == politician_id,
            User.is_active == True
        ).first()
        
        if not politician:
            debug_logger.error(f"Politician {politician_id} NOT FOUND or INACTIVE")
            await websocket.close(code=4003, reason="Politician account inactive")
            return
        
        debug_logger.info(f"Politician Details:")
        debug_logger.info(f"   - Politician ID: {politician.user_id}")
        debug_logger.info(f"   - Politician Name: {politician.full_name}")
        
        # STEP 2: Accept WebSocket
        await websocket.accept()
        debug_logger.info(f"Volunteer {volunteer_id} WebSocket ACCEPTED")
        
        # STEP 3: Register with location manager
        await location_manager.connect_volunteer(volunteer_id, websocket)
        
        # STEP 4: Send connection confirmation
        await websocket.send_json({
            "status": "connected",
            "volunteer_id": volunteer_id,
            "message": "Location tracking started",
            "update_interval_seconds": 30
        })
        
        # STEP 5: Broadcast ONLINE status
        last_location = db.query(VolunteerLocation).filter(
            VolunteerLocation.volunteer_id == volunteer_id
        ).order_by(VolunteerLocation.timestamp.desc()).first()
        
        online_broadcast = {
            "volunteer_id": volunteer_id,
            "volunteer_name": volunteer.username,
            "volunteer_email": volunteer.email,
            "status": "online",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if last_location:
            online_broadcast.update({
                "latitude": float(last_location.latitude),
                "longitude": float(last_location.longitude),
                "accuracy": float(last_location.accuracy) if last_location.accuracy else None,
                "speed": float(last_location.speed) if last_location.speed else None,
                "heading": float(last_location.heading) if last_location.heading else None,
                "battery_level": last_location.battery_level,
            })
        
        debug_logger.info(f"BROADCASTING ONLINE STATUS:")
        debug_logger.info(f"   - FROM: Volunteer {volunteer_id}")
        debug_logger.info(f"   - TO: Politician {politician_id} ONLY")
        
        await location_manager.broadcast_location_to_politician(
            politician_id,
            online_broadcast
        )
        
        # STEP 6: Listen for location updates
        debug_logger.info(f"Listening for location updates from volunteer {volunteer_id}...")
        
        while True:
            data = await websocket.receive_text()
            
            if data == "ping":
                await websocket.send_text("pong")
                continue
            
            try:
                location_json = json.loads(data)
                
                debug_logger.info(f"LOCATION UPDATE RECEIVED:")
                debug_logger.info(f"   - Volunteer ID: {volunteer_id}")
                debug_logger.info(f"   - Lat/Lng: ({location_json.get('latitude')}, {location_json.get('longitude')})")
                
                # Mark previous locations as inactive
                db.query(VolunteerLocation).filter(
                    VolunteerLocation.volunteer_id == volunteer_id,
                    VolunteerLocation.is_active == True
                ).update({"is_active": False}, synchronize_session=False)
                
                # Save new location
                location = VolunteerLocation(
                    volunteer_id=volunteer_id,
                    latitude=location_json.get("latitude"),
                    longitude=location_json.get("longitude"),
                    accuracy=location_json.get("accuracy"),
                    speed=location_json.get("speed"),
                    heading=location_json.get("heading"),
                    battery_level=location_json.get("battery_level"),
                    is_active=True
                )
                db.add(location)
                db.commit()
                db.refresh(location)
                
                debug_logger.info(f"Location saved to database (ID: {location.id})")
                
                # Broadcast to politician's dashboard
                broadcast_data = {
                    "volunteer_id": volunteer_id,
                    "volunteer_name": volunteer.username,
                    "volunteer_email": volunteer.email,
                    "latitude": float(location.latitude),
                    "longitude": float(location.longitude),
                    "accuracy": float(location.accuracy) if location.accuracy else None,
                    "speed": float(location.speed) if location.speed else None,
                    "heading": float(location.heading) if location.heading else None,
                    "battery_level": location.battery_level,
                    "timestamp": make_aware(location.timestamp).isoformat(),
                    "status": "online"
                }
                
                debug_logger.info(f"BROADCASTING to Politician {politician_id} ONLY")
                
                await location_manager.broadcast_location_to_politician(
                    politician_id, 
                    broadcast_data
                )
                
                # Send acknowledgment
                await websocket.send_json({
                    "status": "received",
                    "timestamp": make_aware(location.timestamp).isoformat()
                })
                
            except json.JSONDecodeError as e:
                debug_logger.error(f"Invalid JSON from volunteer {volunteer_id}: {e}")
                await websocket.send_json({"error": "Invalid JSON format"})
            except Exception as e:
                debug_logger.error(f"Error processing location: {e}")
                import traceback
                debug_logger.error(traceback.format_exc())
                db.rollback()
            
    except WebSocketDisconnect:
        debug_logger.info(f"Volunteer {volunteer_id} WebSocket DISCONNECTED")
    
    except Exception as e:
        debug_logger.error(f"CRITICAL ERROR in volunteer {volunteer_id}: {e}")
        import traceback
        debug_logger.error(traceback.format_exc())
    
    finally:
        # CLEANUP
        debug_logger.info(f"CLEANUP for volunteer {volunteer_id}")
        location_manager.disconnect_volunteer(volunteer_id)
        
        try:
            # Mark all locations as inactive
            db.query(VolunteerLocation).filter(
                VolunteerLocation.volunteer_id == volunteer_id,
                VolunteerLocation.is_active == True
            ).update({"is_active": False}, synchronize_session=False)
            db.commit()
        except Exception as e:
            debug_logger.error(f"Error updating location status: {e}")
            db.rollback()
        
        # Broadcast OFFLINE status
        if politician_id and volunteer:
            try:
                last_location = db.query(VolunteerLocation).filter(
                    VolunteerLocation.volunteer_id == volunteer_id
                ).order_by(VolunteerLocation.timestamp.desc()).first()
                
                offline_broadcast = {
                    "volunteer_id": volunteer_id,
                    "volunteer_name": volunteer.username,
                    "volunteer_email": volunteer.email,
                    "status": "offline",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                if last_location:
                    offline_broadcast.update({
                        "latitude": float(last_location.latitude),
                        "longitude": float(last_location.longitude),
                        "accuracy": float(last_location.accuracy) if last_location.accuracy else None,
                        "speed": float(last_location.speed) if last_location.speed else None,
                        "heading": float(last_location.heading) if last_location.heading else None,
                        "battery_level": last_location.battery_level,
                    })
                
                debug_logger.info(f"BROADCASTING OFFLINE to Politician {politician_id}")
                
                await location_manager.broadcast_location_to_politician(
                    politician_id,
                    offline_broadcast
                )
            except Exception as e:
                debug_logger.error(f"Error broadcasting offline status: {e}")
        
        debug_logger.info("=" * 100)
        debug_logger.info(f"VOLUNTEER {volunteer_id} SESSION ENDED")
        debug_logger.info("=" * 100)

# ========================================
# WEBSOCKET: BACKEND → POLITICIAN DASHBOARD
# ========================================

@router.websocket("/ws/politician/locations")
async def politician_location_dashboard(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for politician dashboard.
    Includes periodic status checks to detect offline volunteers.
    """
    politician_id = None
    connection_accepted = False
    status_check_task = None
    
    debug_logger.info("")
    debug_logger.info("=" * 100)
    debug_logger.info(f"POLITICIAN WEBSOCKET CONNECTION ATTEMPT")
    debug_logger.info("=" * 100)
    debug_logger.info(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    
    async def periodic_status_check():
        """
        Background task to check volunteer statuses periodically.
        Detects when volunteers go offline without explicit disconnect.
        """
        while True:
            try:
                await asyncio.sleep(STATUS_CHECK_INTERVAL_SECONDS)
                
                debug_logger.debug(f"Periodic status check for Politician {politician_id}")
                
                # Get all volunteers for this politician
                volunteers = db.query(Volunteer).filter(
                    Volunteer.politician_id == politician_id,
                    Volunteer.is_active == True
                ).all()
                
                status_updates = []
                
                for volunteer in volunteers:
                    # Get current status
                    current_status = get_volunteer_current_status(volunteer.id, db)
                    if current_status:
                        status_updates.append(current_status)
                
                # Send status update to politician
                if status_updates:
                    status_message = {
                        "type": "status_sync",
                        "volunteers": status_updates,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    
                    try:
                        await websocket.send_json(status_message)
                        debug_logger.debug(f"Status sync sent to Politician {politician_id}: {len(status_updates)} volunteers")
                    except Exception as e:
                        debug_logger.error(f"Failed to send status sync: {e}")
                        break
                        
            except asyncio.CancelledError:
                debug_logger.info(f"Status check task cancelled for Politician {politician_id}")
                break
            except Exception as e:
                debug_logger.error(f"Error in periodic status check: {e}")
    
    try:
        # STEP 1: Validate JWT token
        payload = decode_access_token(token)
        if payload is None:
            debug_logger.error("Invalid JWT token")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
            return
        
        user_email = payload.get("sub")
        
        if not user_email:
            debug_logger.error("No email in JWT payload")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
            return
        
        # STEP 2: Query user by EMAIL
        user = db.query(User).filter(
            User.email == user_email,
            User.is_active == True
        ).first()
        
        if not user:
            debug_logger.error(f"User NOT FOUND or INACTIVE for email: {user_email}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User not found")
            return
        
        politician_id = user.user_id
        
        debug_logger.info(f"Politician FOUND:")
        debug_logger.info(f"   - POLITICIAN ID: {politician_id}")
        debug_logger.info(f"   - Email: {user.email}")
        debug_logger.info(f"   - Full Name: {user.full_name}")
        
        # STEP 3: Accept WebSocket
        await websocket.accept()
        connection_accepted = True
        debug_logger.info(f"Politician {politician_id} WebSocket ACCEPTED")
        
        # STEP 4: Register with location manager
        await location_manager.connect_politician(politician_id, websocket)
        
        # STEP 5: Get ONLY this politician's volunteers
        debug_logger.info(f"Fetching volunteers FOR POLITICIAN {politician_id} ONLY...")
        
        volunteers = db.query(Volunteer).filter(
            Volunteer.politician_id == politician_id,
            Volunteer.is_active == True
        ).all()
        
        debug_logger.info(f"Found {len(volunteers)} volunteer(s) for Politician {politician_id}")
        
        # STEP 6: Build initial state
        active_locations = []
        
        for volunteer in volunteers:
            status_data = get_volunteer_current_status(volunteer.id, db)
            if status_data:
                active_locations.append(status_data)
                debug_logger.info(f"   - Volunteer {volunteer.id}: {status_data['status']}")
        
        # STEP 7: Send initial state
        now = datetime.now(timezone.utc)
        initial_message = {
            "type": "initial_state",
            "volunteers": active_locations,
            "count": len([v for v in active_locations if v['latitude'] is not None]),
            "total_volunteers": len(volunteers),
            "server_time": now.isoformat(),
            "politician_id": politician_id,
            "recent_window_minutes": RECENT_LOCATION_WINDOW_MINUTES,
            "status_check_interval": STATUS_CHECK_INTERVAL_SECONDS
        }
        
        debug_logger.info(f"SENDING INITIAL STATE to Politician {politician_id}:")
        debug_logger.info(f"   - Total volunteers: {len(volunteers)}")
        debug_logger.info(f"   - With recent locations: {initial_message['count']}")
        
        await websocket.send_json(initial_message)
        debug_logger.info(f"Initial state sent successfully")
        
        # STEP 8: Start periodic status check task
        status_check_task = asyncio.create_task(periodic_status_check())
        debug_logger.info(f"Started periodic status check (every {STATUS_CHECK_INTERVAL_SECONDS}s)")
        
        # STEP 9: Keep connection alive
        debug_logger.info(f"Listening for messages from Politician {politician_id}...")
        
        while True:
            try:
                message = await websocket.receive_text()
                
                if message == "ping":
                    await websocket.send_text("pong")
                elif message == "refresh":
                    # Manual refresh request
                    debug_logger.info(f"Manual refresh requested by Politician {politician_id}")
                    refresh_data = []
                    for volunteer in volunteers:
                        status_data = get_volunteer_current_status(volunteer.id, db)
                        if status_data:
                            refresh_data.append(status_data)
                    
                    await websocket.send_json({
                        "type": "status_sync",
                        "volunteers": refresh_data,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                else:
                    debug_logger.warning(f"Unknown message from politician {politician_id}: {message}")
                    
            except WebSocketDisconnect:
                debug_logger.info(f"Politician {politician_id} disconnected gracefully")
                break
            except Exception as e:
                debug_logger.error(f"Error in politician {politician_id} message loop: {e}")
                break
                
    except WebSocketDisconnect:
        debug_logger.info(f"Politician {politician_id or 'unknown'} disconnected before setup")
    
    except Exception as e:
        debug_logger.error(f"CRITICAL ERROR in politician {politician_id or 'unknown'}: {e}")
        import traceback
        debug_logger.error(traceback.format_exc())
        
        if connection_accepted:
            try:
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            except:
                pass
    
    finally:
        # Cancel status check task
        if status_check_task:
            status_check_task.cancel()
            try:
                await status_check_task
            except asyncio.CancelledError:
                pass
        
        if politician_id:
            location_manager.disconnect_politician(politician_id, websocket)
            debug_logger.info(f"Cleanup complete for politician {politician_id}")
        
        debug_logger.info("=" * 100)
        debug_logger.info(f"POLITICIAN {politician_id or 'unknown'} SESSION ENDED")
        debug_logger.info("=" * 100)

# [REST API endpoints remain the same as before]
# ... (all REST endpoints from previous code)

# ========================================
# REST API: GET ACTIVE LOCATIONS
# ========================================

@router.get("/volunteers/locations/active", response_model=List[VolunteerLocationDetail])
def get_active_volunteer_locations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current locations of active volunteers (REST fallback).
    ONLY returns THIS politician's volunteers with RECENT locations.
    """
    debug_logger.info(f"REST API: GET /volunteers/locations/active")
    debug_logger.info(f"   - Politician ID: {current_user.user_id}")
    
    volunteers = db.query(Volunteer).filter(
        Volunteer.politician_id == current_user.user_id,
        Volunteer.is_active == True
    ).all()
    
    locations = []
    now = datetime.now(timezone.utc)
    recent_threshold = now - timedelta(minutes=RECENT_LOCATION_WINDOW_MINUTES)
    
    for volunteer in volunteers:
        latest = db.query(VolunteerLocation).filter(
            VolunteerLocation.volunteer_id == volunteer.id,
            VolunteerLocation.timestamp >= recent_threshold  # CRITICAL: Recent only
        ).order_by(VolunteerLocation.timestamp.desc()).first()
        
        if latest:
            location_timestamp = make_aware(latest.timestamp)
            vol_status = determine_volunteer_status(location_timestamp, volunteer.id, now)
            
            locations.append(VolunteerLocationDetail(
                volunteer_id=volunteer.id,
                volunteer_name=volunteer.username,
                volunteer_email=volunteer.email,
                latitude=latest.latitude,
                longitude=latest.longitude,
                accuracy=latest.accuracy,
                speed=latest.speed,
                heading=latest.heading,
                battery_level=latest.battery_level,
                timestamp=latest.timestamp,
                status=vol_status
            ))
    
    debug_logger.info(f"   - Returning {len(locations)} active location(s)")
    return locations

# ========================================
# REST API: GET LOCATION HISTORY
# ========================================

@router.get("/volunteers/{volunteer_id}/location-history", response_model=List[LocationResponse])
def get_volunteer_location_history(
    volunteer_id: int,
    hours: int = Query(24, ge=1, le=168, description="Hours of history (max 7 days)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get location history for a specific volunteer (SECURITY: Only if they belong to current user)"""
    
    # SECURITY CHECK: Verify volunteer belongs to this politician
    volunteer = db.query(Volunteer).filter(
        Volunteer.id == volunteer_id,
        Volunteer.politician_id == current_user.user_id
    ).first()
    
    if not volunteer:
        debug_logger.error(f"SECURITY: Politician {current_user.user_id} tried to access Volunteer {volunteer_id} (unauthorized)")
        raise HTTPException(status_code=404, detail="Volunteer not found")
    
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    locations = db.query(VolunteerLocation).filter(
        VolunteerLocation.volunteer_id == volunteer_id,
        VolunteerLocation.timestamp >= since
    ).order_by(VolunteerLocation.timestamp.asc()).all()
    
    debug_logger.info(f"Politician {current_user.user_id} accessed history for Volunteer {volunteer_id}: {len(locations)} records")
    
    return locations

# ========================================
# REST API: STOP TRACKING
# ========================================

@router.post("/volunteers/{volunteer_id}/location/stop")
def stop_location_tracking(
    volunteer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Stop location tracking (SECURITY: Only for own volunteers)"""
    
    # SECURITY CHECK
    volunteer = db.query(Volunteer).filter(
        Volunteer.id == volunteer_id,
        Volunteer.politician_id == current_user.user_id
    ).first()
    
    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer not found")
    
    # Mark locations inactive
    updated_count = db.query(VolunteerLocation).filter(
        VolunteerLocation.volunteer_id == volunteer_id
    ).update({"is_active": False}, synchronize_session=False)
    db.commit()
    
    # Disconnect WebSocket
    location_manager.disconnect_volunteer(volunteer_id)
    
    debug_logger.info(f"Politician {current_user.user_id} stopped tracking for Volunteer {volunteer_id}")
    
    return {
        "success": True,
        "message": f"Location tracking stopped for {volunteer.username}"
    }

# ========================================
# REST API: GET VOLUNTEER STATUS
# ========================================

@router.get("/volunteers/{volunteer_id}/location/status")
def get_volunteer_location_status(
    volunteer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get volunteer status (SECURITY: Only for own volunteers)"""
    
    # SECURITY CHECK
    volunteer = db.query(Volunteer).filter(
        Volunteer.id == volunteer_id,
        Volunteer.politician_id == current_user.user_id
    ).first()
    
    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer not found")
    
    # Get latest RECENT location
    now = datetime.now(timezone.utc)
    recent_threshold = now - timedelta(minutes=RECENT_LOCATION_WINDOW_MINUTES)
    
    latest = db.query(VolunteerLocation).filter(
        VolunteerLocation.volunteer_id == volunteer_id,
        VolunteerLocation.timestamp >= recent_threshold
    ).order_by(VolunteerLocation.timestamp.desc()).first()
    
    if not latest:
        return {
            "volunteer_id": volunteer_id,
            "volunteer_name": volunteer.username,
            "status": "offline",
            "is_tracking": False
        }
    
    location_timestamp = make_aware(latest.timestamp)
    vol_status = determine_volunteer_status(location_timestamp, volunteer_id, now)
    
    return {
        "volunteer_id": volunteer_id,
        "volunteer_name": volunteer.username,
        "status": vol_status,
        "is_tracking": latest.is_active,
        "last_update": location_timestamp.isoformat(),
        "latitude": float(latest.latitude),
        "longitude": float(latest.longitude),
        "accuracy": float(latest.accuracy) if latest.accuracy else None,
        "battery_level": latest.battery_level
    }
