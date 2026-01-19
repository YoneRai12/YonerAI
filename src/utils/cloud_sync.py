import logging
import os
from typing import Any, Dict, Optional

import firebase_admin
from firebase_admin import credentials, firestore

logger = logging.getLogger(__name__)

class CloudSyncManager:
    """Handles synchronization between local state and Firebase/Firestore."""

    def __init__(self, service_account_path: Optional[str] = None):
        self.db = None
        self.enabled = False
        
        # Use provided path or environment variable
        path = service_account_path or os.getenv("FIREBASE_SERVICE_ACCOUNT")
        if not path:
            logger.info("Firebase Service Account key not found. Cloud Sync is disabled.")
            return

        try:
            if not firebase_admin._apps:
                cred = credentials.Certificate(path)
                firebase_admin.initialize_app(cred)
            self.db = firestore.client()
            self.enabled = True
            logger.info("Cloud Sync initialized successfully (Firebase).")
        except Exception as e:
            logger.error(f"Failed to initialize Cloud Sync: {e}")

    async def sync_user_data(self, user_id: str, data: Dict[str, Any]):
        """Sync user personality/memory to Firestore."""
        if not self.enabled or not self.db:
            return

        try:
            # Firestore doesn't support async natively in the standard admin SDK easily,
            # so we run it in a thread or use the async client if available.
            # For simplicity in this ORA implementation, we'll use the sync client 
            # as it's often called from background tasks anyway.
            doc_ref = self.db.collection("users").document(user_id)
            doc_ref.set(data, merge=True)
            logger.debug(f"Synced user {user_id} to Cloud.")
        except Exception as e:
            logger.error(f"Cloud Sync failed for user {user_id}: {e}")

    async def sync_channel_data(self, channel_id: str, data: Dict[str, Any]):
        """Sync channel-level memory to Firestore."""
        if not self.enabled or not self.db:
            return

        try:
            doc_ref = self.db.collection("channels").document(channel_id)
            doc_ref.set(data, merge=True)
            logger.debug(f"Synced channel {channel_id} to Cloud.")
        except Exception as e:
            logger.error(f"Cloud Sync failed for channel {channel_id}: {e}")

# Singleton instance
cloud_sync = CloudSyncManager()
