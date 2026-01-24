from sqlalchemy.orm import Session
from typing import Union, Optional, Dict, Any
from app.models.voter_change_log import VoterChangeLog
from app.models.user import User
from app.models.volunteer import Volunteer


class AuditLogger:
    """Service to log voter data changes"""
    
    @staticmethod
    def log_voter_change(
        db: Session,
        voter_id: int,
        epic_no: str,
        current_user: Union[User, Volunteer],
        action_type: str,
        field_changed: str,
        old_value: Any = None,
        new_value: Any = None,
        ip_address: Optional[str] = None,
        device_info: Optional[str] = None
    ) -> VoterChangeLog:
        """
        Log a single voter field change.
        
        Args:
            voter_id: ID of the voter
            epic_no: EPIC number of the voter
            current_user: User or Volunteer who made the change
            action_type: 'UPDATE', 'CREATE', or 'DELETE'
            field_changed: Name of the field that changed
            old_value: Previous value
            new_value: New value
            ip_address: IP address of the request
            device_info: Device/browser information
        """
        # Determine user type and get details
        if hasattr(current_user, 'politician_id'):
            # This is a Volunteer
            user_type = 'volunteer'
            user_id = None
            volunteer_id = current_user.id
            user_name = current_user.username
            user_email = current_user.email
        else:
            # This is a User (Politician)
            user_type = 'politician'
            user_id = current_user.user_id
            volunteer_id = None
            user_name = current_user.full_name
            user_email = current_user.email
        
        # Convert values to string for storage
        old_value_str = str(old_value) if old_value is not None else None
        new_value_str = str(new_value) if new_value is not None else None
        
        # Create log entry
        log_entry = VoterChangeLog(
            voter_id=voter_id,
            epic_no=epic_no,
            user_id=user_id,
            volunteer_id=volunteer_id,
            user_type=user_type,
            user_name=user_name,
            user_email=user_email,
            action_type=action_type,
            field_changed=field_changed,
            old_value=old_value_str,
            new_value=new_value_str,
            ip_address=ip_address,
            device_info=device_info
        )
        
        db.add(log_entry)
        return log_entry
    
    @staticmethod
    def log_multiple_changes(
        db: Session,
        voter_id: int,
        epic_no: str,
        current_user: Union[User, Volunteer],
        action_type: str,
        changes: Dict[str, Dict[str, Any]],
        ip_address: Optional[str] = None,
        device_info: Optional[str] = None
    ) -> None:
        """
        Log multiple field changes at once.
        
        Args:
            changes: Dict with format {field_name: {'old': old_val, 'new': new_val}}
        """
        for field_name, values in changes.items():
            AuditLogger.log_voter_change(
                db=db,
                voter_id=voter_id,
                epic_no=epic_no,
                current_user=current_user,
                action_type=action_type,
                field_changed=field_name,
                old_value=values.get('old'),
                new_value=values.get('new'),
                ip_address=ip_address,
                device_info=device_info
            )
