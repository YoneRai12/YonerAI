import pytest
import asyncio
import os
import sqlite3
from unittest.mock import MagicMock, patch, ANY
from src.storage import Store

@pytest.mark.asyncio
async def test_backup_success():
    store = Store("test.db")
    
    # Mock os.path.exists to return True for db path and L: drive check
    # We need to be careful with os.path.exists calls.
    # The code checks self._db_path, then "L:/", then final_path.
    
    def side_effect_exists(path):
        if path == "test.db": return True
        if path == "L:/": return False # Force local backup for simplicity
        return False
        
    with patch("os.path.exists", side_effect=side_effect_exists), \
         patch("src.storage.sqlite3") as mock_sqlite, \
         patch("os.replace") as mock_replace, \
         patch("os.remove") as mock_remove, \
         patch("pathlib.Path.mkdir") as mock_mkdir, \
         patch("pathlib.Path.glob") as mock_glob:
        
        # Setup mocks
        mock_src_conn = MagicMock()
        mock_dst_conn = MagicMock()
        mock_verify_conn = MagicMock()
        
        # sqlite3.connect side effect to return different mocks
        # Order: src, dst, verify
        mock_sqlite.connect.side_effect = [mock_src_conn, mock_dst_conn, mock_verify_conn]
        
        # Integrity check returns "ok"
        mock_verify_conn.cursor.return_value.fetchone.return_value = ["ok"]
        
        # Run backup
        await store.backup()
        
        # Verify backup called
        mock_src_conn.backup.assert_called_once()
        
        # Verify integrity check
        mock_verify_conn.cursor.return_value.execute.assert_called_with("PRAGMA integrity_check")
        
        # Verify replace called (atomic switch)
        mock_replace.assert_called_once()
        args, _ = mock_replace.call_args
        # args[0] is Path object, convert to str or check name
        assert str(args[0]).endswith(".tmp")
        assert str(args[1]).endswith(".sqlite")

@pytest.mark.asyncio
async def test_backup_integrity_failure():
    store = Store("test.db")
    
    def side_effect_exists(path):
        if path == "test.db": return True
        if path == "L:/": return False
        return False

    with patch("os.path.exists", side_effect=side_effect_exists), \
         patch("src.storage.sqlite3") as mock_sqlite, \
         patch("os.replace") as mock_replace, \
         patch("os.rename") as mock_rename, \
         patch("pathlib.Path.mkdir"):
        
        mock_src_conn = MagicMock()
        mock_dst_conn = MagicMock()
        mock_verify_conn = MagicMock()
        mock_sqlite.connect.side_effect = [mock_src_conn, mock_dst_conn, mock_verify_conn]
        
        # Integrity check returns "corrupt"
        mock_verify_conn.cursor.return_value.fetchone.return_value = ["corrupt"]
        
        await store.backup()
        
        # Verify replace called for corrupt file
        mock_replace.assert_called_once()
        args, _ = mock_replace.call_args
        assert str(args[1]).endswith(".corrupt")
        
        # Verify rename NOT called (since we use replace now)
        mock_rename.assert_not_called()
