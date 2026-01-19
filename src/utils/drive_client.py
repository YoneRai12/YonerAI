from __future__ import annotations

import os
from typing import Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def build_drive(credentials: Credentials):
    return build("drive", "v3", credentials=credentials)


def create_folder(service, name: str, parent_id: Optional[str] = None) -> str:
    file_metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        file_metadata["parents"] = [parent_id]

    folder = service.files().create(body=file_metadata, fields="id", supportsAllDrives=True).execute()
    return folder["id"]


def upload_file(service, file_path: str, folder_id: str) -> str:
    file_metadata = {
        "name": os.path.basename(file_path),
        "parents": [folder_id],
    }
    media = MediaFileUpload(file_path, resumable=True)

    file = (
        service.files()
        .create(
            body=file_metadata,
            media_body=media,
            fields="id",
            supportsAllDrives=True,
        )
        .execute()
    )
    return file["id"]


class DriveClient:
    """Wrapper for Google Drive API operations."""

    def __init__(self, credentials: Optional[Credentials] = None):
        self.credentials = credentials
        self.service = None
        if credentials:
            self.service = build_drive(credentials)

    def set_credentials(self, credentials: Credentials) -> None:
        """Update credentials and rebuild service."""
        self.credentials = credentials
        self.service = build_drive(credentials)

    def create_folder(self, name: str, parent_id: Optional[str] = None) -> str:
        """Create a folder."""
        if not self.service:
            raise RuntimeError("Drive service not initialized. Set credentials first.")
        return create_folder(self.service, name, parent_id)

    def upload_file(self, file_path: str, folder_id: str) -> str:
        """Upload a file."""
        if not self.service:
            raise RuntimeError("Drive service not initialized. Set credentials first.")
        return upload_file(self.service, file_path, folder_id)
