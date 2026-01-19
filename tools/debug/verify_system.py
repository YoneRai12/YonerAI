import socket

# Simple health check for core ORA services.
# Emoji caused cp932 encode errors on some consoles, so keep output ASCII-only.
SERVICES = [
    ("Main Brain (vLLM)", "127.0.0.1", 8001),
    ("Voice Engine (Lazy)", "127.0.0.1", 8002),
    ("Layer Service (Lazy)", "127.0.0.1", 8003),
    ("Image Gen (ComfyUI)", "127.0.0.1", 8188),
]


def check_port(name, host, port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex((host, port))
            if result == 0:
                print(f"[OK]      {name:20} -> {host}:{port}")
                return True
            else:
                print(f"[MISS]    {name:20} -> {host}:{port}")
                return False
    except Exception as e:
        print(f"[ERROR]   {name:20} -> {e}")
        return False


if __name__ == "__main__":
    print("Checking ORA System Status...")
    print("=================================")
    all_up = True
    for name, host, port in SERVICES:
        if not check_port(name, host, port):
            all_up = False

    print("=================================")
    if all_up:
        print("System is fully operational.")
    else:
        print("Some services are down. Please run 'start_services.bat' and 'Start ORA Bot'.")

    print("\nTo test Lazy Loading:")
    print("1. Open Task Manager -> Performance -> GPU")
    print("2. Run a command (e.g., /layer)")
    print("3. Watch VRAM usage jump up, then drop back down after 5 mins.")
