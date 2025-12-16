
import asyncio
import logging
from typing import List, Callable, Optional, Set
import psutil

logger = logging.getLogger(__name__)

class GameWatcher:
    """
    Monitors running processes for known games and triggers callbacks on state change.
    Designed to help the bot downgrade resources (e.g. switch to lighter LLM) when the user is gaming.
    """
    def __init__(
        self, 
        target_processes: List[str], 
        on_game_start: Callable[[], None],
        on_game_end: Callable[[], None],
        poll_interval: int = 30
    ):
        self.target_processes = set(p.lower() for p in target_processes)
        self.on_game_start = on_game_start
        self.on_game_end = on_game_end
        self.poll_interval = poll_interval
        self._is_gaming = False
        self._stop_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        # Debounce: require 2 consecutive checks to confirm state change to avoid rapid flickers
        self._consecutive_detection_count = 0
        self._required_consecutive_checks = 2

    def start(self):
        """Start the monitoring loop."""
        if self._task is None:
            self._stop_event.clear()
            self._task = asyncio.create_task(self._monitor_loop())
            logger.info(f"GameWatcher using processes: {self.target_processes}")

    def stop(self):
        """Stop the monitoring loop."""
        if self._task:
            self._stop_event.set()
            self._task.cancel()
            self._task = None
            logger.info("GameWatcher stopped.")

    async def _monitor_loop(self):
        logger.info("GameWatcher started monitoring.")
        while not self._stop_event.is_set():
            try:
                is_running = await self._check_processes()
                
                # State Machine with Debounce
                if is_running:
                    if not self._is_gaming:
                        self._consecutive_detection_count += 1
                        if self._consecutive_detection_count >= self._required_consecutive_checks:
                            logger.info("Game detected! Triggering Game Mode.")
                            self._is_gaming = True
                            if self.on_game_start:
                                try:
                                    if asyncio.iscoroutinefunction(self.on_game_start):
                                        await self.on_game_start()
                                    else:
                                        self.on_game_start()
                                except Exception as e:
                                    logger.error(f"Error in on_game_start callback: {e}")
                else:
                    if self._is_gaming:
                        # Immediate switch off? Or also debounce?
                        # Let's debounce switch off too to safe guard against crash/restart
                        self._consecutive_detection_count -= 1
                        if self._consecutive_detection_count <= 0:
                            logger.info("Game closed. Disabling Game Mode.")
                            self._is_gaming = False
                            if self.on_game_end:
                                try:
                                    if asyncio.iscoroutinefunction(self.on_game_end):
                                        await self.on_game_end()
                                    else:
                                        self.on_game_end()
                                except Exception as e:
                                    logger.error(f"Error in on_game_end callback: {e}")
                    else:
                        # Reset counter if not gaming and not detected
                        self._consecutive_detection_count = 0

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in GameWatcher check: {e}")
            
            await asyncio.sleep(self.poll_interval)

    async def _check_processes(self) -> bool:
        """Check if any target process is running using psutil."""
        # Run in executor because psutil can be synchronous and slow iterating all processes
        return await asyncio.to_thread(self._check_processes_sync)

    def _check_processes_sync(self) -> bool:
        try:
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info['name'] and proc.info['name'].lower() in self.target_processes:
                        # logger.debug(f"Found game process: {proc.info['name']}")
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        except Exception:
            pass
        return False
