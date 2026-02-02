import logging
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from src.utils.privacy import PrivacyFilter

def test_privacy_filter():
    print("--- Testing PrivacyFilter ---")
    
    # Setup record
    cwd = os.getcwd()
    print(f"Current Working Directory: {cwd}")
    
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.INFO)
    
    # Mock LogRecord
    # We test filter logic directly
    pf = PrivacyFilter()
    
    # Test Case 1: CWD masking
    msg = f"Error occurred in file: {cwd}\\src\\main.py"
    record = logging.LogRecord("test", logging.INFO, "path/to/file.py", 10, msg, (), None)
    
    pf.filter(record)
    print(f"Original: {msg}")
    print(f"Filtered: {record.msg}")
    
    if "[ROOT]" in record.msg and cwd not in record.msg:
        print("✅ CWD Masking Passed")
    else:
        print("❌ CWD Masking Failed")

    # Test Case 2: Normalized Path (Forward Slash)
    cwd_norm = cwd.replace("\\", "/")
    msg_norm = f"Error in {cwd_norm}/src/main.py"
    record_norm = logging.LogRecord("test", logging.INFO, "path", 10, msg_norm, (), None)
    
    pf.filter(record_norm)
    print(f"Original (Norm): {msg_norm}")
    print(f"Filtered (Norm): {record_norm.msg}")
    
    if "[ROOT]" in record_norm.msg and cwd_norm not in record_norm.msg:
        print("✅ CWD Normalized Masking Passed")
    else:
        print("❌ CWD Normalized Masking Failed")

if __name__ == "__main__":
    test_privacy_filter()
