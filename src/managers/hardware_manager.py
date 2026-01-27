import asyncio
import logging
import shutil
from typing import Optional

logger = logging.getLogger(__name__)

class HardwareManager:
    """
    Manages hardware resource monitoring and statistics (GPU, CPU).
    Provides safe access to system commands like nvidia-smi.
    """
    def __init__(self):
        self._nvidia_smi_path = shutil.which("nvidia-smi")
        if self._nvidia_smi_path:
            logger.info(f"HardwareManager: GPU monitoring enabled (found at {self._nvidia_smi_path})")
        else:
            logger.warning("HardwareManager: nvidia-smi not found. GPU monitoring disabled.")

    async def get_gpu_stats(self) -> Optional[str]:
        """Fetch GPU stats using nvidia-smi."""
        if not self._nvidia_smi_path:
            return "GPU Stats unavailable (Driver/Command not found)"

        try:
            # 1. Global Stats
            # name, utilization.gpu, memory.used, memory.total
            cmd1 = "nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits"
            proc1 = await asyncio.create_subprocess_shell(
                cmd1, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            out1, _ = await proc1.communicate()

            if proc1.returncode != 0:
                return "GPU Stats unavailable (Command failed)"

            gpu_info = out1.decode().strip().split(",")
            if len(gpu_info) < 4:
                return "Unknown GPU Data"

            name = gpu_info[0].strip()
            util = gpu_info[1].strip()
            mem_used = int(gpu_info[2].strip())
            mem_total = int(gpu_info[3].strip())
            mem_free = mem_total - mem_used

            text = f"**{name}**\nUtilization: {util}%\nVRAM: {mem_used}MB / {mem_total}MB (Free: {mem_free}MB)"

            # 2. Process List
            # pid, process_name
            cmd2 = "nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader"
            proc2 = await asyncio.create_subprocess_shell(
                cmd2, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            out2, _ = await proc2.communicate()

            if proc2.returncode == 0 and out2:
                lines = out2.decode().strip().splitlines()
                processes = []
                for line in lines:
                    parts = line.split(",")
                    if len(parts) >= 2:
                        pid = parts[0].strip()
                        # Clean up path to just filename
                        path = parts[1].strip()
                        exe_name = path.split("\\")[-1]
                        processes.append(f"{exe_name} ({pid})")

                if processes:
                    text += f"\nProcesses: {', '.join(processes)}"
                else:
                    text += "\nProcesses: None (or hidden)"

            return text

        except Exception as e:
            logger.error(f"Failed to get GPU stats: {e}")
            return f"Error fetching GPU stats: {e}"
