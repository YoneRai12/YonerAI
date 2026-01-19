import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from google.auth.transport import requests as g_requests
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow

router = APIRouter()

# Dependency to get store (lazy import to avoid circular dependency)
def get_store():
    from src.web.app import get_store as _get_store
    return _get_store()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

GOOGLE_CLIENT_SECRETS_FILE = "google_client_secrets.json"
GOOGLE_SCOPES = ["openid", "https://www.googleapis.com/auth/drive.file", "email", "profile"]
GOOGLE_REDIRECT_URI = "http://localhost:8000/api/auth/google/callback" # Update with actual domain in prod


def build_flow(state: str | None = None) -> Flow:
    return Flow.from_client_secrets_file(
        GOOGLE_CLIENT_SECRETS_FILE,
        scopes=GOOGLE_SCOPES,
        redirect_uri=GOOGLE_REDIRECT_URI,
        state=state,
    )

@router.get("/auth/discord")
async def auth_discord(request: Request, code: str | None = None, state: str | None = None):
    # If no code, redirect to Google
    if code is None:
        discord_user_id = request.query_params.get("discord_user_id")
        flow = build_flow(state=discord_user_id or "")
        auth_url, _ = flow.authorization_url(prompt="consent", include_granted_scopes="true")
        return RedirectResponse(auth_url)

    # If code exists, handle Discord auth (not implemented yet per instructions)
    return {"message": "Discord auth flow not fully implemented yet."}


@router.get("/auth/google/callback")
async def auth_google_callback(request: Request, code: str, state: str | None = None):
    # We need the store. Since we can't import from app easily due to circular deps,
    # we will access it via the app instance attached to the request, or import it inside.
    from src.web.app import get_store
    store = get_store()

    flow = build_flow(state=state)
    flow.fetch_token(code=code)

    creds = flow.credentials
    request_adapter = g_requests.Request()
    idinfo = id_token.verify_oauth2_token(
        creds.id_token,
        request_adapter,
        flow.client_config["client_id"],
    )

    google_sub = idinfo["sub"]
    email = idinfo.get("email")

    # Update DB
    await store.upsert_google_user(google_sub=google_sub, email=email, credentials=creds)

    # Link Discord User
    discord_user_id = state
    if discord_user_id:
        # Validate discord_user_id is int-like
        if discord_user_id.isdigit():
             await store.link_discord_google(int(discord_user_id), google_sub)

    return RedirectResponse(url="/linked") # Redirect to a success page (to be created)


@router.post("/auth/link-code")
async def request_link_code(request: Request):
    """Generate a temporary link code for a Discord user."""
    try:
        data = await request.json()
        discord_user_id = data.get("user_id")
        if not discord_user_id:
            raise HTTPException(status_code=400, detail="Missing user_id")
            
        store = get_store()
        # Create a unique state/code
        code = str(uuid.uuid4())
        
        # Store it with expiration (e.g., 15 minutes)
        await store.start_login_state(code, discord_user_id, ttl_sec=900)
        
        # Return the auth URL that the user should visit
        # In a real app, this might be a short link or just the code
        # For ORA, we return the full URL to the web auth endpoint with state
        auth_url = f"{GOOGLE_REDIRECT_URI}?state={code}" # Wait, this is callback.
        # We need to point to the start of the flow
        # Actually, the user should visit /api/auth/discord?discord_user_id=...
        # But we want to use the code as state.
        
        # Let's construct the Google Auth URL directly or via our endpoint
        flow = build_flow(state=code)
        auth_url, _ = flow.authorization_url(prompt="consent", include_granted_scopes="true")
        
        return {"url": auth_url, "code": code}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ocr")
async def ocr_endpoint(request: Request):
    """
    Analyze an uploaded image using the same logic as the ORA Cog.
    Expects multipart/form-data with 'file'.
    """
    from src.utils import image_tools
    
    # We need to parse the body manually or use FastAPI's File
    # Since we are inside a router without explicit File param in signature above (to keep imports clean),
    # let's do it properly by importing UploadFile at top or here.
    # To avoid messing up the file structure too much, I'll use Request form.
    
    form = await request.form()
    file = form.get("file")
    
    if not file:
        return {"error": "No file provided"}
        
    content = await file.read()
    
    # Analyze
    try:
        # Use structured analysis
        result = image_tools.analyze_image_structured(content)
        return result
    except Exception as e:
        return {"error": str(e)}


@router.get("/conversations/latest")
async def get_latest_conversations(user_id: str | None = None, limit: int = 20):
    """Get recent conversations for a user (Discord ID or Google Sub). If None, returns all."""
    from src.web.app import get_store
    store = get_store()
    
    try:
        convs = await store.get_conversations(user_id, limit)
        return {"ok": True, "data": convs}
    except Exception as e:
        return {"ok": False, "error_code": "DB_ERROR", "error_message": str(e)}

@router.get("/memory/graph")
async def get_memory_graph():
    """Get the knowledge graph data."""
    import json
    from pathlib import Path
    try:
        path = Path("graph_cache.json")
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {"ok": True, "data": data}
        return {"ok": True, "data": {"nodes": [], "links": []}}
    except Exception as e:
        return {"ok": False, "error_code": "READ_ERROR", "error_message": str(e)}

@router.get("/dashboard/usage")
async def get_dashboard_usage():
    """Get global cost usage stats from CostManager state file (Aggregated)."""
    import json
    from pathlib import Path
    
    state_path = Path("L:/ORA_State/cost_state.json")
    
    # Calculate Today in JST
    # Calculate Today (Match CostManager Timezone)
    import pytz

    from src.config import COST_TZ
    
    tz = pytz.timezone(COST_TZ)
    today_str = datetime.now(tz).strftime("%Y-%m-%d")
    
    # Default Structure
    response_data = {
        "total_usd": 0.0,
        "daily_tokens": {
            "high": 0,
            "stable": 0,
            "burn": 0
        },
        "last_reset": "",
        "unlimited_mode": False,
        "unlimited_users": []
    }
    
    if not state_path.exists():
         return {"ok": True, "data": response_data, "message": "No cost state found"}
         
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        # Helper to Sum Usage
        def add_usage(bucket_key: str, bucket_data: dict, target_data: dict):
            # bucket_data structure: {"used": {"tokens_in": X, "tokens_out": Y, "usd": Z}, ...}
            # target_data: The specific dict in response_data (daily_tokens or lifetime_tokens)
            
            used = bucket_data.get("used", {})
            tokens = used.get("tokens_in", 0) + used.get("tokens_out", 0)
            usd = used.get("usd", 0.0)
            
            # Add to proper lane
            if bucket_key.startswith("high:"):
                target_data["high"] += tokens
            elif bucket_key.startswith("stable:"):
                target_data["stable"] += tokens
            elif bucket_key.startswith("burn:"):
                target_data["burn"] += tokens
            elif bucket_key.startswith("optimization:"):
                if "optimization" not in target_data:
                    target_data["optimization"] = 0
                target_data["optimization"] += tokens

            # Add to OpenAI Sum (for verifying against Dashboard)
            # RELAXED CHECK: If it contains 'openai' OR is an optimization lane (usually API)
            # We want to capture ALL API usage in this sum for the user.
            if ":openai" in bucket_key or "optimization" in bucket_key or "high" in bucket_key:
                # Exclude local manually if needed, but usually local doesn't use these lanes in CostManager
                if "openai_sum" in target_data:
                   target_data["openai_sum"] += tokens
                else:
                   target_data["openai_sum"] = tokens
            
            return usd

        # Default Structure
        response_data = {
            "total_usd": 0.0,
            "daily_tokens": {
                "high": 0, "stable": 0, "burn": 0
            },
            "lifetime_tokens": {
                "high": 0, "stable": 0, "burn": 0, "optimization": 0, "openai_sum": 0
            },
            "last_reset": datetime.now().isoformat(),
            "unlimited_mode": raw_data.get("unlimited_mode", False),
            "unlimited_users": raw_data.get("unlimited_users", [])
        }

        # 1. Process Global Buckets (Current - Daily)
        for key, bucket in raw_data.get("global_buckets", {}).items():
            if bucket.get("day") == today_str:
                usd_gain = add_usage(key, bucket, response_data["daily_tokens"])
                response_data["total_usd"] += usd_gain
            
        # 1b. Process Global History (Lifetime)
        # First, add Today's usage to Lifetime
        for key, bucket in raw_data.get("global_buckets", {}).items():
            add_usage(key, bucket, response_data["lifetime_tokens"])
        
        # Then, add History to Lifetime
        for key, history_list in raw_data.get("global_history", {}).items():
            for bucket in history_list:
                usd_gain = add_usage(key, bucket, response_data["lifetime_tokens"])
                response_data["total_usd"] += usd_gain # Accumulate lifetime USD? Or just daily USD?
                # Burn limit is cumulative, so let's track ALL usage USD here for "Lifetime USD".
                # But "Current Burn Limit" might need separate logic. 
                # For this dashboard view, "Total Spend" implies Lifetime.

        # 2. Process User Buckets (Main Source of Truth for Dashboard)
        # We assume User Buckets contain the breakdown.
        # To avoid double counting with Global (if it existed), we rely on Users here or use max.
        # Given Global seems empty/desynced, we add User usage to valid totals.
        
        for user_buckets in raw_data.get("user_buckets", {}).values():
            for key, bucket in user_buckets.items():
                if bucket.get("day") == today_str:
                    usd_gain = add_usage(key, bucket, response_data["daily_tokens"])
                    # Accumulate Total USD from Users (Wait, total_usd is usually lifetime?)
                    # If we only sum today, it's Daily Cost. If we sum all, it's Lifetime.
                    # The UI likely separates them.
                    # But the variable is `total_usd` at root.
                    # If the bug was "Not Resetting", it means Daily Tokens wasn't resetting,
                    # AND total_usd (Daily Cost?) wasnt resetting.
                    # So we should filter USD too.
                    response_data["total_usd"] += usd_gain
                
                # CRITICAL FIX: Also aggregate User Usage into Lifetime Tokens
                # This ensures that if Global History is missing/desynced, the Dashboard still shows the sum of known users.
                # add_usage adds to the target dict.
                add_usage(key, bucket, response_data["lifetime_tokens"])
                
        # 2b. User History Loop (to catch past usage not in current user_buckets)
        for user_hists in raw_data.get("user_history", {}).values():
             for key, hist_list in user_hists.items():
                 for bucket in hist_list:
                     add_usage(key, bucket, response_data["lifetime_tokens"])
                
                # Update Lifetime with User data too? 
                # If we trust user buckets, we should ensure they feed into lifetime view if needed.
                # But lifetime_tokens loop (1b) looked at Global History.
                # If Global History is empty, user history won't be seen.
                # For now, fixing "Current Estimated Cost" (total_usd) is the priority.

        # 2b. User History (Not needed for system total, but good for individual stats below)
        pass

        return {"ok": True, "data": response_data}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.get("/dashboard/history")
async def get_dashboard_history():
    """Get historical usage data (timeline) and model breakdown."""
    import json
    from pathlib import Path
    
    state_path = Path("L:/ORA_State/cost_state.json")
    if not state_path.exists():
        return {"ok": False, "error": "No cost state found"}

    try:
        with open(state_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
            
        timeline = {} # "YYYY-MM-DD" -> {high, stable, optimization, usd}
        breakdown = {} # "high" -> {"openai": 100, "total": 100}
        hourly = {} # "YYYY-MM-DDTHH" -> {hour, high, stable, optimization, burn, usd}

        def process_bucket(key, bucket, date_str):
            # 1. Update Timeline
            if date_str not in timeline:
                timeline[date_str] = {"date": date_str, "high": 0, "stable": 0, "optimization": 0, "burn": 0, "usd": 0.0}
            
            t_data = timeline[date_str]
            used = bucket.get("used", {})
            reserved = bucket.get("reserved", {})
            tokens = used.get("tokens_in", 0) + used.get("tokens_out", 0) + reserved.get("tokens_in", 0) + reserved.get("tokens_out", 0)
            usd = used.get("usd", 0.0) + reserved.get("usd", 0.0)
            
            t_data["usd"] += usd
            
            key_lower = key.lower()
            lane = "unknown"
            if key_lower.startswith("high"):
                t_data["high"] += tokens
                lane = "high"
            elif key_lower.startswith("stable"):
                t_data["stable"] += tokens
                lane = "stable"
            elif key_lower.startswith("optimization"):
                t_data["optimization"] += tokens
                lane = "optimization"
            elif key_lower.startswith("burn"):
                t_data["burn"] += tokens
                lane = "burn"

            # 2. Update Breakdown (Total Lifetime)
            if lane not in breakdown:
                breakdown[lane] = {"total": 0}
            
            breakdown[lane]["total"] += tokens
            
            # Extract Provider/Model (Format: lane:provider:model)
            parts = key_lower.split(":")
            if len(parts) >= 2:
                provider = parts[1]
                # If model is present, maybe use it? For now just provider.
                model = parts[2] if len(parts) > 2 else "default"
                label = f"{provider} ({model})"
                
                if label not in breakdown[lane]:
                    breakdown[lane][label] = 0
                breakdown[lane][label] += tokens

        def process_hourly(bucket_key, hour_map):
            key_lower = bucket_key.lower()
            lane = "unknown"
            if key_lower.startswith("high"):
                lane = "high"
            elif key_lower.startswith("stable"):
                lane = "stable"
            elif key_lower.startswith("optimization"):
                lane = "optimization"
            elif key_lower.startswith("burn"):
                lane = "burn"

            if lane == "unknown":
                return

            for hour, usage in hour_map.items():
                if hour not in hourly:
                    hourly[hour] = {"hour": hour, "high": 0, "stable": 0, "optimization": 0, "burn": 0, "usd": 0.0}
                tokens = usage.get("tokens_in", 0) + usage.get("tokens_out", 0)
                usd = usage.get("usd", 0.0)
                hourly[hour][lane] += tokens
                hourly[hour]["usd"] += usd

        # Process History
        for key, hist_list in raw_data.get("global_history", {}).items():
            for bucket in hist_list:
                process_bucket(key, bucket, bucket["day"])

        # Process Current (Today)
        for key, bucket in raw_data.get("global_buckets", {}).items():
             process_bucket(key, bucket, bucket["day"])

        # Process User History
        for user_hists in raw_data.get("user_history", {}).values():
            for key, hist_list in user_hists.items():
                for bucket in hist_list:
                    process_bucket(key, bucket, bucket["day"])

        # Process User Current Buckets
        for user_buckets in raw_data.get("user_buckets", {}).values():
            for key, bucket in user_buckets.items():
                process_bucket(key, bucket, bucket["day"])

        # Process Hourly (Global + User)
        for key, hour_map in raw_data.get("global_hourly", {}).items():
            process_hourly(key, hour_map)
        for user_hour_map in raw_data.get("user_hourly", {}).values():
            for key, hour_map in user_hour_map.items():
                process_hourly(key, hour_map)

        # Convert timeline to sorted list
        sorted_timeline = sorted(timeline.values(), key=lambda x: x["date"])
        sorted_hourly = [hourly[k] for k in sorted(hourly.keys())]

        return {"ok": True, "data": {"timeline": sorted_timeline, "breakdown": breakdown, "hourly": sorted_hourly}}
        
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.get("/dashboard/users")
async def get_dashboard_users(response: Response):
    """Get list of users with display names and stats from Memory JSONs."""
    # Force No-Cache to ensure real-time updates
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, proxy-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    import json
    from pathlib import Path

    import aiofiles
    
    MEMORY_DIR = Path("L:/ORA_Memory/users")
    users = []

    # 1. Load Discord State (Presence/Names/Guilds) FIRST
    discord_state_path = Path("L:/ORA_State/discord_state.json")
    discord_state = {"users": {}, "guilds": {}}
    if discord_state_path.exists():
        try:
            with open(discord_state_path, "r", encoding="utf-8") as f:
                discord_state = json.load(f)
        except Exception:
            pass # Sync might be writing

    try:
        if MEMORY_DIR.exists():
            for method_file in MEMORY_DIR.glob("*.json"):
                try:
                    uid = method_file.stem # Filename without extension = User ID
                    
                    async with aiofiles.open(method_file, "r", encoding="utf-8") as f:
                        content = await f.read()
                        data = json.loads(content)
                        
                        traits = data.get("traits", [])
                        
                        # Respect saved status
                        raw_status = data.get("status", "Optimized" if len(traits) > 0 else "New")

                        real_discord_id = data.get("discord_user_id", uid.split("_")[0])
                        
                        # Resolve Name/Guild if missing/unknown
                        display_name = data.get("name", "Unknown")
                        guild_name = data.get("guild_name", "Unknown Server")
                        
                        # Fallback to Discord State if data is stale/missing
                        d_user = discord_state["users"].get(real_discord_id, {})
                        if display_name in ["Unknown", ""] or display_name.startswith("User "):
                             if d_user.get("name"):
                                 display_name = d_user["name"]

                        if guild_name == "Unknown Server":
                            # Try to find guild from file name if possible (UID_GID)
                            parts = uid.split("_")
                            if len(parts) == 2:
                                gid = parts[1]
                                if gid in discord_state.get("guilds", {}):
                                    guild_name = discord_state["guilds"][gid]
                            
                            # Try to find guild from discord_state user info
                            if guild_name == "Unknown Server":
                                 d_user = discord_state["users"].get(real_discord_id, {})
                                 gid = d_user.get("guild_id")
                                 if gid and gid in discord_state.get("guilds", {}):
                                     guild_name = discord_state["guilds"][gid]

                        # Deduplication Check
                        # If we already have this (real_id, guild_name) tuple, keep the one with more points/optimized status
                        # Deduplication Logic: Prioritize Processing (Show activity) > Optimized > Error > New
                        score_base = 0
                        if raw_status.lower() == "processing": score_base = 2500
                        elif raw_status.lower() == "optimized": score_base = 2000
                        elif raw_status.lower() == "error": score_base = 1000

                        entry = {
                            "discord_user_id": method_file.stem,
                            "real_user_id": real_discord_id, 
                            "display_name": display_name,
                            "created_at": data.get("last_updated", ""), 
                            "points": len(traits), 
                            "message_count": data.get("message_count", len(data.get("last_context", []))),
                            "status": raw_status,
                            "impression": data.get("impression", None),
                            "guild_name": guild_name,
                            "banner": data.get("banner", None),
                            "traits": traits,
                            "is_nitro": d_user.get("is_nitro", False),
                            "_sort_score": score_base + len(traits)
                        }
                        users.append(entry)
                except Exception as e:
                    print(f"Error reading user file {method_file}: {e}")

        # 2. Merge with Cost Data & Find Ghost Users
        state_path = Path("L:/ORA_State/cost_state.json")
        cost_data = {}
        if state_path.exists():
             with open(state_path, "r", encoding="utf-8") as f:
                cost_data = json.load(f)
                
        # Use a set of REAL User IDs to prefer checking existence logic
        existing_real_ids = set()
        for u in users:
            uid = str(u.get("real_user_id", u["discord_user_id"]))
            existing_real_ids.add(uid)

        # 2a. Check for users who have cost activity but NO memory file yet
        all_user_buckets = cost_data.get("user_buckets", {})
        for uid in all_user_buckets:
            # Check if this user (by real_user_id) is already in our list from memory files
            # We need to handle composite IDs (UID_GID) vs simple UIDs
            real_uid_from_bucket = uid.split("_")[0] # Extract real UID from potential UID_GID
            if str(real_uid_from_bucket) not in existing_real_ids:
                # Try to resolve Name/Guild from Discord State
                d_user = discord_state["users"].get(real_uid_from_bucket, {})
                display_name = d_user.get("name", f"User {real_uid_from_bucket}"[:12] + "...")
                
                guild_id = d_user.get("guild_id")
                # Resolve Guild Name from ID
                guild_name = "Unknown Server"
                if guild_id and guild_id in discord_state.get("guilds", {}):
                    guild_name = discord_state["guilds"][guild_id]
                
                users.append({
                    "discord_user_id": uid, # Keep original bucket ID for cost lookup
                    "real_user_id": real_uid_from_bucket, # Use real UID for deduplication
                    "display_name": display_name,
                    "created_at": "",
                    "points": 0,
                    "status": "New", 
                    "impression": None,
                    "guild_name": guild_name,
                    "guild_id": guild_id,
                    "discord_status": d_user.get("status", "offline")
                })
                existing_real_ids.add(str(real_uid_from_bucket)) # Add real UID to set
                
        # 2b. Add Purely Online Users (No Memory, No Cost) - Requested by User
        for uid, d_user in discord_state.get("users", {}).items():
            if str(uid) not in existing_real_ids:
                # Add only if not already present via Memory or Cost
                guild_id = d_user.get("guild_id")
                guild_name = "Unknown Server"
                if guild_id and guild_id in discord_state.get("guilds", {}):
                    guild_name = discord_state["guilds"][guild_id]

                users.append({
                    "discord_user_id": uid,
                    "real_user_id": uid,
                    "display_name": d_user.get("name", "Unknown"),
                    "created_at": "",
                    "points": 0,
                    "status": "New",
                    "impression": None,
                    "guild_name": guild_name,
                    "guild_id": guild_id,
                    "discord_status": d_user.get("status", "offline"),
                    "is_bot": d_user.get("is_bot", False)
                })
                existing_real_ids.add(str(uid))
                
        # 3. Calculate Cost Usage for ALL Users & Inject Presence
        for u in users:
            uid = u["discord_user_id"]
            
            # Inject Presence using REAL ID (Fix for uid_gid mismatch)
            target_uid = str(u.get("real_user_id", uid))
            d_user = discord_state["users"].get(target_uid, {})
            u["discord_status"] = d_user.get("status", "offline")
            
            # Ensure is_bot is present (fallback to discord_state if not set in earlier steps)
            if "is_bot" not in u:
                u["is_bot"] = d_user.get("is_bot", False)
            
            # Fix Name if "Unknown" and we have data
            if u["display_name"] == "Unknown" and d_user.get("name"):
                u["display_name"] = d_user.get("name")
            
            # Inject URLs
            if not u.get("avatar_url"):
                u["avatar_url"] = f"https://cdn.discordapp.com/avatars/{target_uid}/{d_user.get('avatar')}.png" if d_user.get("avatar") else None
            
            # Banner Prioritization: JSON (Global/Memory) > Discord State (Live)
            banner_key = u.get("banner") or d_user.get("banner")
            u["banner_url"] = f"https://cdn.discordapp.com/banners/{target_uid}/{banner_key}.png" if banner_key else None
            # Default Structure
            u["cost_usage"] = {"high": 0, "stable": 0, "burn": 0, "total_usd": 0.0}
            
            target_id = uid
            # If composite ID (UID_GID) is not in bucket, try real_user_id (UID)
            if target_id not in all_user_buckets and "real_user_id" in u:
                target_id = u["real_user_id"]

            if target_id in all_user_buckets:
                user_specific_buckets = all_user_buckets[target_id]
                for key, bucket in user_specific_buckets.items():
                    used = bucket.get("used", {})
                    reserved = bucket.get("reserved", {})
                    tokens = used.get("tokens_in", 0) + used.get("tokens_out", 0) + reserved.get("tokens_in", 0) + reserved.get("tokens_out", 0)
                    cost = used.get("usd", 0.0) + reserved.get("usd", 0.0)
                    
                    u["cost_usage"]["total_usd"] += cost

                    bucket_key_lower = key.lower()
                    if bucket_key_lower.startswith("high"):
                        u["cost_usage"]["high"] += tokens
                    elif bucket_key_lower.startswith("stable"):
                        u["cost_usage"]["stable"] += tokens
                    elif bucket_key_lower.startswith("burn"):
                        u["cost_usage"]["burn"] += tokens
                    elif bucket_key_lower.startswith("optimization"):
                        if "optimization" not in u["cost_usage"]:
                            u["cost_usage"]["optimization"] = 0
                        u["cost_usage"]["optimization"] += tokens

                    
                    # Detect Provider
                    # key pattern: lane:provider:model or similar
                    parts = bucket_key_lower.split(":")
                    if len(parts) >= 2:
                        provider = parts[1]
                        if "providers" not in u:
                            u["providers"] = set()
                        u["providers"].add(provider)
                    
            # Determine Mode
            providers = u.get("providers", set())
            if "openai" in providers:
                u["mode"] = "API (Paid)"
            elif "local" in providers or "gemini_trial" in providers:
                u["mode"] = "Private (Local/Free)"
            else:
                u["mode"] = "Unknown"
            
            
            # Clean up set for JSON
            if "providers" in u:
                del u["providers"]
            
            # Force Pending status? NO. Only if they strictly lack a profile (handled above).
            # If they have usage but no profile: they were added as Pending.
            # If they have usage AND profile: status comes from profile (Optimized/Idle).
            pass
        
        # Deduplicate Users by (real_user_id, guild_name)
        # Keep the entry with highest _sort_score
        unique_map = {}
        for u in users:
            # Safety: Fallback to discord_user_id if real_user_id is missing
            rid = u.get("real_user_id", u["discord_user_id"])
            key = (rid, u["guild_name"])
            if key not in unique_map:
                unique_map[key] = u
            else:
                # Compare scores
                if u.get("_sort_score", 0) > unique_map[key].get("_sort_score", 0):
                    unique_map[key] = u
        
        # Determine final list
        final_users = list(unique_map.values())
        
        # Clean up internal keys
        for u in final_users:
            u.pop("_sort_score", None)

        # Global Property Sync (Fix for Header/Nitro/Impression mismatch across servers)
        # 1. Collect Best Global Props
        global_props = {}
        for u in final_users:
            rid = u.get("real_user_id")
            if not rid: continue

            if rid not in global_props:
                global_props[rid] = {"banner_url": None, "is_nitro": False, "impression": None}
            
            # Propagate Banner (First non-null wins, or prefer one with value)
            if u.get("banner_url") and not global_props[rid]["banner_url"]:
                global_props[rid]["banner_url"] = u["banner_url"]
            
            # Propagate Nitro (True wins)
            if u.get("is_nitro"):
                global_props[rid]["is_nitro"] = True

            # Propagate Impression (Prefer General Profile i.e. no underscore in ID, or just first non-null)
            # General profile usually has ID == Real ID
            is_general = str(u["discord_user_id"]) == str(rid)
            if u.get("impression"):
                # If we encounter the General Profile's impression, It wins (or at least is stored).
                # If we haven't stored any impression yet, store this one.
                # If we already have one, only overwrite if this is the General one.
                if is_general:
                     global_props[rid]["impression"] = u["impression"]
                elif not global_props[rid]["impression"]:
                     global_props[rid]["impression"] = u["impression"]

        # 2. Apply Global Props
        for u in final_users:
            rid = u.get("real_user_id")
            if rid and rid in global_props:
                props = global_props[rid]
                if props["banner_url"] and not u.get("banner_url"):
                    u["banner_url"] = props["banner_url"]
                if props["is_nitro"]:
                    u["is_nitro"] = True
                # Backfill Impression
                if props["impression"] and not u.get("impression"):
                    u["impression"] = props["impression"]
                    
        return {"ok": True, "data": final_users}

    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.post("/system/refresh_profiles")
async def trigger_refresh_profiles():
    """Trigger backend profile optimization via file watcher."""
    try:
        trigger_path = "refresh_profiles.trigger"
        # Touch file
        with open(trigger_path, "w") as f:
            f.write("trigger")
        return {"ok": True, "message": "Triggered profile refresh."}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.get("/dashboard/users/{user_id}")
async def get_user_details(user_id: str):
    """Get full details for a specific user (traits, history, context). Supports dual profiles."""
    import json
    from pathlib import Path
    
    MEMORY_DIR = Path("L:/ORA_Memory/users")
    parts = user_id.split("_")
    uid = parts[0]
    gid = parts[1] if len(parts) > 1 else None
    
    specific_data = None
    general_data = None
    
    try:
        # 1. Try Specific Profile
        if gid:
            # FIX: Check public/private suffixes matching memory.py
            path_spec = MEMORY_DIR / f"{uid}_{gid}_public.json"
            if not path_spec.exists():
                 path_spec = MEMORY_DIR / f"{uid}_{gid}_private.json"
            
            # Legacy fallback
            if not path_spec.exists():
                 path_spec = MEMORY_DIR / f"{uid}_{gid}.json"

            if path_spec.exists():
                with open(path_spec, "r", encoding="utf-8") as f:
                    specific_data = json.load(f)
                    
        # 2. Try General Profile
        path_gen = MEMORY_DIR / f"{uid}.json"
        if path_gen.exists():
            with open(path_gen, "r", encoding="utf-8") as f:
                general_data = json.load(f)
                
        if not specific_data and not general_data:
            return {"ok": False, "error": "User profile not found"}
            
        return {
            "ok": True, 
            "data": {
                "specific": specific_data,
                "general": general_data
            }
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.post("/system/refresh_profiles")
async def request_profile_refresh():
    """Trigger profile refresh via file signal for the Bot process."""
    try:
        from pathlib import Path
        # Create a trigger file that MemoryCog watches
        trigger_path = Path("refresh_profiles.trigger")
        trigger_path.touch()
        return {"ok": True, "message": "Profile refresh requested"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.get("/dashboard/history")
async def get_dashboard_history(request: Request):
    """Get historical usage data (hourly/daily) for charts."""
    try:
        if not hasattr(request.app.state, "bot") or not request.app.state.bot:
             return {"ok": False, "error": "Bot not initialized"}
        
        cm = request.app.state.bot.cost_manager
        if not cm:
             return {"ok": False, "error": "CostManager not available"}
        
        # 1. Build Hourly Data (Past 25 hours)
        # Global Hourly is Dict[lane:provider, Dict[hour_iso, Usage]]
        # We need List[{hour: iso, high: int, stable: int, optimization: int, usd: float}]
        
        hourly_map = {} # hour_iso -> {high: 0, stable: 0, ...}
        
        # Iterate all tracked keys in global_hourly
        for key, hours in cm.global_hourly.items():
            if ":" in key:
                lane, provider = key.split(":", 1)
            else:
                lane = key
            
            for h_iso, usage in hours.items():
                if h_iso not in hourly_map:
                    hourly_map[h_iso] = {"hour": h_iso, "high": 0, "stable": 0, "optimization": 0, "usd": 0.0}
                
                # Sum Tokens (In+Out)
                total_tokens = usage.tokens_in + usage.tokens_out
                if lane in hourly_map[h_iso]:
                    hourly_map[h_iso][lane] += total_tokens
                
                # Sum USD
                hourly_map[h_iso]["usd"] += usage.usd

        hourly_list = sorted(hourly_map.values(), key=lambda x: x["hour"])

        # 2. Build Daily Timeline (Past 7 days)
        # Using global_history (List[Bucket]) + global_buckets (Current Day)
        # Key: lane:provider
        
        daily_map = {} # date_iso -> {date: iso, high: 0, ...}

        # Helper to merge bucket
        def merge_bucket(lane, bucket):
            d_iso = bucket.day
            if d_iso not in daily_map:
                daily_map[d_iso] = {"date": d_iso, "high": 0, "stable": 0, "optimization": 0, "usd": 0.0}
            
            total = bucket.used.tokens_in + bucket.used.tokens_out
            if lane in daily_map[d_iso]:
                 daily_map[d_iso][lane] += total
            daily_map[d_iso]["usd"] += bucket.used.usd

        # Process History
        for key, buckets in cm.global_history.items():
            lane = key.split(":")[0] if ":" in key else key
            for b in buckets:
                merge_bucket(lane, b)

        # Process Current (Active) Buckets
        for key, bucket in cm.global_buckets.items():
            lane = key.split(":")[0] if ":" in key else key
            merge_bucket(lane, bucket)

        timeline_list = sorted(daily_map.values(), key=lambda x: x["date"])

        return {
            "ok": True,
            "data": {
                "hourly": hourly_list,
                "timeline": timeline_list
            }
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.post("/dashboard/users/{user_id}/optimize")
async def optimize_user(user_id: str):
    """Triggers forced optimization for a user."""
    # Extract real Discord ID from potential UID_GID format
    real_uid = int(user_id.split("_")[0])
    
    # Architecture Change: Write to Queue File for MemoryCog to pick up (IPC)
    import json
    import time
    from pathlib import Path
    
    parts = user_id.split("_")
    real_uid = int(parts[0])
    target_guild_id = int(parts[1]) if len(parts) > 1 else None
    
    queue_path = Path("L:/ORA_State/optimize_queue.json")
    
    try:
        # 1. Read existing queue
        queue = []
        if queue_path.exists():
            try:
                with open(queue_path, "r", encoding="utf-8") as f:
                    queue = json.load(f)
            except:
                queue = []
        
        # 2. Append new request
        queue.append({
            "user_id": real_uid,
            "guild_id": target_guild_id,
            "timestamp": time.time()
        })
        
        # 3. Write back (Atomic-ish)
        with open(queue_path, "w", encoding="utf-8") as f:
            json.dump(queue, f, indent=2)
            
        return {"status": "queued", "message": "Optimization requested via Queue"}
        
    except Exception as e:
         raise HTTPException(status_code=500, detail=f"Failed to queue optimization: {e}")

@router.post("/system/restart")
async def system_restart():
    """Restart the Bot Process (Self-Termination)."""
    # In a managed environment (systemd/Docker), exiting 0 or 1 usually triggers restart.
    import asyncio
    import sys
    
    # Schedule exit
    async def _exit():
        await asyncio.sleep(1)
        sys.exit(0)
        
    asyncio.create_task(_exit())
    return {"ok": True, "message": "Restarting system..."}

@router.post("/system/shutdown")
async def system_shutdown():
    """Shutdown the Bot Process."""
    import asyncio
    import sys
    
    async def _exit():
        await asyncio.sleep(1)
        # 0 might mean success and no restart in some configs, but usually scripts loop.
        # If we really want to stop, we might need a specific exit code or flag file.
        # For now, standard exit.
        sys.exit(0) 
        
    asyncio.create_task(_exit())
    return {"ok": True, "message": "Shutting down system..."}

@router.get("/logs/stream")
async def log_stream():
    """Simple Log Stream (Not fully implemented, returns recent logs)."""
    # For a real stream, we'd use WebSocket or SSE.
    # Here, let's just return the last 50 lines of the log file if available.
    log_path = "discord.log"
    try:
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                return {"ok": True, "logs": lines[-50:]}
        return {"ok": False, "error": "Log file not found"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.get("/dashboard/view", response_class=Response)
async def get_server_dashboard_view(token: str):
    """Render a beautiful, server-specific dashboard (HTML) SECURELY."""

    from fastapi.responses import HTMLResponse

    # 0. Validate Token
    from src.web.app import get_store
    store = get_store()
    
    guild_id = await store.validate_dashboard_token(token)
    if not guild_id:
        return HTMLResponse(
            "<h1>403 Access Denied</h1><p>Invalid or expired dashboard token. Please generate a new link using <code>/dashboard</code> in your server.</p>", 
            status_code=403
        )

    # 1. Fetch ALL users (reuse logic)
    class MockResponse:
        headers = {}
    
    res = await get_dashboard_users(MockResponse())
    if not res.get("ok"):
        return HTMLResponse(f"Error loading data: {res.get('error')}", status_code=500)
    
    all_users = res.get("data", [])
    
    # 2. Filter by Guild ID (Securely obtained from Token)
    server_users = []
    guild_name = "Unknown Server"
    
    for u in all_users:
        # Check explicit guild_id
        if str(u.get("guild_id")) == guild_id:
            server_users.append(u)
            if u.get("guild_name") and u["guild_name"] != "Unknown Server":
                guild_name = u["guild_name"]
        # Fallback: Check if UID_GID matches (though with token, this might be less relevant)
        elif "_" in str(u["discord_user_id"]):
            parts = str(u["discord_user_id"]).split("_")
            if len(parts) == 2 and parts[1] == guild_id:
                server_users.append(u)
                if u.get("guild_name") and u["guild_name"] != "Unknown Server":
                    guild_name = u["guild_name"]

    # 3. Calculate Stats
    total_users = len(server_users)
    total_cost = sum(u["cost_usage"]["total_usd"] for u in server_users)
    active_users = len([u for u in server_users if u["status"] != "New"])
    
    # 4. Generate HTML (Dark Mode, Glassmorphism)
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ORA Dashboard - {guild_name}</title>
        <style>
            :root {{
                --bg: #0f172a;
                --card-bg: rgba(30, 41, 59, 0.7);
                --text-main: #f8fafc;
                --text-sub: #94a3b8;
                --accent: #3b82f6;
                --accent-glow: rgba(59, 130, 246, 0.5);
                --sc-success: #10b981;
                --sc-warn: #f59e0b;
                --sc-danger: #ef4444;
            }}
            body {{
                background-color: var(--bg);
                background-image: radial-gradient(circle at 10% 20%, rgba(59, 130, 246, 0.1) 0%, transparent 20%),
                                  radial-gradient(circle at 90% 80%, rgba(16, 185, 129, 0.05) 0%, transparent 20%);
                color: var(--text-main);
                font-family: 'Inter', system-ui, -apple-system, sans-serif;
                margin: 0;
                padding: 40px;
                min-height: 100vh;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
            }}
            header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 40px;
                border-bottom: 1px solid rgba(255,255,255,0.1);
                padding-bottom: 20px;
            }}
            h1 {{
                font-size: 2.5rem;
                font-weight: 800;
                background: linear-gradient(135deg, #fff 0%, #94a3b8 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin: 0;
            }}
            
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 40px;
            }}
            .stat-card {{
                background: var(--card-bg);
                backdrop-filter: blur(12px);
                border: 1px solid rgba(255,255,255,0.05);
                border-radius: 16px;
                padding: 24px;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
                transition: transform 0.2s;
            }}
            .stat-card:hover {{
                transform: translateY(-2px);
                border-color: rgba(255,255,255,0.1);
            }}
            .stat-label {{ color: var(--text-sub); font-size: 0.9rem; margin-bottom: 8px; }}
            .stat-value {{ font-size: 2rem; font-weight: 700; color: #fff; }}
            
            .users-table {{
                width: 100%;
                border-collapse: collapse;
                background: var(--card-bg);
                backdrop-filter: blur(12px);
                border-radius: 16px;
                overflow: hidden;
                border: 1px solid rgba(255,255,255,0.05);
            }}
            th, td {{
                padding: 16px 24px;
                text-align: left;
                border-bottom: 1px solid rgba(255,255,255,0.05);
            }}
            th {{
                background: rgba(0,0,0,0.2);
                color: var(--text-sub);
                font-weight: 600;
                font-size: 0.85rem;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }}
            tr:last-child td {{ border-bottom: none; }}
            tr:hover td {{ background: rgba(255,255,255,0.02); }}
            
            .avatar {{
                width: 32px;
                height: 32px;
                border-radius: 50%;
                vertical-align: middle;
                margin-right: 12px;
                border: 2px solid rgba(255,255,255,0.1);
            }}
            .badge {{
                display: inline-block;
                padding: 4px 10px;
                border-radius: 20px;
                font-size: 0.75rem;
                font-weight: 600;
            }}
            .badge-success {{ background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.2); }}
            .badge-warn {{ background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.2); }}
            .badge-neutral {{ background: rgba(148, 163, 184, 0.2); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.2); }}
            
            .cost {{ font-family: 'SF Mono', 'Roboto Mono', monospace; color: var(--sc-warn); }}
            
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <div>
                    <h1>{guild_name}</h1>
                    <span style="color: var(--text-sub)">Server Dashboard</span>
                </div>
                <div style="text-align: right">
                     <span class="badge badge-success">SECURE VIEW</span>
                     <span class="badge badge-neutral">ID: {guild_id}</span>
                </div>
            </header>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">Total Users</div>
                    <div class="stat-value">{total_users}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Active Profiles</div>
                    <div class="stat-value">{active_users}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">AI Cost (Est.)</div>
                    <div class="stat-value" style="color: #fbbf24">${total_cost:.4f}</div>
                </div>
            </div>
            
            <h2 style="margin-bottom: 20px; font-weight: 600;">Member Activity</h2>
            
            <table class="users-table">
                <thead>
                    <tr>
                        <th>User</th>
                        <th>Status</th>
                        <th>Points</th>
                        <th>AI Cost</th>
                        <th>Last Active</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    for u in server_users:
        avatar = u.get("avatar_url") or "https://cdn.discordapp.com/embed/avatars/0.png"
        status = u.get("status", "New")
        badge_class = "badge-neutral"
        if status == "Optimized": badge_class = "badge-success"
        elif status == "Processing": badge_class = "badge-warn"
        
        cost = u["cost_usage"]["total_usd"]
        
        html += f"""
                    <tr>
                        <td>
                            <img src="{avatar}" class="avatar" alt="av">
                            {u['display_name']}
                        </td>
                        <td><span class="badge {{badge_class}}">{status}</span></td>
                        <td>{u['points']}</td>
                        <td class="cost">${cost:.4f}</td>
                        <td style="color: var(--text-sub)">{u.get('created_at', 'N/A')[:16]}</td>
                    </tr>
        """
        
    html += """
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html, status_code=200)
