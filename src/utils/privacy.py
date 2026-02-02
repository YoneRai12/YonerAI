import logging
import re
import os
from pathlib import Path


class PrivacyFilter(logging.Filter):
    """
    Filter that masks IP addresses, localhost, and file paths in log messages.
    Supports IPv4, IPv4:PORT, host='...' formats, and local path disclosure.
    """
    
    def __init__(self, name: str = ""):
        super().__init__(name)
        # Pre-calculate paths to mask
        try:
            self.cwd = os.getcwd()
            self.home = str(Path.home())
            # Normalize slashes for Windows just in case regex/strings vary
            self.cwd_normalized = self.cwd.replace("\\", "/")
            self.home_normalized = self.home.replace("\\", "/")
        except Exception:
            self.cwd = "C:\\Users\\Default"
            self.home = "C:\\Users\\Default"
            self.cwd_normalized = self.cwd.replace("\\", "/")
            self.home_normalized = self.home.replace("\\", "/")

    def filter(self, record: logging.LogRecord) -> bool:
        msg = str(record.msg)
        
        # 0. Path Masking (Critical for Privacy)
        # Order matters: Mask Root first (longer), then Home.
        # Check both raw backslash and normalized forward slash versions
        
        # Mask CWD
        if self.cwd in msg:
            msg = msg.replace(self.cwd, "[ROOT]")
        if self.cwd_normalized in msg:
            msg = msg.replace(self.cwd_normalized, "[ROOT]")
            
        # Mask HOME
        if len(self.home) > 3: # Avoid masking "C:\" or "/" logic errors
            if self.home in msg:
                msg = msg.replace(self.home, "[HOME]")
            if self.home_normalized in msg:
                msg = msg.replace(self.home_normalized, "[HOME]")

        # 1. Mask IPv4 with optional port: 127.0.0.1:8008 -> [RESTRICTED]
        msg = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?\b", "[RESTRICTED]", msg)
        
        # 2. Mask host='127.0.0.1' or host="127.0.0.1" (aiohttp specific)
        msg = re.sub(r"host=['\"]\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}['\"]", "host=[RESTRICTED]", msg)
        
        # 3. Mask Google Project IDs / Identifiers (10-12 digit numbers)
        # Avoid masking Discord IDs (18-19 digits) by bounding the length.
        msg = re.sub(r"\b\d{10,12}\b", "[RESTRICTED_ID]", msg)
        msg = re.sub(r"project\s+[0-9]+", "project [RESTRICTED_ID]", msg)

        # 4. Mask localhost and 127.0.0.1 literally just in case regex misses boundaries
        msg = msg.replace("localhost", "[RESTRICTED]").replace("127.0.0.1", "[RESTRICTED]")
        
        record.msg = msg

        # Also mask in formatted message and arguments if they exist
        if record.args:
            new_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    # Path Masking for Args
                    arg = arg.replace(self.cwd, "[ROOT]").replace(self.cwd_normalized, "[ROOT]")
                    if len(self.home) > 3:
                        arg = arg.replace(self.home, "[HOME]").replace(self.home_normalized, "[HOME]")
                        
                    # IP Masking for Args
                    arg = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?\b", "[RESTRICTED]", arg)
                    arg = arg.replace("localhost", "[RESTRICTED]").replace("127.0.0.1", "[RESTRICTED]")
                new_args.append(arg)
            record.args = tuple(new_args)

        return True
