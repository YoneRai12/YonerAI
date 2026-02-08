from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = (os.getenv("ORA_RELAY_HOST") or "127.0.0.1").strip()
    port = int((os.getenv("ORA_RELAY_PORT") or "9010").strip() or "9010")
    ws_max_size = int((os.getenv("ORA_RELAY_MAX_MSG_BYTES") or "1048576").strip() or "1048576")
    uvicorn.run(
        "src.relay.app:app",
        host=host,
        port=port,
        log_level="info",
        access_log=False,
        ws_max_size=ws_max_size,
    )


if __name__ == "__main__":
    main()
