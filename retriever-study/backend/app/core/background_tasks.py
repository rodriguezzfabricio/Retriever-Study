
from datetime import datetime, timedelta
from app.data.database import db
from app.core.logging_config import get_logger

logger = get_logger(__name__)

def check_group_expiration():
    """Checks for groups that are about to expire and logs a notification."""
    logger.info("Running group expiration check...")
    groups = db.get_all_groups()
    for group in groups:
        if group.expires_at:
            try:
                expires_at = datetime.fromisoformat(group.expires_at)
                if expires_at - timedelta(days=14) < datetime.now() < expires_at:
                    logger.info(f"Group '{group.title}' (ID: {group.groupId}) is expiring on {group.expires_at}. Sending notification...")
                    # In a real application, you would send an email or in-app notification here.
            except ValueError:
                logger.warning(f"Could not parse expires_at for group {group.groupId}: {group.expires_at}")
