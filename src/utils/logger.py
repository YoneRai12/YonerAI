import logging
import os
from logging import Handler


class GuildLogger:
    """
    Manager for dynamic guild-specific logging.
    Maintains a registry of loggers for each guild to avoid handler duplication.
    """

    _loggers = {}
    _l_log_dir = r"L:\ORA_Logs\guilds"

    @classmethod
    def get_logger(cls, guild_id: int | str) -> logging.Logger:
        """
        Get or create a logger for a specific guild.
        Logs will be saved to L:\ORA_Logs\guilds\{guild_id}.log
        """
        guild_id_str = str(guild_id)
        logger_name = f"guild_{guild_id_str}"

        if logger_name in cls._loggers:
            return cls._loggers[logger_name]

        # Ensure directory exists
        if not os.path.exists(cls._l_log_dir):
            os.makedirs(cls._l_log_dir, exist_ok=True)

        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)

        # Avoid duplicate handlers if get_logger called multiple times
        if not logger.handlers:
            log_file = os.path.join(cls._l_log_dir, f"{guild_id_str}.log")

            # Use RotatingFileHandler
            handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=5 * 1024 * 1024,  # 5MB
                backupCount=5,
                encoding="utf-8",
            )

            # Use the standard formatting
            formatter = logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%SZ"
            )
            # Use ISO8601UTCFormatter if available, effectively defaulting to standard for now
            # to avoid circular imports or complex referencing.

            handler.setFormatter(formatter)
            logger.addHandler(handler)

            # Don't propagate to root to avoid spamming main logs with guild chat junk if not needed
            # But user requested "ALL" log to have everything.
            # If we want it in ALL log, we should propagate OR add a specific All handler to this logger.
            # For now, let's propagate but assume the filtering in main config handles global noise.
            # Actually, user wants "All logged in one place" too.
            logger.propagate = True

        cls._loggers[logger_name] = logger
        cls._loggers[logger_name] = logger
        return logger

    # Global Queue for Discord Forwarding
    queue = __import__("asyncio").Queue()


class QueueHandler(Handler):
    """
    Non-blocking handler that pushes LogRecord to an asyncio.Queue.
    Consumed by SystemCog for Discord channel reporting.
    """

    def __init__(self, queue):
        super().__init__()
        self.queue = queue

    def emit(self, record):
        try:
            self.queue.put_nowait(record)
        except Exception:
            self.handleError(record)
