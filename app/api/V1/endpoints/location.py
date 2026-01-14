"""
Real-time Location Tracking Endpoints
WebSocket + REST API for volunteer location tracking
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
import json
from datetime import datetime, timedelta, timezone
import logging

from app.db.session import get_db
from app.models.volunteer import Volunteer
from app.models.volunteer_location import VolunteerLocation
from app.models.user import User
from app.services.location_manager import location_manager
from app.api.deps import get_current_user
from app.core.security import decode_access_token
from app.schemas.location import LocationResponse, VolunteerLocationDetail

router = APIRouter()
logger = logging.getLogger(__name__)


# ========================================
# HELPER FUNCTION: Make datetime timezone-aware
# ========================================

def make_aware(dt: datetime) -> datetime:
    """Convert naive datetime to timezone-aware UTC"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


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
    Updates every 30 seconds for battery optimization.
    """
    politician_id = None
    volunteer = None
    
    try:
        # STEP 1: Verify volunteer exists
        volunteer = db.query(Volunteer).filter(Volunteer.id == volunteer_id).first()
        if not volunteer:
            await websocket.close(code=4004, reason="Volunteer not found")
            return
        
        politician_id = volunteer.politician_id
        
        # STEP 2: Accept WebSocket
        await websocket.accept()
        logger.info(f"✅ Volunteer {volunteer_id} WebSocket accepted")
        
        # STEP 3: Register with location manager
        await location_manager.connect_volunteer(volunteer_id, websocket)
        
        # STEP 4: Send connection confirmation
        await websocket.send_json({
            "status": "connected",
            "volunteer_id": volunteer_id,
            "message": "Location tracking started ✅",
            "update_interval_seconds": 30
        })
        
        # ✅ STEP 5: BROADCAST ONLINE STATUS IMMEDIATELY
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
        
        # Include last known location if exists
        if last_location:
            online_broadcast.update({
                "latitude": float(last_location.latitude),
                "longitude": float(last_location.longitude),
                "accuracy": float(last_location.accuracy) if last_location.accuracy else None,
                "speed": float(last_location.speed) if last_location.speed else None,
                "heading": float(last_location.heading) if last_location.heading else None,
                "battery_level": last_location.battery_level,
            })
        
        await location_manager.broadcast_location_to_politician(
            politician_id,
            online_broadcast
        )
        logger.info(f"📤 Broadcast ONLINE status for volunteer {volunteer_id} to politician {politician_id}")
        
        # STEP 6: Listen for location updates
        while True:
            data = await websocket.receive_text()
            
            if data == "ping":
                await websocket.send_text("pong")
                continue
            
            try:
                location_json = json.loads(data)
                
                logger.info(f"📍 Location from volunteer {volunteer_id}: ({location_json.get('latitude')}, {location_json.get('longitude')})")
                
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
                logger.error(f"❌ Invalid JSON from volunteer {volunteer_id}: {e}")
                await websocket.send_json({"error": "Invalid JSON format"})
            except Exception as e:
                logger.error(f"❌ Error processing location: {e}")
                import traceback
                traceback.print_exc()
                db.rollback()
            
    except WebSocketDisconnect:
        logger.info(f"🔌 Volunteer {volunteer_id} WebSocket disconnected")
    
    except Exception as e:
        logger.error(f"❌ Error in volunteer {volunteer_id} location stream: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # ✅ ALWAYS CLEANUP AND BROADCAST OFFLINE STATUS
        logger.info(f"🧹 Cleaning up volunteer {volunteer_id}")
        location_manager.disconnect_volunteer(volunteer_id)
        
        try:
            # Mark all locations as inactive
            db.query(VolunteerLocation).filter(
                VolunteerLocation.volunteer_id == volunteer_id,
                VolunteerLocation.is_active == True
            ).update({"is_active": False}, synchronize_session=False)
            db.commit()
        except Exception as e:
            logger.error(f"❌ Error updating location status: {e}")
            db.rollback()
        
        # ✅ BROADCAST OFFLINE STATUS TO POLITICIAN
        if politician_id and volunteer:
            try:
                # Get last known location
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
                
                # Include last known location if exists
                if last_location:
                    offline_broadcast.update({
                        "latitude": float(last_location.latitude),
                        "longitude": float(last_location.longitude),
                        "accuracy": float(last_location.accuracy) if last_location.accuracy else None,
                        "speed": float(last_location.speed) if last_location.speed else None,
                        "heading": float(last_location.heading) if last_location.heading else None,
                        "battery_level": last_location.battery_level,
                    })
                
                await location_manager.broadcast_location_to_politician(
                    politician_id,
                    offline_broadcast
                )
                logger.info(f"📤 Broadcast OFFLINE status for volunteer {volunteer_id} to politician {politician_id}")
            except Exception as e:
                logger.error(f"❌ Error broadcasting offline status: {e}")
                import traceback
                traceback.print_exc()


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
    WebSocket endpoint for politician dashboard to receive all volunteer locations.
    Real-time updates with no polling required.
    """
    politician_id = None
    connection_accepted = False
    
    try:
        # STEP 1: Validate JWT token BEFORE accepting WebSocket
        payload = decode_access_token(token)
        if payload is None:
            logger.error("❌ Invalid JWT token")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
            return
        
        user_email = payload.get("sub")
        if not user_email:
            logger.error("❌ No email in JWT payload")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token payload")
            return
        
        # STEP 2: Query user by EMAIL
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            logger.error(f"❌ User not found for email: {user_email}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User not found")
            return
        
        politician_id = user.user_id
        
        # STEP 3: Accept WebSocket
        await websocket.accept()
        connection_accepted = True
        logger.info(f"✅ Politician {politician_id} ({user_email}) WebSocket ACCEPTED")
        
        # STEP 4: Register with location manager
        await location_manager.connect_politician(politician_id, websocket)
        
        # STEP 5: Get all volunteers
        volunteers = db.query(Volunteer).filter(
            Volunteer.politician_id == politician_id
        ).all()
        
        # STEP 6: Build initial location state (ALL volunteers)
        active_locations = []
        now = datetime.now(timezone.utc)
        
        for volunteer in volunteers:
            # Get LATEST location (no time limit)
            recent_location = db.query(VolunteerLocation).filter(
                VolunteerLocation.volunteer_id == volunteer.id
            ).order_by(VolunteerLocation.timestamp.desc()).first()
            
            if recent_location:
                location_timestamp = make_aware(recent_location.timestamp)
                time_diff = (now - location_timestamp).total_seconds()
                
                # Determine status based on time difference
                if time_diff < 120:
                    vol_status = "online"
                elif time_diff < 300:
                    vol_status = "stale"
                else:
                    vol_status = "offline"
                
                # ✅ Override with real-time connection status
                if location_manager.is_volunteer_connected(volunteer.id):
                    vol_status = "online"
                
                active_locations.append({
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
                })
            else:
                # Never tracked
                active_locations.append({
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
                    "status": "never_tracked",
                    "is_active": False
                })
        
        # STEP 7: Send initial state
        initial_message = {
            "type": "initial_state",
            "volunteers": active_locations,
            "count": len([v for v in active_locations if v['latitude'] is not None]),
            "total_volunteers": len(volunteers),
            "server_time": now.isoformat()
        }
        
        await websocket.send_json(initial_message)
        logger.info(f"📤 Sent {len(active_locations)}/{len(volunteers)} locations to politician {politician_id}")
        
        # STEP 8: Keep connection alive
        while True:
            try:
                message = await websocket.receive_text()
                
                if message == "ping":
                    await websocket.send_text("pong")
                    logger.debug(f"🏓 Pong sent to politician {politician_id}")
                else:
                    logger.warning(f"⚠️  Unknown message from politician {politician_id}: {message}")
                    
            except WebSocketDisconnect:
                logger.info(f"🔌 Politician {politician_id} WebSocket disconnected gracefully")
                break
            except Exception as e:
                logger.error(f"❌ Error in politician {politician_id} message loop: {e}")
                break
                
    except WebSocketDisconnect:
        logger.info(f"🔌 Politician {politician_id or 'unknown'} disconnected before setup complete")
    
    except Exception as e:
        logger.error(f"❌ CRITICAL ERROR in politician {politician_id or 'unknown'} WebSocket: {e}")
        import traceback
        traceback.print_exc()
        
        if connection_accepted:
            try:
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Internal server error")
            except:
                pass
    
    finally:
        if politician_id:
            location_manager.disconnect_politician(politician_id, websocket)
            logger.info(f"🧹 Cleanup complete for politician {politician_id}")


# ========================================
# REST API: GET ACTIVE LOCATIONS (Fallback)
# ========================================

@router.get("/volunteers/locations/active", response_model=List[VolunteerLocationDetail])
def get_active_volunteer_locations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current locations of all active volunteers (REST fallback)"""
    volunteers = db.query(Volunteer).filter(
        Volunteer.politician_id == current_user.user_id
    ).all()
    
    locations = []
    now = datetime.now(timezone.utc)
    
    for volunteer in volunteers:
        latest = db.query(VolunteerLocation).filter(
            VolunteerLocation.volunteer_id == volunteer.id
        ).order_by(VolunteerLocation.timestamp.desc()).first()
        
        if latest and make_aware(latest.timestamp) >= now - timedelta(minutes=5):
            time_diff = (now - make_aware(latest.timestamp)).total_seconds()
            
            if time_diff < 120:
                vol_status = "online"
            elif time_diff < 300:
                vol_status = "stale"
            else:
                vol_status = "offline"
            
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
    """Get location history for a specific volunteer"""
    volunteer = db.query(Volunteer).filter(
        Volunteer.id == volunteer_id,
        Volunteer.politician_id == current_user.user_id
    ).first()
    
    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer not found")
    
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    locations = db.query(VolunteerLocation).filter(
        VolunteerLocation.volunteer_id == volunteer_id,
        VolunteerLocation.timestamp >= since
    ).order_by(VolunteerLocation.timestamp.asc()).all()
    
    return locations


# ========================================
# REST API: TOGGLE TRACKING
# ========================================

@router.post("/volunteers/{volunteer_id}/location/stop")
def stop_location_tracking(
    volunteer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Stop location tracking for a volunteer"""
    volunteer = db.query(Volunteer).filter(
        Volunteer.id == volunteer_id,
        Volunteer.politician_id == current_user.user_id
    ).first()
    
    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer not found")
    
    # Mark all locations as inactive
    db.query(VolunteerLocation).filter(
        VolunteerLocation.volunteer_id == volunteer_id
    ).update({"is_active": False}, synchronize_session=False)
    db.commit()
    
    # Disconnect volunteer WebSocket if active
    location_manager.disconnect_volunteer(volunteer_id)
    
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
    """Get current location status of a volunteer"""
    volunteer = db.query(Volunteer).filter(
        Volunteer.id == volunteer_id,
        Volunteer.politician_id == current_user.user_id
    ).first()
    
    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer not found")
    
    # Get latest location
    latest = db.query(VolunteerLocation).filter(
        VolunteerLocation.volunteer_id == volunteer_id
    ).order_by(VolunteerLocation.timestamp.desc()).first()
    
    if not latest:
        return {
            "volunteer_id": volunteer_id,
            "volunteer_name": volunteer.username,
            "status": "never_tracked",
            "is_tracking": False
        }
    
    now = datetime.now(timezone.utc)
    location_timestamp = make_aware(latest.timestamp)
    time_diff = (now - location_timestamp).total_seconds()
    
    # Determine status
    if time_diff < 120:
        vol_status = "online"
    elif time_diff < 300:
        vol_status = "stale"
    else:
        vol_status = "offline"
    
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
