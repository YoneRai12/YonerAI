import os
import time
import subprocess
import asyncio
import logging
import psutil

# Configure Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ResourceGuard")

class ResourceManager:
    """
    Layer 2: Resource Manager (The Guard Dog)
    Ensures only ONE heavy GPU process runs at a time.
    Enforces 'Absolute Load/Unload' via Process Termination.
    """
    def __init__(self):
        self.current_context = "none" # "llm", "image", "video", "none"
        self.gaming_mode = False # State flag
        self.ports = {
            "llm": 8001,
            "image": 8188,
            "video": 8189, # Reserved for separated video instance
            "manager": 5000 # Placeholder
        }
        self.scripts = {
            "llm": os.path.abspath("start_vllm.bat"),
            "image": os.path.abspath("run_comfy_gpu.bat"), # We need to create this specifically for GPU run? Or use update_comfy.bat? No, usually run_nvidia_gpu.bat
            # Assuming standard Comfy run script exists or we use the user's batch file.
            # User has 'update_comfy.bat' running in logs, but likely uses 'run_nvidia_gpu.bat' for launch.
            # I'll default to looking for run_nvidia_gpu.bat in Comfy folder later.
        }
        # Hardcoded paths for now - should be config driven ideally
        self.comfy_dir = r"L:\\ComfyUI_windows_portable\\ComfyUI" # Inferred from previous logs? Or desktop?
        # Re-inferring from User logs: "C:\Users\YoneRai12\Desktop\ORADiscordBOT-main3" is bot dir.
        # "L:\ComfyUI\custom_nodes\..." seen in logs.
        # User migrated to L drive.
        self.comfy_bat = r"L:\ComfyUI\run_nvidia_gpu.bat" 
        
        # Override with exact paths found in system if possible, but for now hardcode common setup
        if not os.path.exists(self.comfy_bat):
             # Fallback to local desktop if L drive path fails (safety)
             self.comfy_bat = os.path.join(os.getcwd(), "run_comfy.bat")

        # STARTUP ADOPTION LOGIC
        # Check if vLLM was started externally (by Launcher)
        startup_mode = os.environ.get("ORA_STARTUP_MODE")
        if startup_mode:
            logger.info(f"🚀 Detected Launcher Startup Mode: {startup_mode}")
            # We assume the launcher started it. We need to verify if port 8001 is active.
            # However, since this is async init, we can't await here.
            # We will flag it for the first 'switch_context' call.
            self.startup_mode_pending = startup_mode
            if startup_mode == "gaming":
                self.gaming_mode = True
        else:
            self.startup_mode_pending = None

    async def switch_context(self, target: str):
        """
        Main API: Switches the active GPU workload.
        """
        if self.current_context == target:
            logger.info(f"Context is already {target}. No action needed.")
            return

        logging.info(f"🚨 SWITCHING CONTEXT: {self.current_context} -> {target}")

        # STARTUP ADOPTION CHECK
        if target == "llm" and self.startup_mode_pending:
            logger.info(f"🔍 Checking for Startup Process ({self.startup_mode_pending})...")
            # vLLM takes time to load 30B model. Give it 2 minutes to open the port.
            if await self.wait_for_port(self.ports["llm"], timeout=120):
                logger.info(f"✅ Startup Process Adopted! Skipping kill/launch sequence.")
                self.current_context = "llm"
                self.startup_mode_pending = None
                return
            else:
                logger.warning("⚠️ Startup Process Not Found (Port Closed). Proceeding with standard launch.")
                self.startup_mode_pending = None

        # 1. KILL EVERYTHING (The "Absolute" Rule)
        # We don't trust "what was running". We clean the house.
        await self.kill_process_on_port(self.ports["llm"])
        await self.kill_process_on_port(self.ports["image"])
        
        # 2. Wait for VRAM to settle (Magic Wait)
        # Windows Driver can lag. 2 seconds is usually safe.
        await asyncio.sleep(2)

        # 3. Start Target
        if target == "llm":
            await self.start_llm()
        elif target == "image":
            await self.start_comfy()
        elif target == "none":
            pass
        else:
            logger.error(f"Unknown context target: {target}")
            return

        self.current_context = target
        logger.info(f"✅ Context Switched to {target}")

    async def kill_process_on_port(self, port: int):
        """
        Terminates any process listening on the given port using Windows 'netstat' & 'taskkill'.
        """
        logger.info(f"🔫 Killing process on port {port}...")
        try:
            # Find PID
            # netstat -ano | findstr :PORT
            cmd = f"netstat -ano | findstr :{port}"
            process = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await process.communicate()
            
            if not stdout:
                logger.info(f"No process found on port {port}.")
                return

            # Parse PIDs (lines look like: "TCP 0.0.0.0:8000 ... LISTENING 1234")
            lines = stdout.decode().strip().split('\n')
            pids = set()
            for line in lines:
                parts = line.split()
                if len(parts) > 4:
                    pid = parts[-1]
                    if pid.isdigit() and int(pid) > 0:
                        pids.add(pid)
            
            for pid in pids:
                logger.info(f"Found PID {pid}. Terminating...")
                subprocess.run(f"taskkill /F /PID {pid}", shell=True, check=False)
                
        except Exception as e:
            logger.error(f"Error killing process on port {port}: {e}")

    async def start_llm(self, specific_mode: str = None):
        """
        Starts vLLM using the appropriate batch file.
        args:
            specific_mode: Optional force override (e.g. 'thinking')
        """
        from ..config import Config
        config = Config.load()
        
        # Determine Mode
        mode = "instruct" # Default
        
        if self.gaming_mode:
            mode = "gaming"
        elif specific_mode:
            mode = specific_mode
            
        script_name = config.model_modes.get(mode, "start_vllm_instruct.bat")
        title = f"ORA_LLM_{mode.upper()}"
            
        script_path = os.path.abspath(script_name)
        if not os.path.exists(script_path):
            logger.error(f"LLM Script not found for mode {mode}: {script_path}")
            # Fallback to default
            script_path = os.path.abspath("start_vllm.bat")
            
        logger.info(f"🚀 Starting Orchestrator LLM ({title})...")
        
        # Launch visible window (Foreground)
        cmd = f'start "{title}" "{script_path}"'
        subprocess.Popen(cmd, shell=True)
        
        # Wait for Port 8001 to be live
        await self.wait_for_port(8001)

    async def switch_model(self, mode_name: str):
        """
        Hot-swaps the running vLLM process to the target mode.
        """
        logger.info(f"🔀 HOT-SWAP REQUESTED: Switching to {mode_name.upper()}...")
        
        # 1. Kill current LLM
        await self.kill_process_on_port(self.ports["llm"])
        await asyncio.sleep(2) # Wait for VRAM release
        
        # 2. Start new LLM
        await self.start_llm(specific_mode=mode_name)
        self.current_context = "llm"

    async def start_comfy(self):
        """Starts ComfyUI."""
        target_bat = os.path.abspath("start_comfy.bat")
        
        if not os.path.exists(target_bat):
             logger.error("start_comfy.bat not found!")
             return

        logger.info(f"🎨 Starting ComfyUI ({target_bat})...")
        # Launch minimized
        subprocess.Popen(f'start /min "ORA_Comfy" "{target_bat}"', shell=True)
        await self.wait_for_port(8188)

    async def wait_for_port(self, port: int, timeout=60):
        """Polls for a port to become active."""
        logger.info(f"Waiting for port {port}...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Simple connect test? or netstat?
                # Netstat is heavier. 
                # Let's use asyncio.open_connection
                try:
                    _, writer = await asyncio.open_connection('127.0.0.1', port)
                    writer.close()
                    await writer.wait_closed()
                    logger.info(f"Port {port} is active!")
                    return True
                except (ConnectionRefusedError, OSError):
                    await asyncio.sleep(1)
            except Exception:
                await asyncio.sleep(1)
        
        
        logger.warning(f"Timed out waiting for port {port}!")
        return False

    async def set_gaming_mode(self, enabled: bool):
        """
        Toggles Gaming Mode (Low VRAM usage).
        """
        if self.gaming_mode == enabled:
            return

        logger.info(f"🎮 Gaming Mode Toggled: {enabled}")
        self.gaming_mode = enabled
        
        # If LLM is running, we need to restart it to apply model change
        if self.current_context == "llm":
            logger.info("🔄 Restarting LLM to apply Gaming Mode...")
            await self.switch_context("none") # Stop it
            await self.switch_context("llm")  # Start it (will pick up new mode)
