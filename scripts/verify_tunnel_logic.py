
import asyncio
import os
import subprocess
import re
import sys

# Mock config
LOG_DIR = os.path.join(os.getcwd(), "logs")
LOG_PATH = os.path.join(LOG_DIR, "cf_browser.log")
CF_BIN = os.path.abspath("tools/cloudflare/cloudflared.exe")
if not os.path.exists(CF_BIN):
    CF_BIN = "cloudflared" # Fallback

async def verify_tunnel():
    print(f"--- Verify Tunnel Logic ---")
    print(f"Log Path: {LOG_PATH}")
    print(f"Binary: {CF_BIN}")
    
    # 1. Kill Logic
    print("\n[Step 1] Killing old processes...")
    try:
        cmd = "Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -like '*localhost:8000*' } | Select-Object -ExpandProperty ProcessId"
        proc = await asyncio.create_subprocess_shell(
            f"powershell -Command \"{cmd}\"",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        pids = stdout.decode().strip().split()
        print(f"Found PIDs: {pids}")
        for pid in pids:
            if pid:
                subprocess.run(f"taskkill /PID {pid} /F", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"Killed PID: {pid}")
    except Exception as e:
        print(f"Kill failed: {e}")

    # Cleanup log
    if os.path.exists(LOG_PATH):
        os.remove(LOG_PATH)
        print("Removed old log file.")

    # 2. Start Logic
    print("\n[Step 2] Starting Tunnel (Background)...")
    try:
        cmd = [CF_BIN, "tunnel", "--url", "http://localhost:8000"]
        # Exact logic from tool_handler.py
        subprocess.Popen(
            cmd,
            stdout=open(LOG_PATH, "w"),
            stderr=subprocess.STDOUT,
            shell=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        print("Process launched.")
    except Exception as e:
        print(f"Start failed: {e}")
        return

    # 3. Poll Logic
    print("\n[Step 3] Polling for URL...")
    public_url = None
    for i in range(15):
        await asyncio.sleep(2)
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if "Too Many Requests" in content:
                    print("Error: Rate Limit detected.")
                    return
                match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", content)
                if match:
                    public_url = match.group(0)
                    print(f"Found URL: {public_url}")
                    break
        print(f"Waiting... ({i+1}/15)")

    if public_url:
        print(f"\n✅ SUCCESS! Cloudflare Tunnel is working.\nURL: {public_url}/static/operator.html")
    else:
        print("\n❌ FAILED. No URL found in logs.")
        if os.path.exists(LOG_PATH):
            print("--- Log Content ---")
            with open(LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
                print(f.read())

if __name__ == "__main__":
    if not os.path.exists("logs"):
        os.makedirs("logs")
    asyncio.run(verify_tunnel())
