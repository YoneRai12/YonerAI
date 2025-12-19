#!/usr/bin/env python3
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.request
import urllib.error
import datetime
import signal
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Pattern


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


class HardwareDetector:
    @staticmethod
    def get_specs() -> Dict[str, Any]:
        specs = {
            "cpu_cores": os.cpu_count() or 4,
            "ram_gb": 8,
            "gpu_vram_gb": 0,
            "gpu_name": "Unknown"
        }
        
        # 1. Detect RAM (Windows)
        if os.name == "nt":
            try:
                import ctypes
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                specs["ram_gb"] = int(stat.ullTotalPhys / (1024**3))
            except Exception:
                pass
        
        # 2. Detect GPU VRAM (nvidia-smi)
        try:
            # Try to get VRAM in MiB
            cmd = ["nvidia-smi", "--query-gpu=memory.total,name", "--format=csv,noheader,nounits"]
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
            if proc.returncode == 0:
                lines = proc.stdout.strip().splitlines()
                if lines:
                    # Take the first GPU (usually the primary one)
                    # Output format: "16384, NVIDIA GeForce RTX 5080"
                    parts = lines[0].split(",", 1)
                    if len(parts) >= 1:
                        specs["gpu_vram_gb"] = int(int(parts[0].strip()) / 1024)
                    if len(parts) >= 2:
                        specs["gpu_name"] = parts[1].strip()
        except Exception:
            pass
            
        return specs

@dataclasses.dataclass
class Config:
    project_root: Path = dataclasses.field(default_factory=lambda: Path.cwd())
    train_cmd: List[str] = dataclasses.field(
        default_factory=lambda: shlex.split(os.environ.get("PHOENIX_TRAIN_CMD", "python train_lora.py"))
    )
    
    # ... (Hardware Detection for Auto-Tuning)
    specs: Dict[str, Any] = dataclasses.field(default_factory=HardwareDetector.get_specs)

    test_cmd: List[str] = dataclasses.field(
        default_factory=lambda: shlex.split(os.environ.get("PHOENIX_TEST_CMD", ""))
    )
    require_test_pass: bool = os.environ.get("PHOENIX_REQUIRE_TEST_PASS", "1") == "1"

    fallback_llm_cmd: List[str] = dataclasses.field(
        default_factory=lambda: [] # Handled in post_init for multiple commands
    )
    fallback_llm_type: str = os.environ.get("PHOENIX_FALLBACK_LLM_TYPE", "cli") # cli or api
    fallback_llm_url: str = os.environ.get("PHOENIX_FALLBACK_LLM_URL", "http://localhost:1234/v1/chat/completions")
    fallback_llm_model: str = os.environ.get("PHOENIX_FALLBACK_LLM_MODEL", "") # Empty = auto-detect

    primary_llm: str = dataclasses.field(default_factory=lambda: os.environ.get("PHOENIX_PRIMARY", "gemini_cli"))
    max_retries_per_signature: int = int(os.environ.get("PHOENIX_MAX_RETRIES_PER_SIGNATURE", "3"))
    max_total_retries: int = int(os.environ.get("PHOENIX_MAX_TOTAL_RETRIES", "10"))
    
    # Advanced Features
    discord_webhook_url: str = os.environ.get("PHOENIX_DISCORD_WEBHOOK_URL", "")
    discord_bot_token: str = os.environ.get("PHOENIX_DISCORD_BOT_TOKEN", "")
    discord_channel_id: str = os.environ.get("PHOENIX_DISCORD_CHANNEL_ID", "")
    
    git_auto_commit: bool = os.environ.get("PHOENIX_GIT_COMMIT", "0") == "1"
    report_dir: Path = dataclasses.field(default_factory=lambda: Path(".phoenix_cli/reports"))
    
    # Final Polish
    patch_mode: str = os.environ.get("PHOENIX_PATCH_MODE", "auto") # auto, restart-only, analyze-only
    fallback_max_per_run: int = int(os.environ.get("PHOENIX_FALLBACK_MAX_PER_RUN", "5"))
    
    # Data & Verification
    data_dir: Path = dataclasses.field(default_factory=lambda: Path(os.environ.get("PHOENIX_DATA_DIR", "data")))
    val_loss_regex: str = os.environ.get("PHOENIX_VAL_LOSS_REGEX", r"(?:val_loss|Val Loss)[:=]\s*([\d\.]+)")
    
    # Safety Guards
    max_gpu_temp: int = int(os.environ.get("PHOENIX_MAX_GPU_TEMP", "85"))
    min_disk_gb: int = int(os.environ.get("PHOENIX_MIN_DISK_GB", "10"))
    
    # ETA & Scheduling
    progress_regex: str = os.environ.get("PHOENIX_PROGRESS_REGEX", r"(\d+)/(\d+)") # Matches "Step 10/100" or "Epoch 1/10"
    loss_regex: str = os.environ.get("PHOENIX_LOSS_REGEX", r"(?:loss|Loss)[:=]\s*([\d\.]+)") # Matches "loss: 0.123" or "Loss=0.123"
    notify_every_steps: int = int(os.environ.get("PHOENIX_NOTIFY_STEPS", "0")) # 0 = disable step-based, use time-based (60m)
    deadline_time: str = os.environ.get("PHOENIX_DEADLINE", "") # HH:MM format (24h)
    kwh_price: float = float(os.environ.get("PHOENIX_KWH_PRICE", "0.03")) # USD/kWh 
    
    # Auto-tune log tail based on RAM
    # If RAM > 32GB, we can afford larger buffers.
    log_tail_lines: int = dataclasses.field(init=False)
    
    dry_run: bool = os.environ.get("PHOENIX_DRY_RUN", "0") == "1"
    log_format: str = os.environ.get("PHOENIX_LOG_FORMAT", "json")

    state_path: Path = dataclasses.field(default_factory=lambda: Path(".phoenix_cli/state.json"))
    backups_dir: Path = dataclasses.field(default_factory=lambda: Path(".phoenix_cli/backups"))
    log_path: Path = dataclasses.field(default_factory=lambda: Path(".phoenix_cli/run.log"))
    lock_path: Path = dataclasses.field(default_factory=lambda: Path(".phoenix_cli/lock"))

    # Safety: Allowlist is strict. Default is EMPTY (DENY ALL).
    allow_modify_globs: Tuple[str, ...] = dataclasses.field(
        default_factory=lambda: tuple(filter(None, os.environ.get("PHOENIX_ALLOWLIST", "").split(";")))
    )
    
    # Safety: Deny list includes tests and sensitive dirs
    deny_dirs: Tuple[str, ...] = (
        ".git", ".github", ".venv", "venv", "node_modules", "__pycache__", 
        "dist", "build", ".idea", ".vscode", "data", "logs", "secrets", 
        "credential", "cert", "AppData", "Users", "Program Files", "tests", "test"
    )

    max_file_bytes: int = int(os.environ.get("PHOENIX_MAX_FILE_BYTES", "200000"))
    max_prompt_chars: int = int(os.environ.get("PHOENIX_MAX_PROMPT_CHARS", "180000"))
    
    # Patch Guardrails
    max_patch_lines: int = int(os.environ.get("PHOENIX_MAX_PATCH_LINES", "50"))
    max_patch_files: int = int(os.environ.get("PHOENIX_MAX_PATCH_FILES", "3"))

    gemini_cli_bin: str = dataclasses.field(default_factory=lambda: os.environ.get("GEMINI_CLI_BIN", "gemini"))
    curl_bin: str = dataclasses.field(default_factory=lambda: os.environ.get("CURL_BIN", "curl"))
    gemini_api_key_env: str = dataclasses.field(default_factory=lambda: os.environ.get("GEMINI_API_KEY_ENV", "GEMINI_API_KEY"))
    gemini_model: str = dataclasses.field(default_factory=lambda: os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"))
    request_timeout_s: int = int(os.environ.get("PHOENIX_HTTP_TIMEOUT", "120"))

    python_bin: str = dataclasses.field(default_factory=lambda: sys.executable)

    heartbeat_timeout_min: int = int(os.environ.get("PHOENIX_HEARTBEAT_MIN", "15"))
    
    # Redaction
    redact_max_patterns: int = int(os.environ.get("PHOENIX_REDACT_MAX_PATTERNS", "32"))
    redact_max_pattern_len: int = int(os.environ.get("PHOENIX_REDACT_MAX_PATTERN_LEN", "120"))
    
    base_redact_patterns: Tuple[str, ...] = (
        r"(?i)api_key\s*[=:]\s*['\"]?[-A-Za-z0-9_\.]{8,}['\"]?",
        r"(?i)token\s*[=:]\s*['\"]?[-A-Za-z0-9_\.]{8,}['\"]?",
        r"(?i)bearer\s+[A-Za-z0-9._-]{8,}",
        r"(?i)secret\s*[=:]\s*['\"]?[-A-Za-z0-9_\.]{6,}['\"]?",
    )

    log_max_bytes: int = int(os.environ.get("PHOENIX_LOG_MAX_BYTES", str(5 * 1024 * 1024)))
    max_backups_per_file: int = int(os.environ.get("PHOENIX_MAX_BACKUPS", "20"))
    cooldown_seconds_on_stop: int = int(os.environ.get("PHOENIX_COOLDOWN_SECONDS", "0"))

    def __post_init__(self):
        # Auto-tune based on specs if not explicitly set in env (env overrides everything usually, 
        # but here we use env to set defaults in field definition. 
        # Wait, dataclasses.field default_factory is called once. 
        # We need to handle the logic where env was NOT set.
        # Actually, the field definitions above ALREADY read env. 
        # So we only override if we want to be smarter than the default string "200".
        
        env_tail = os.environ.get("PHOENIX_TAIL")
        if env_tail:
            self.log_tail_lines = int(env_tail)
        else:
            # Auto-tune
            if self.specs["ram_gb"] >= 32:
                self.log_tail_lines = 1000 # Rich context for high RAM
            elif self.specs["ram_gb"] >= 16:
                self.log_tail_lines = 500
            else:
                self.log_tail_lines = 200

        # Auto-configure Fallback Model if not set
        if not self.fallback_llm_model:
            vram = self.specs.get("gpu_vram_gb", 0)
            if vram >= 40:
                self.fallback_llm_model = "deepseek-coder-33b-instruct"
            elif vram >= 20:
                self.fallback_llm_model = "codellama-34b-instruct"
            elif vram >= 12:
                self.fallback_llm_model = "codellama-13b-instruct"
            else:
                self.fallback_llm_model = "phi-3-mini-4k-instruct"
        
        # Handle multiple fallback commands (semicolon separated)
        # Stored as a list of lists: [["cmd1", "arg"], ["cmd2", "arg"]]
        # But Config.fallback_llm_cmd is List[str]... wait. 
        # Let's change fallback_llm_cmd to be a list of commands.
        # Actually, to keep it simple, let's just parse it here and store it.
        # But Config fields are typed. Let's add a new field or abuse the existing one.
        # Let's make fallback_llm_cmds (plural)
        raw_cmds = os.environ.get("PHOENIX_FALLBACK_LLM_CMD", "")
        self.fallback_llm_cmds: List[List[str]] = []
        if raw_cmds:
            for cmd_str in raw_cmds.split(";"):
                if cmd_str.strip():
                    self.fallback_llm_cmds.append(shlex.split(cmd_str.strip()))
        
        # Backwards compatibility for single cmd access if needed (use first)
        if self.fallback_llm_cmds:
            self.fallback_llm_cmd = self.fallback_llm_cmds[0]
        else:
            self.fallback_llm_cmd = []

    def ensure_dirs(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def get_redact_patterns(self) -> List[str]:
        extra = os.environ.get("PHOENIX_ADDITIONAL_REDACT_PATTERNS", "")
        patterns = list(self.base_redact_patterns)
        if extra:
            patterns.extend(filter(None, extra.split(";")))
        return patterns[:self.redact_max_patterns]


class Redactor:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.patterns: List[Pattern] = []
        for p in cfg.get_redact_patterns():
            if len(p) > cfg.redact_max_pattern_len:
                continue # Skip too long patterns
            try:
                self.patterns.append(re.compile(p))
            except re.error:
                pass # Ignore invalid regex

    def redact(self, text: str) -> str:
        if not text:
            return ""
        redacted = text
        for pattern in self.patterns:
            try:
                redacted = pattern.sub("<REDACTED>", redacted)
            except Exception:
                pass
        return redacted
    
    def redact_obj(self, obj: Any) -> Any:
        if isinstance(obj, str):
            return self.redact(obj)
        if isinstance(obj, Path):
            return self.redact(str(obj))
        if isinstance(obj, dict):
            return {k: self.redact_obj(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.redact_obj(i) for i in obj]
        if dataclasses.is_dataclass(obj):
            return self.redact_obj(dataclasses.asdict(obj))
        return obj


class Logger:
    def __init__(self, cfg: Config, redactor: Redactor) -> None:
        self.cfg = cfg
        self.redactor = redactor
        self._lock = threading.Lock()
        self.run_id = _sha256(str(time.time()))[:8]

    def _rotate_if_needed(self) -> None:
        # Lock is already held by caller (log method)
        try:
            if not self.cfg.log_path.exists():
                return
            if self.cfg.log_path.stat().st_size <= self.cfg.log_max_bytes:
                return
            rotated = self.cfg.log_path.with_suffix(self.cfg.log_path.suffix + ".1")
            if rotated.exists():
                rotated.unlink()
            self.cfg.log_path.rename(rotated)
        except Exception:
            pass

    def log(self, event: str, level: str = "INFO", **kwargs: Any) -> None:
        entry = {
            "schema_version": "v1",
            "ts": _now_iso(),
            "level": level,
            "event": event,
            "run_id": self.run_id,
            **kwargs
        }
        
        # Redact everything
        safe_entry = self.redactor.redact_obj(entry)

        with self._lock:
            self._rotate_if_needed()
            
            if self.cfg.log_format == "json":
                line = json.dumps(safe_entry, ensure_ascii=False)
            else:
                # Legacy text format
                kv = " ".join(f"{k}={v}" for k, v in safe_entry.items() if k not in ("ts", "level", "event", "schema_version"))
                line = f"[{safe_entry['ts']}] {level} {event} {kv}"

            print(line, flush=True)
            try:
                with self.cfg.log_path.open("a", encoding="utf-8", errors="ignore") as f:
                    f.write(line + "\n")
            except Exception:
                pass


class RollingBuffer:
    def __init__(self, max_lines: int) -> None:
        self.max_lines = max_lines
        self._lines: List[str] = []
        self._lock = threading.Lock()

    def add(self, line: str) -> None:
        with self._lock:
            self._lines.append(line.rstrip("\n"))
            if len(self._lines) > self.max_lines:
                self._lines = self._lines[-self.max_lines :]

    def tail_text(self) -> str:
        with self._lock:
            return "\n".join(self._lines)


class StateStore:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self._lock = threading.Lock()
        self._state: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self.cfg.state_path.exists():
            try:
                self._state = json.loads(self.cfg.state_path.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                self._state = {}
        if "retries" not in self._state:
            self._state["retries"] = {}
        if "quarantine" not in self._state:
            self._state["quarantine"] = []

    def _save(self) -> None:
        tmp = self.cfg.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            tmp.replace(self.cfg.state_path)
        except OSError:
            pass

    def get_retry(self, signature: str) -> int:
        with self._lock:
            return int(self._state.get("retries", {}).get(signature, 0))

    def inc_retry(self, signature: str) -> int:
        with self._lock:
            self._state.setdefault("retries", {})
            self._state["retries"][signature] = int(self._state["retries"].get(signature, 0)) + 1
            self._save()
            return int(self._state["retries"][signature])
            
    def is_quarantined(self, signature: str) -> bool:
        with self._lock:
            return signature in self._state.get("quarantine", [])

    def quarantine(self, signature: str) -> None:
        with self._lock:
            q = self._state.get("quarantine", [])
            if signature not in q:
                q.append(signature)
                self._state["quarantine"] = q
                self._save()


class GeminiCLIClient:
    def __init__(self, cfg: Config, logger: Logger) -> None:
        self.cfg = cfg
        self.logger = logger

    def request_fix(self, prompt: str) -> Dict[str, Any]:
        cmd = [self.cfg.gemini_cli_bin, "-p", prompt]
        self.logger.log("llm_request", method="cli")
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
        if proc.returncode != 0:
            raise RuntimeError(f"Gemini CLI failed rc={proc.returncode} stderr={(proc.stderr or '')[-1000:]}")
        return _extract_json_object(proc.stdout)


class GeminiApiCurlClient:
    def __init__(self, cfg: Config, logger: Logger) -> None:
        self.cfg = cfg
        self.logger = logger

    def request_fix(self, prompt: str, target_path: str) -> Dict[str, Any]:
        api_key = os.environ.get(self.cfg.gemini_api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing env {self.cfg.gemini_api_key_env}")

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.cfg.gemini_model}:generateContent?key={api_key}"
        )

        patch_schema = {
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING"},
                "mode": {"type": "STRING"},
                "diff": {"type": "STRING"},
                "start_line": {"type": "NUMBER"},
                "end_line": {"type": "NUMBER"},
                "code": {"type": "STRING"},
            },
            "required": ["file_path", "mode"],
        }

        schema = {
            "type": "OBJECT",
            "properties": {
                "patches": {
                    "type": "ARRAY",
                    "items": patch_schema,
                }
            },
            "required": ["patches"],
        }

        body = {
            "system_instruction": {
                "parts": [
                    {
                        "text": (
                            "Return JSON only with top-level patches array."
                            "Each patch must include file_path, mode (unified_diff or replace_range),"
                            "and required fields per mode."
                            "No markdown or commentary."
                        )
                    }
                ]
            },
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "response_mime_type": "application/json",
                "response_schema": schema,
            },
        }

        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")

        cmd = [
            self.cfg.curl_bin,
            "-sS",
            "-H",
            "Content-Type: application/json",
            "-X",
            "POST",
            url,
            "--data-binary",
            "@-",
        ]

        self.logger.log("llm_request", method="api", model=self.cfg.gemini_model, target=target_path)
        proc = subprocess.run(
            cmd,
            input=payload,
            capture_output=True,
            timeout=self.cfg.request_timeout_s,
        )
        if proc.returncode != 0:
            err = (proc.stderr or b"").decode("utf-8", errors="ignore")
            raise RuntimeError(f"curl failed rc={proc.returncode} stderr={err[-1200:]}")

        outer = json.loads((proc.stdout or b"{}").decode("utf-8", errors="ignore"))
        text = _extract_gemini_text(outer)
        return _extract_json_object(text)


class LocalCodeCLIClient:
    def __init__(self, cfg: Config, logger: Logger) -> None:
        self.cfg = cfg
        self.logger = logger

    def check_health(self) -> bool:
        if not self.cfg.fallback_llm_cmds:
            return False
        
        # Check all configured commands
        all_ok = True
        for cmd in self.cfg.fallback_llm_cmds:
            if not cmd:
                continue
            
            # 1. Existence Check
            exe = shutil.which(cmd[0])
            if not exe:
                self.logger.log("fallback_health_fail", reason="not_found", cmd=cmd[0])
                all_ok = False
                continue
                
            # 2. Run Check (with --help or similar if possible, but risky if it runs model)
            # Just checking existence is safer for arbitrary commands unless we know they support --help
            # Let's try running with --help and timeout quickly
            try:
                subprocess.run([exe, "--help"], capture_output=True, timeout=2)
            except subprocess.TimeoutExpired:
                pass # It exists and runs, just timed out. That's "alive".
            except Exception as e:
                self.logger.log("fallback_health_fail", reason="exec_error", cmd=cmd[0], error=str(e))
                all_ok = False
        
        return all_ok

    def request_fix(self, prompt: str) -> Dict[str, Any]:
        # Try each configured command in order
        last_error = None
        for cmd in self.cfg.fallback_llm_cmds:
            try:
                full_cmd = cmd + [prompt]
                self.logger.log("llm_request", method="fallback_cli", cmd=cmd[0])
                proc = subprocess.run(full_cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
                if proc.returncode != 0:
                    raise RuntimeError(f"Fallback CLI failed rc={proc.returncode} stderr={(proc.stderr or '')[-500:]}")
                return _extract_json_object(proc.stdout)
            except Exception as e:
                last_error = e
                self.logger.log("fallback_retry", failed_cmd=cmd[0], error=str(e))
                continue
        
        raise last_error or RuntimeError("No fallback commands succeeded")


class DiscordNotifier:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    def notify(self, title: str, description: str, color: int = 0x00FF00, fields: List[Dict[str, Any]] = None) -> None:
        if not self.cfg.discord_webhook_url:
            return
        
        embed = {
            "title": title,
            "description": description[:2000], # Discord limit
            "color": color,
            "timestamp": _now_iso(),
            "footer": {"text": "RTX5090-DebugSystem"}
        }
        
        if fields:
            embed["fields"] = fields
            
        payload = {"embeds": [embed]}
        
        def _send():
            try:
                req = urllib.request.Request(
                    self.cfg.discord_webhook_url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "User-Agent": "Phoenix/1.0"}
                )
                with urllib.request.urlopen(req, timeout=5) as res:
                    pass
            except Exception:
                pass
        
        # Send in background to not block
        threading.Thread(target=_send, daemon=True).start()


class AutoHealer:
    def __init__(self, cfg: Config, logger: Logger) -> None:
        self.cfg = cfg
        self.logger = logger

    def analyze_failure(self, returncode: int, stdout: str, stderr: str) -> Optional[Dict[str, Any]]:
        """
        Analyze logs and return a patch/action dict if a known fix exists.
        """
        full_log = (stdout + "\n" + stderr)
        
        # Scenario 1: Gradient Explosion (NaN)
        if "grad_norm: nan" in full_log or "loss: 0.0" in full_log or "loss: nan" in full_log:
            self.logger.log("auto_heal_trigger", reason="gradient_explosion")
            return {
                "action": "modify_config",
                "target": "train_lora.py",
                "changes": {
                    "learning_rate": "reduce_50_percent",
                    "max_grad_norm": "0.5" 
                },
                "explanation": "Detected Gradient Explosion (NaN). Reducing Learning Rate and enabling Gradient Clipping."
            }

        # Scenario 2: OOM (CUDA Out Of Memory)
        if "CUDA out of memory" in full_log:
             self.logger.log("auto_heal_trigger", reason="oom")
             return {
                 "action": "modify_config",
                 "target": "train_lora.py",
                 "changes": {
                     "per_device_train_batch_size": "reduce_50_percent",
                     "gradient_accumulation_steps": "double"
                 },
                 "explanation": "Detected OOM. Halving batch size and doubling accumulation to maintain effective batch size."
             }
             
        # Scenario 3: Missing Dependencies
        if "ModuleNotFoundError" in full_log:
             # Basic regex to capture module name
             m = re.search(r"ModuleNotFoundError: No module named '([^']+)'", full_log)
             if m:
                 missing = m.group(1)
                 return {
                     "action": "install_pip",
                     "package": missing,
                     "explanation": f"Missing dependency: {missing}"
                 }

        return None

    def apply_fix(self, fix: Dict[str, Any]) -> bool:
        """
        Apply the fix physically to the files.
        """
        if fix["action"] == "modify_config":
            # Rough sed/regex replacement for safe config tuning
            target_path = Path(self.cfg.project_root) / fix["target"]
            if not target_path.exists():
                return False
            
            content = target_path.read_text(encoding="utf-8")
            
            for key, mode in fix["changes"].items():
                # Regex to find key assignment in SFTConfig
                # pattern: key = value,
                pattern = re.compile(rf"({key}\s*=\s*)([\d\.e-]+)(,?)")
                match = pattern.search(content)
                if match:
                    prefix, current_val_str, suffix = match.groups()
                    try:
                        current_val = float(current_val_str)
                    except ValueError:
                        continue
                        
                    new_val = current_val
                    if mode == "reduce_50_percent":
                        new_val = current_val * 0.5
                    elif mode == "double":
                        new_val = current_val * 2.0
                    elif mode.replace('.', '', 1).isdigit():
                        new_val = float(mode) # Direct set
                    
                    # Format preservation
                    new_val_str = f"{new_val:.2e}" if "e" in current_val_str else f"{new_val:.5f}".rstrip("0").rstrip(".")
                    
                    content = content.replace(match.group(0), f"{prefix}{new_val_str}{suffix}")
                    self.logger.log("auto_heal_apply", file=fix["target"], key=key, old=current_val_str, new=new_val_str)
            
            target_path.write_text(content, encoding="utf-8")
            return True

        elif fix["action"] == "install_pip":
            pkg = fix["package"]
            subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True)
            return True
            
        return False


class Monitor:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.logger = Logger(cfg, Redactor(cfg))
        self.notifier = DiscordNotifier(cfg)
        self.healer = AutoHealer(cfg, self.logger)
        
    def run(self):
        self.logger.log("monitor_start", cmd=self.cfg.train_cmd)
        self.notifier.notify("Training Started", f"Command: {' '.join(self.cfg.train_cmd)}", color=0x3498db)
        
        retries = 0
        while retries <= 3: # Max auto-heals
            start_time = time.time()
            
            # Run Training
            proc = subprocess.run(
                self.cfg.train_cmd,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
                capture_output=True, # We need output for analysis. 
                # streaming output to console AND capturing is hard with simple subprocess.run.
                # For now, we capture. 
                # TODO: Implement Tee logic for real-time console + capture.
                text=True,
                encoding="utf-8",
                errors="ignore"
            )
            
            # Print output for user
            print(proc.stdout)
            print(proc.stderr, file=sys.stderr)
            
            if proc.returncode == 0:
                duration = time.time() - start_time
                self.logger.log("monitor_success", duration=duration)
                self.notifier.notify("Training Complete", f"Success! Duration: {duration:.1f}s", color=0x2ecc71)
                return 0
            
            # Failure Analysis
            self.logger.log("monitor_fail", rc=proc.returncode)
            self.notifier.notify("Training Failed", f"RC: {proc.returncode}\nAnalyzeing...", color=0xe74c3c)
            
            fix = self.healer.analyze_failure(proc.returncode, proc.stdout, proc.stderr)
            if fix and retries < 3:
                self.logger.log("monitor_healing", fix=fix)
                self.notifier.notify("Auto-Healing", f"Applying fix: {fix['explanation']}", color=0xf1c40f)
                
                if self.healer.apply_fix(fix):
                    retries += 1
                    time.sleep(2)
                    continue
                else:
                    self.logger.log("monitor_heal_fail_apply")
                    break
            else:
                self.logger.log("monitor_give_up")
                break
                
        self.notifier.notify("Training Fatal Error", "Could not recover.", color=0x992d22)
        return 1


class DiscordBot:
    """Zero-dependency Discord Bot using polling (REST API)."""
    def __init__(self, cfg: Config, logger: Logger, notifier: DiscordNotifier, tracker: 'ProgressTracker', graph_gen: GraphGenerator) -> None:
        self.cfg = cfg
        self.logger = logger
        self.notifier = notifier
        self.tracker = tracker
        self.graph_gen = graph_gen
        self.last_msg_id = None
        self.base_url = f"https://discord.com/api/v10/channels/{cfg.discord_channel_id}/messages"
        self.headers = {
            "Authorization": f"Bot {cfg.discord_bot_token}",
            "User-Agent": "Phoenix/1.0",
            "Content-Type": "application/json"
        }
        self.stop_requested = False
        self.resume_requested = False
        self.status_requested = False

    def poll_commands(self) -> None:
        if not self.cfg.discord_bot_token or not self.cfg.discord_channel_id:
            return

        try:
            # Get latest messages
            url = f"{self.base_url}?limit=5"
            if self.last_msg_id:
                url += f"&after={self.last_msg_id}"
                
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=5) as res:
                msgs = json.loads(res.read().decode("utf-8"))
                
                if not msgs:
                    return

                # Process from oldest to newest
                for msg in sorted(msgs, key=lambda x: x["id"]):
                    self.last_msg_id = msg["id"]
                    content = msg.get("content", "").strip()
                    
                    if content == "!status":
                        self.status_requested = True
                        self._react(msg["id"], "👀")
                    elif content == "!stop":
                        self.stop_requested = True
                        self._react(msg["id"], "🛑")
                        self.notifier.notify("🛑 Command Received", "Stopping training...", 0xFF0000)
                    elif content == "!resume":
                        self.resume_requested = True
                        self.stop_requested = False # Cancel stop
                        self._react(msg["id"], "▶️")
                        self.notifier.notify("▶️ Command Received", "Resuming training...", 0x00FF00)
                    elif content == "!config":
                        self._send_reply(msg["id"], f"```json\n{json.dumps(dataclasses.asdict(self.cfg), default=str, indent=2)[:1900]}\n```")
                    elif content == "!report":
                        self._handle_report(msg["id"])

        except Exception:
            pass

    def _handle_report(self, msg_id: str) -> None:
        self._react(msg_id, "📊")
        # Generate Graph
        graph_path = self.graph_gen.generate_loss_graph(self.tracker.loss_history)
        
        msg = "📊 **Daily Report**\n"
        msg += f"Current Step: {self.tracker.current_step}/{self.tracker.total_steps}\n"
        msg += f"Current Loss: {self.tracker.current_loss:.4f}\n"
        
        if graph_path and graph_path.exists():
            # Sending images via raw HTTP request in Python without requests lib is painful (multipart/form-data).
            # For simplicity, we will just notify that graph is saved locally, 
            # OR we can try to send it if we implement multipart.
            # Given constraints, let's just send text stats and mention where the graph is.
            # "Graph saved to .phoenix_cli/reports/loss_graph.png"
            # Ideally we upload it. But implementing multipart encoder from scratch is verbose.
            # Let's try to just send the text report for now.
            msg += f"\nGraph generated: `{graph_path.name}` (Check local folder)"
        else:
            msg += "\n(Graph generation failed or no data)"
            
        self._send_reply(msg_id, msg)

    def _react(self, msg_id: str, emoji: str) -> None:
        try:
            # PUT /channels/{channel.id}/messages/{message.id}/reactions/{emoji}/@me
            # Emoji must be URL encoded. Standard emoji are just characters.
            encoded_emoji = urllib.parse.quote(emoji)
            url = f"{self.base_url}/{msg_id}/reactions/{encoded_emoji}/@me"
            req = urllib.request.Request(url, headers=self.headers, method="PUT")
            with urllib.request.urlopen(req, timeout=5) as res:
                pass
        except Exception:
            pass

    def _send_reply(self, msg_id: str, content: str) -> None:
        try:
            payload = {
                "content": content,
                "message_reference": {"message_id": msg_id}
            }
            req = urllib.request.Request(
                self.base_url,
                data=json.dumps(payload).encode("utf-8"),
                headers=self.headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5) as res:
                pass
        except Exception:
            pass


class GitManager:
    def __init__(self, cfg: Config, logger: Logger) -> None:
        self.cfg = cfg
        self.logger = logger

    def commit_fix(self, message: str) -> bool:
        if not self.cfg.git_auto_commit:
            return False
            
        try:
            # Check if git repo
            if not (self.cfg.project_root / ".git").exists():
                return False
                
            subprocess.run(["git", "add", "."], cwd=str(self.cfg.project_root), check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", f"Phoenix Auto-Fix: {message}"], cwd=str(self.cfg.project_root), check=True, capture_output=True)
            self.logger.log("git_commit_success", message=message)
            return True
        except Exception as e:
            self.logger.log("git_commit_failed", error=str(e))
            return False


class DataSanitizer:
    def __init__(self, cfg: Config, logger: Logger) -> None:
        self.cfg = cfg
        self.logger = logger
        # Common data error patterns
        self.patterns = [
            (re.compile(r"PIL\.UnidentifiedImageError: cannot identify image file '([^']+)'"), "corrupt_image"),
            (re.compile(r"UnicodeDecodeError: .* in file '([^']+)'"), "encoding_error"),
            (re.compile(r"OSError: image file is truncated .* '([^']+)'"), "truncated_image"),
        ]

    def sanitize(self, stderr: str) -> bool:
        for pattern, reason in self.patterns:
            match = pattern.search(stderr)
            if match:
                file_path = Path(match.group(1))
                if not file_path.is_absolute():
                    file_path = self.cfg.project_root / file_path
                
                if file_path.exists():
                    try:
                        new_path = file_path.with_suffix(file_path.suffix + ".corrupt")
                        file_path.rename(new_path)
                        self.logger.log("data_quarantined", file=str(file_path), reason=reason)
                        return True
                    except Exception as e:
                        self.logger.log("data_quarantine_failed", file=str(file_path), error=str(e))
        return False


class ReportGenerator:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.report_file = cfg.report_dir / f"report_{time.strftime('%Y%m%d')}.html"

    def update(self, events: List[Dict[str, Any]]) -> None:
        # Simple append-only HTML generator
        # In reality, we'd parse the log file, but here we just append a row if it's new
        pass # Placeholder for complex logic, or we can generate on exit.
        
    def generate_daily(self) -> None:
        if not self.cfg.log_path.exists():
            return
            
        # Read today's logs
        today = time.strftime("%Y-%m-%d")
        events = []
        try:
            with self.cfg.log_path.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if data.get("ts", "").startswith(today):
                            events.append(data)
                    except: pass
        except: return

        # Summarize
        total_errors = sum(1 for e in events if e.get("event") == "attempt_fix")
        successes = sum(1 for e in events if e.get("event") == "patch_success")
        
        html = f"""
        <html>
        <head><title>Phoenix Daily Report {today}</title>
        <style>body{{font-family:sans-serif;}} .success{{color:green;}} .fail{{color:red;}}</style>
        </head>
        <body>
        <h1>Phoenix Report: {today}</h1>
        <p>Total Fix Attempts: {total_errors}</p>
        <p>Successes: <span class="success">{successes}</span></p>
        <h2>Event Log</h2>
        <ul>
        """
        for e in events:
            if e.get("level") in ("WARNING", "ERROR") or e.get("event") in ("patch_success", "startup"):
                html += f"<li>[{e.get('ts')}] <b>{e.get('event')}</b>: {e}</li>"
        
        html += "</ul></body></html>"
        self.report_file.write_text(html, encoding="utf-8")


class SafetyGuards:
    def __init__(self, cfg: Config, logger: Logger, discord: DiscordNotifier) -> None:
        self.cfg = cfg
        self.logger = logger
        self.discord = discord
        self.power_samples: List[float] = [] # Watts

    def check_thermal(self) -> bool:
        """Check GPU temperature and track power usage."""
        try:
            # nvidia-smi --query-gpu=temperature.gpu,power.draw --format=csv,noheader
            cmd = ["nvidia-smi", "--query-gpu=temperature.gpu,power.draw", "--format=csv,noheader,nounits"]
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
            if proc.returncode == 0:
                line = proc.stdout.strip()
                if "," in line:
                    temp_str, power_str = line.split(",", 1)
                    temp = int(float(temp_str))
                    power = float(power_str)
                    
                    # Track power
                    self.power_samples.append(power)
                    if len(self.power_samples) > 100: # Keep last 100 samples (~1-2 mins)
                        self.power_samples.pop(0)

                    if temp >= self.cfg.max_gpu_temp:
                        msg = f"GPU Overheating! {temp}C >= {self.cfg.max_gpu_temp}C"
                        self.logger.log("thermal_warning", temp=temp)
                        self.discord.notify("🔥 Thermal Warning", msg, 0xFF0000)
                        return False
        except Exception:
            pass
        return True

    def check_disk(self) -> bool:
        """Check disk space. Returns False if low space."""
        try:
            total, used, free = shutil.disk_usage(self.cfg.project_root)
            free_gb = free / (1024**3)
            if free_gb < self.cfg.min_disk_gb:
                msg = f"Low Disk Space! {free_gb:.1f}GB < {self.cfg.min_disk_gb}GB"
                self.logger.log("disk_warning", free_gb=free_gb)
                self.discord.notify("💾 Disk Warning", msg, 0xFF0000)
                return False
        except Exception:
            pass
        return True
        
    def get_avg_power(self) -> float:
        if not self.power_samples:
            return 0.0
        return sum(self.power_samples) / len(self.power_samples)


class DataValidator:
    def __init__(self, cfg: Config, logger: Logger, discord: DiscordNotifier) -> None:
        self.cfg = cfg
        self.logger = logger
        self.discord = discord

    def validate(self) -> bool:
        if not self.cfg.data_dir.exists():
            self.logger.log("data_dir_missing", path=str(self.cfg.data_dir))
            self.discord.notify("⚠️ Data Missing", f"Data directory '{self.cfg.data_dir}' not found!", 0xFFFF00)
            return False # Warn but maybe don't block? Or block? Let's block if user expects data.
            # Actually, if train.py handles it, we might just warn.
            # But user asked "How to verify". So we should be proactive.
            
        files = list(self.cfg.data_dir.glob("*"))
        if not files:
            self.logger.log("data_dir_empty", path=str(self.cfg.data_dir))
            self.discord.notify("⚠️ Data Empty", f"Data directory '{self.cfg.data_dir}' is empty!", 0xFFFF00)
            return False

        # Check for common formats
        valid_exts = {".jsonl", ".json", ".txt", ".parquet", ".csv", ".tsv", ".pt", ".bin"}
        has_valid_data = any(f.suffix in valid_exts for f in files)
        
        if not has_valid_data:
            self.logger.log("no_valid_data_files", path=str(self.cfg.data_dir))
            self.discord.notify("⚠️ No Valid Data", f"No recognized data files in '{self.cfg.data_dir}'", 0xFFFF00)
            return False
            
        # Check for empty files
        for f in files:
            if f.is_file() and f.stat().st_size == 0:
                self.logger.log("empty_data_file", file=str(f))
                self.discord.notify("⚠️ Empty Data File", f"File '{f.name}' is empty.", 0xFFFF00)

        self.logger.log("data_validation_passed", file_count=len(files))
        return True


class ProgressTracker:
    def __init__(self, cfg: Config, discord: DiscordNotifier) -> None:
        self.cfg = cfg
        self.discord = discord
        self.regex = re.compile(cfg.progress_regex)
        self.loss_regex = re.compile(cfg.loss_regex)
        self.val_loss_regex = re.compile(cfg.val_loss_regex)
        
        self.start_time = time.time()
        self.last_notify_time = time.time()
        self.last_notify_step = 0
        self.current_step = 0
        self.total_steps = 0
        self.eta_seconds = 0.0
        
        self.current_loss = 0.0
        self.current_val_loss = 0.0
        self.loss_history: List[float] = []
        self.val_loss_history: List[float] = []
        
        self.virtual_target_step: Optional[int] = None
        self.pacing_active = False

    def parse(self, line: str) -> None:
        # Parse Progress
        match = self.regex.search(line)
        if match:
            try:
                cur = int(match.group(1))
                tot = int(match.group(2))
                if tot > 0:
                    self.current_step = cur
                    self.total_steps = tot
                    self._update_eta()
            except: pass
            
        # Parse Loss
        loss_match = self.loss_regex.search(line)
        if loss_match:
            try:
                val = float(loss_match.group(1))
                self.current_loss = val
                self.loss_history.append(val)
                if len(self.loss_history) > 100:
                    self.loss_history.pop(0)
                self._check_loss_anomaly(val)
                self._check_stagnation()
            except: pass

        # Parse Val Loss
        val_match = self.val_loss_regex.search(line)
        if val_match:
            try:
                val = float(val_match.group(1))
                self.current_val_loss = val
                self.val_loss_history.append(val)
                if len(self.val_loss_history) > 20:
                    self.val_loss_history.pop(0)
                self._check_overfitting(val)
            except: pass

    def _check_loss_anomaly(self, loss: float) -> None:
        if math.isnan(loss) or math.isinf(loss):
            self.discord.notify("⚠️ Loss Anomaly", f"Loss is {loss}!", 0xFF0000)
            return
            
        # Simple spike detection (if > 3x average of last 10)
        if len(self.loss_history) > 10:
            recent = self.loss_history[-11:-1]
            avg = sum(recent) / len(recent)
            if avg > 0 and loss > avg * 3:
                self.discord.notify("📈 Loss Spike", f"Loss spiked to {loss:.4f} (Avg: {avg:.4f})", 0xFFA500)

    def _check_stagnation(self) -> None:
        # If loss hasn't improved in 50 steps
        if len(self.loss_history) >= 50:
            recent = self.loss_history[-50:]
            if max(recent) - min(recent) < 0.0001:
                self.discord.notify("🛑 Loss Stagnation", "Loss hasn't changed significantly in 50 steps.", 0xFFFF00)

    def _check_overfitting(self, val_loss: float) -> None:
        # If val_loss is increasing while train loss is decreasing (simple check)
        if len(self.val_loss_history) >= 3:
            recent = self.val_loss_history[-3:]
            if recent[0] < recent[1] < recent[2]:
                 self.discord.notify("📉 Overfitting Warning", f"Validation loss is increasing! ({recent[0]:.4f} -> {recent[2]:.4f})", 0xFFA500)

    def _update_eta(self) -> None:
        if self.current_step <= 0:
            return
            
        elapsed = time.time() - self.start_time
        rate = elapsed / self.current_step # seconds per step
        remaining_steps = self.total_steps - self.current_step
        self.eta_seconds = rate * remaining_steps
        
        # Smart Pacing Logic
        if self.cfg.deadline_time and not self.pacing_active and self.total_steps > 0:
            try:
                # Parse deadline
                now = datetime.datetime.now()
                deadline_h, deadline_m = map(int, self.cfg.deadline_time.split(":"))
                deadline_dt = now.replace(hour=deadline_h, minute=deadline_m, second=0, microsecond=0)
                if deadline_dt < now:
                    deadline_dt += datetime.timedelta(days=1)
                
                time_until_deadline = (deadline_dt - now).total_seconds()
                
                # If ETA exceeds deadline by margin (e.g. 5 mins)
                if self.eta_seconds > time_until_deadline + 300:
                    # Calculate max steps possible
                    max_possible_steps = int(time_until_deadline / rate) + self.current_step
                    # Safety buffer (95%)
                    safe_target = int(max_possible_steps * 0.95)
                    
                    if safe_target < self.total_steps and safe_target > self.current_step:
                        self.virtual_target_step = safe_target
                        self.pacing_active = True
                        msg = (f"⚠️ Pacing Adjustment Active\n"
                               f"Cannot finish {self.total_steps} steps by {self.cfg.deadline_time}.\n"
                               f"Adjusting target to {safe_target} steps to finish on time.")
                        self.discord.notify("📉 Smart Pacing", msg, 0xFFA500)
            except Exception:
                pass

        # Notify Logic
        should_notify = False
        
        # 1. Step-based
        if self.cfg.notify_every_steps > 0:
            if self.current_step - self.last_notify_step >= self.cfg.notify_every_steps:
                should_notify = True
        
        # 2. Time-based (fallback to 60m if step-based not set, or force every 60m anyway?)
        # Let's say if step-based is set, we rely on that. If not, we use time (60m).
        if self.cfg.notify_every_steps == 0:
            if time.time() - self.last_notify_time > 3600:
                should_notify = True
                
        if should_notify:
            self._notify_status()
            self.last_notify_time = time.time()
            self.last_notify_step = self.current_step

    def _notify_status(self) -> None:
        eta_str = time.strftime("%H:%M:%S", time.gmtime(self.eta_seconds))
        pct = (self.current_step / self.total_steps) * 100
        msg = f"Progress: {self.current_step}/{self.total_steps} ({pct:.1f}%)\nETA: {eta_str}"
        
        fields = [
            {"name": "Step", "value": f"{self.current_step}/{self.total_steps}", "inline": True},
            {"name": "Progress", "value": f"{pct:.1f}%", "inline": True},
            {"name": "ETA", "value": eta_str, "inline": True},
        ]
        
        if self.current_loss > 0:
            fields.append({"name": "Loss", "value": f"{self.current_loss:.4f}", "inline": True})
        
        if self.current_val_loss > 0:
            fields.append({"name": "Val Loss", "value": f"{self.current_val_loss:.4f}", "inline": True})
        
        if self.pacing_active:
            msg += f"\n(Target adjusted to {self.virtual_target_step} for deadline)"
            fields.append({"name": "Pacing Target", "value": str(self.virtual_target_step), "inline": False})
            
        self.discord.notify("⏳ Training Status", msg, 0x00FFFF, fields=fields)

    def get_eta_str(self) -> str:
        if self.eta_seconds == 0:
            return "Unknown"
        return time.strftime("%H:%M:%S", time.gmtime(self.eta_seconds))
    
    def should_stop_early(self) -> bool:
        if self.pacing_active and self.virtual_target_step:
            return self.current_step >= self.virtual_target_step
        return False


class CostEstimator:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.start_time = time.time()
        self.total_kwh = 0.0
        self.last_check = time.time()

    def update(self, avg_power_watts: float) -> None:
        now = time.time()
        hours = (now - self.last_check) / 3600.0
        kwh = (avg_power_watts / 1000.0) * hours
        self.total_kwh += kwh
        self.last_check = now

    def get_cost(self) -> float:
        return self.total_kwh * self.cfg.kwh_price


class LocalOpenAIClient:
    def __init__(self, cfg: Config, logger: Logger) -> None:
        self.cfg = cfg
        self.logger = logger

    def check_health(self) -> bool:
        # Ping /v1/models to check if server is up
        try:
            base_url = self.cfg.fallback_llm_url.rsplit("/", 2)[0] # remove /chat/completions
            if not base_url.endswith("/v1"):
                 base_url += "/v1"
            url = f"{base_url}/models"
            
            req = urllib.request.Request(url, headers={"User-Agent": "Phoenix/1.0"})
            with urllib.request.urlopen(req, timeout=2) as res:
                return res.status == 200
        except Exception:
            # Fallback: try a dummy completion if models endpoint fails or is different
            try:
                self.request_fix("ping")
                return True
            except:
                return False

    def request_fix(self, prompt: str) -> Dict[str, Any]:
        # ... (existing implementation)
        payload = {
            "model": self.cfg.fallback_llm_model,
            "messages": [
                {"role": "system", "content": "Return JSON only."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        
        try:
            req = urllib.request.Request(
                self.cfg.fallback_llm_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=self.cfg.request_timeout_s) as res:
                body = json.loads(res.read().decode("utf-8"))
                content = body["choices"][0]["message"]["content"]
                return _extract_json_object(content)
        except Exception as e:
            raise RuntimeError(f"Fallback API failed: {e}")


def _extract_gemini_text(resp: Dict[str, Any]) -> str:
    parts: List[str] = []
    for candidate in resp.get("candidates", []) or []:
        content = (candidate or {}).get("content", {}) or {}
        for part in content.get("parts", []) or []:
            text = (part or {}).get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()


def _extract_json_object(raw: str) -> Dict[str, Any]:
    data = raw.strip()
    if not data:
        raise RuntimeError("Empty LLM output")

    try:
        return json.loads(data)
    except Exception:
        pass

    match = re.search(r"\{.*\}", data, flags=re.DOTALL)
    if not match:
        raise RuntimeError(f"Failed to locate JSON object head={data[:200]!r}")
    return json.loads(match.group(0))


class PatchApplier:
    def __init__(self, cfg: Config, logger: Logger) -> None:
        self.cfg = cfg
        self.logger = logger

    def is_safe_target(self, path: Path) -> bool:
        try:
            resolved = path.resolve()
            rel = resolved.relative_to(self.cfg.project_root.resolve())
        except Exception:
            return False

        # 1. Deny Dirs (Prefix check)
        for part in rel.parts:
            if part in self.cfg.deny_dirs:
                return False
        
        # 2. Test Protection
        if "test" in rel.name.lower() and "dummy" not in rel.name.lower():
             # Strict protection for tests unless it's a dummy
             return False

        # 3. Allowlist (Strict)
        if not self.cfg.allow_modify_globs:
            # Default DENY ALL if allowlist is empty
            return False
            
        # Check if matches any allow glob
        matched = False
        for glob in self.cfg.allow_modify_globs:
            if rel.match(glob) or path.match(glob):
                matched = True
                break
        
        return matched

    def _prune_backups(self, path: Path) -> None:
        backups = sorted(
            self.cfg.backups_dir.glob(f"{path.name}.*.bak"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old in backups[self.cfg.max_backups_per_file :]:
            try:
                old.unlink()
            except Exception:
                pass

    def backup(self, path: Path, content: str) -> Path:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup = self.cfg.backups_dir / f"{path.name}.{timestamp}.bak"
        backup.write_text(content, encoding="utf-8")
        self._prune_backups(path)
        return backup

    def run_test_cmd(self) -> Tuple[bool, str]:
        if not self.cfg.test_cmd:
            return True, ""
        
        self.logger.log("run_test", cmd=self.cfg.test_cmd)
        proc = subprocess.run(
            self.cfg.test_cmd,
            cwd=str(self.cfg.project_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        output = "\n".join([
            (proc.stdout or "").strip(),
            (proc.stderr or "").strip(),
        ]).strip()
        return proc.returncode == 0, output

    def _apply_replace_range(self, content: str, start: int, end: int, code: str) -> str:
        lines = content.splitlines(keepends=True)
        start_idx = max(start - 1, 0)
        end_idx = max(end, 0)
        if start_idx > len(lines):
            start_idx = len(lines)
        if end_idx > len(lines):
            end_idx = len(lines)
        replacement = code.splitlines(keepends=True)
        return "".join(lines[:start_idx] + replacement + lines[end_idx:])

    def _apply_unified_diff(self, content: str, diff: str) -> str:
        original_lines = content.splitlines(keepends=True)
        diff_lines = diff.splitlines(keepends=True)
        patched_lines: List[str] = []
        idx = 0
        i = 0

        while i < len(diff_lines):
            line = diff_lines[i]
            if not line.startswith("@@"):
                i += 1
                continue
            match = re.match(r"@@ -(?P<l1>\d+)(,(?P<n1>\d+))? \+(?P<l2>\d+)(,(?P<n2>\d+))? @@", line)
            if not match:
                raise ValueError("Invalid unified diff header")
            start_old = int(match.group("l1")) - 1
            while idx < start_old and idx < len(original_lines):
                patched_lines.append(original_lines[idx])
                idx += 1
            i += 1
            while i < len(diff_lines) and not diff_lines[i].startswith("@@"):
                hunk_line = diff_lines[i]
                if hunk_line.startswith(" "):
                    if idx >= len(original_lines):
                        raise ValueError("Context line out of range")
                    patched_lines.append(original_lines[idx])
                    idx += 1
                elif hunk_line.startswith("-"):
                    idx += 1
                elif hunk_line.startswith("+"):
                    patched_lines.append(hunk_line[1:])
                else:
                    raise ValueError("Unknown diff line prefix")
                i += 1
        patched_lines.extend(original_lines[idx:])
        return "".join(patched_lines)

    def apply_patch_set(self, patches: List[Dict[str, Any]]) -> Tuple[bool, str]:
        # Guardrails: Check limits
        if len(patches) > self.cfg.max_patch_files:
            return False, f"Too many files patched: {len(patches)} > {self.cfg.max_patch_files}"

        total_lines = 0
        for p in patches:
            code = p.get("code", "") or p.get("diff", "")
            total_lines += len(code.splitlines())
        
        if total_lines > self.cfg.max_patch_lines:
            return False, f"Patch too large: {total_lines} lines > {self.cfg.max_patch_lines}"

        # Shadow Patching Strategy
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            temp_map: Dict[Path, Path] = {} # Real Path -> Temp Path
            originals: Dict[Path, str] = {}
            
            # 1. Prepare Shadow Copies
            for patch in patches:
                file_path = Path(str(patch.get("file_path"))).resolve()
                if not self.is_safe_target(file_path):
                    return False, f"Unsafe target path {file_path}"
                
                if file_path not in temp_map:
                    # Create temp file structure
                    rel_path = file_path.relative_to(self.cfg.project_root.resolve())
                    temp_file = temp_root / rel_path
                    temp_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    if file_path.exists():
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        temp_file.write_text(content, encoding="utf-8")
                        originals[file_path] = content
                    else:
                        originals[file_path] = ""
                        temp_file.write_text("", encoding="utf-8")
                    
                    temp_map[file_path] = temp_file

            # 2. Apply Patches to Shadow Copies
            for patch in patches:
                file_path = Path(str(patch.get("file_path"))).resolve()
                temp_file = temp_map[file_path]
                mode = patch.get("mode")
                
                current_content = temp_file.read_text(encoding="utf-8", errors="ignore")
                
                try:
                    if mode == "replace_range":
                        start = int(patch.get("start_line", 0))
                        end = int(patch.get("end_line", 0))
                        code = patch.get("code", "")
                        updated = self._apply_replace_range(current_content, start, end, code)
                    elif mode == "unified_diff":
                        diff = patch.get("diff", "")
                        updated = self._apply_unified_diff(current_content, diff)
                    else:
                        return False, f"Unknown patch mode {mode}"
                    
                    temp_file.write_text(updated, encoding="utf-8")
                except Exception as e:
                    return False, f"Failed to apply patch to {file_path.name}: {e}"

            # 3. Verification (Compile & Test)
            # Check syntax BEFORE commit
            for real_path, temp_path in temp_map.items():
                if real_path.suffix == ".py":
                    try:
                        with open(temp_path, "r", encoding="utf-8") as f:
                            ast.parse(f.read())
                    except Exception as e:
                        return False, f"Syntax error in patched {real_path.name}: {e}"

            # 4. Commit (Atomic Move)
            # We need to move all temp files to real paths.
            # If any fails, we are in trouble. But os.replace is atomic-ish on POSIX.
            # On Windows it's atomic if destination exists (with proper flags) or we use replace.
            # To be safe, we keep backups of what we are about to overwrite.
            
            backups: Dict[Path, Path] = {}
            try:
                for real_path, temp_path in temp_map.items():
                    if real_path.exists():
                        bk = self.backup(real_path, originals[real_path])
                        backups[real_path] = bk

                    os.replace(str(temp_path), str(real_path))
            except Exception as e:
                self.logger.log("commit_failed", error=str(e))
                # Rollback
                for real_path, bk in backups.items():
                    try:
                        shutil.copy2(str(bk), str(real_path))
                    except Exception:
                        pass
                return False, f"Commit failed: {e}"
                

            # 5. Post-Commit Test
            if self.cfg.require_test_pass:
                ok, output = self.run_test_cmd()
                if not ok:
                    self.logger.log("test_failed_rollback", output=output[-500:])
                    # Rollback!
                    for real_path in temp_map.keys():
                        # Find latest backup
                        bk_glob = sorted(self.cfg.backups_dir.glob(f"{real_path.name}.*.bak"), reverse=True)
                        if bk_glob:
                            shutil.copy2(str(bk_glob[0]), str(real_path))
                    return False, f"Tests failed after patch: {output[-200:]}"

            return True, ""


class ErrorHandler:
    TB_RE = re.compile(r'File "([^"]+)", line (\d+), in ')

    def __init__(self, cfg: Config, logger: Logger, state: StateStore) -> None:
        self.cfg = cfg
        self.logger = logger
        self.state = state
        self.patch = PatchApplier(cfg, logger)
        self.gemini_cli = GeminiCLIClient(cfg, logger)
        self.gemini_api = GeminiApiCurlClient(cfg, logger)
        self.fallback_cli = LocalCodeCLIClient(cfg, logger)
        self.fallback_api = LocalOpenAIClient(cfg, logger)
        self.redactor = Redactor(cfg)
        
        # Advanced Features
        self.discord = DiscordNotifier(cfg)
        self.git = GitManager(cfg, logger)
        self.sanitizer = DataSanitizer(cfg, logger)
        self.reporter = ReportGenerator(cfg)

    def _select_target_from_traceback(self, stderr_tail: str) -> Tuple[Optional[Path], Optional[int]]:
        matches = list(self.TB_RE.finditer(stderr_tail))
        root = self.cfg.project_root.resolve()
        for match in reversed(matches):
            candidate = Path(match.group(1)).resolve()
            if candidate.suffix != ".py":
                continue
            try:
                candidate.relative_to(root)
            except Exception:
                continue
            if not self.patch.is_safe_target(candidate):
                continue
            return candidate, int(match.group(2))
        return None, None

    def _fallback_target(self) -> Path:
        # Try to find a likely target in allowlist
        if self.cfg.allow_modify_globs:
             # Just pick the first file that exists and matches allowlist
             for glob in self.cfg.allow_modify_globs:
                 for p in self.cfg.project_root.glob(glob):
                     if p.is_file():
                         return p
        return (self.cfg.project_root / "train.py").resolve()

    def _read_file_safe(self, path: Path) -> str:
        if not path.exists():
            return ""
        try:
            # Binary read to avoid encoding issues with partial chars
            with path.open("rb") as f:
                data = f.read(self.cfg.max_file_bytes)
            content = data.decode("utf-8", errors="ignore")
            if len(data) == self.cfg.max_file_bytes:
                content += "\n\n# <truncated>"
            return self.redactor.redact(content)
        except Exception:
            return ""

    def _build_prompt(
        self,
        target: Path,
        line_no: Optional[int],
        stderr_tail: str,
        stdout_tail: str,
        previous_error: str = "",
        is_oom: bool = False,
    ) -> str:
        content = self._read_file_safe(target)
        stderr_safe = self.redactor.redact(stderr_tail)
        stdout_safe = self.redactor.redact(stdout_tail)
        
        parts = [
            "You are a surgical Python bugfixer.",
            "Output JSON only with a top-level 'patches' array.",
            "Each patch object must include: file_path, mode, and depending on mode:",
            "- mode: unified_diff => diff: unified diff content",
            "- mode: replace_range => start_line, end_line (1-indexed, inclusive), code",
            "Rules:",
            "- file_path must stay inside project_root and match the provided targets only.",
            "- Keep changes minimal to fix the error; avoid refactors or formatting.",
            "- No markdown, no explanations, JSON only.",
            "- Do not add dependencies; standard library only.",
            f"project_root={self.cfg.project_root}",
            f"allow_modify_globs={self.cfg.allow_modify_globs}",
        ]
        
        if is_oom:
             parts.append("CRITICAL: The error is OUT OF MEMORY (OOM).")
             parts.append("You must propose a fix to REDUCE MEMORY USAGE.")
             parts.append("Examples: reduce batch size, enable gradient accumulation, use mixed precision, clear cache.")
        
        parts += [
            "",
            "Context",
            f"OS: {os.name}",
            f"Python: {sys.version.split()[0]}",
            "",
            "Training command",
            " ".join(self.cfg.train_cmd),
            "",
            "stderr tail (redacted)",
            stderr_safe,
            "",
            "stdout tail (redacted)",
            stdout_safe,
        ]
        if line_no is not None:
            parts += ["", f"Target line: {line_no}"]
        if previous_error:
            parts += ["", "Previous validation/test error", self.redactor.redact(previous_error)]
        parts += ["", "Target file content (redacted)", content]
        prompt = "\n".join(parts)
        if len(prompt) > self.cfg.max_prompt_chars:
            prompt = prompt[: self.cfg.max_prompt_chars] + "\n\n<truncated>"
        return prompt

    def _is_oom(self, stderr: str) -> bool:
        return "out of memory" in stderr.lower() or "cuda out of memory" in stderr.lower()

    def handle_failure(self, exit_code: int, stderr_tail: str, stdout_tail: str) -> bool:
        # 0. Data Sanitization Check
        if self.sanitizer.sanitize(stderr_tail):
            self.discord.notify("Data Quarantined", "Corrupt data file removed. Restarting...", 0xFFFF00)
            return True # Considered "fixed" (data removed)

        target, line_no = self._select_target_from_traceback(stderr_tail)
        if target is None:
            target = self._fallback_target()

        # Error Signature
        sanitized_err = self.redactor.redact(stderr_tail)
        signature = _sha256(f"{exit_code}:{target.name}:{sanitized_err[:500]}")
        
        # Quarantine Check
        if self.state.is_quarantined(signature):
            self.logger.log("quarantine_skip", signature=signature)
            return False

        # OOM Special Handling
        is_oom = self._is_oom(stderr_tail)
        max_retries = 1 if is_oom else self.cfg.max_retries_per_signature
        
        attempt = self.state.get_retry(signature)
        if attempt >= max_retries:
            self.logger.log("max_retries_reached", signature=signature, target=str(target))
            self.state.quarantine(signature)
            self.discord.notify("Give Up", f"Max retries reached for {target.name}", 0xFF0000)
            return False

        self.logger.log("attempt_fix", signature=signature, attempt=attempt+1, is_oom=is_oom)
        self.discord.notify("Attempting Fix", f"Target: {target.name}\nError: {sanitized_err[:200]}...", 0xFFA500)
        
        # Check Patch Mode
        if self.cfg.patch_mode == "restart-only":
            self.logger.log("patch_mode_restart_only")
            self.discord.notify("Restart Only", "PHOENIX_PATCH_MODE=restart-only. Restarting without fix.", 0xFFFF00)
            return True # Return True to restart process loop (ProcessManager loop continues if handle_failure returns True? No, handle_failure returns True if fixed.)
            # Wait, if we return True, main loop thinks it's fixed and restarts.
            # If we return False, main loop exits.
            # We want to restart. So True.
            # But we didn't fix anything. So it might crash again.
            # That's fine, that's what restart-only means.
        
        previous_error = ""
        # Try to fix
        prompt = self._build_prompt(target, line_no, stderr_tail, stdout_tail, previous_error, is_oom)
        
        try:
            # Check Analyze Only
            if self.cfg.patch_mode == "analyze-only":
                self.logger.log("patch_mode_analyze_only")
                # We still call LLM to generate patches but don't apply them
                data = self._call_llm(prompt, target)
                self.discord.notify("Analyze Only", "Patches generated but not applied (analyze-only).", 0x00FFFF)
                # Save to file for inspection
                analysis_file = self.cfg.report_dir / f"analysis_{signature[:8]}.json"
                analysis_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
                return False # Stop loop
            
            data = self._call_llm(prompt, target)
            patches = self._validate_response(data, target)
            ok, err = self.patch.apply_patch_set(patches)
            
            self.state.inc_retry(signature)
            
            if ok:
                self.logger.log("patch_success", signature=signature)
                self.discord.notify("Fix Applied", f"Successfully patched {target.name}", 0x00FF00)
                self.git.commit_fix(f"Fixed error in {target.name}")
                self.reporter.generate_daily()
                return True
            else:
                self.logger.log("patch_failed", error=err)
                self.discord.notify("Patch Failed", f"Failed to apply patch: {err}", 0xFF0000)
                # If patch failed to apply or verify, we count it as a retry.
                # If it was OOM, we stop immediately after 1 fail.
                if is_oom:
                     self.state.quarantine(signature)
                return False

        except Exception as e:
            self.logger.log("llm_error", error=str(e))
            self.discord.notify("LLM Error", str(e), 0xFF0000)
            return False

    def _call_llm(self, prompt: str, target: Path) -> Dict[str, Any]:
        # 1. Try Primary
        try:
            if self.cfg.primary_llm == "gemini_cli":
                return self.gemini_cli.request_fix(prompt)
            elif self.cfg.primary_llm == "gemini_api":
                return self.gemini_api.request_fix(prompt, str(target))
            else:
                raise ValueError(f"Unknown primary LLM: {self.cfg.primary_llm}")
        except Exception as primary_error:
            self.logger.log("primary_llm_failed", error=str(primary_error))
            
            # 2. Try Fallback
            # Check Rate Limit
            if self.state.get_retry("fallback_usage") >= self.cfg.fallback_max_per_run:
                self.logger.log("fallback_limit_reached")
                raise primary_error

            try:
                if self.cfg.fallback_llm_type == "cli":
                    if self.fallback_cli.check_health():
                        self.logger.log("fallback_attempt", type="cli")
                        self.state.inc_retry("fallback_usage")
                        return self.fallback_cli.request_fix(prompt)
                elif self.cfg.fallback_llm_type == "api":
                    if self.fallback_api.check_health():
                        self.logger.log("fallback_attempt", type="api", model=self.cfg.fallback_llm_model)
                        self.state.inc_retry("fallback_usage")
                        return self.fallback_api.request_fix(prompt)
            except Exception as fe:
                self.logger.log("fallback_failed", error=str(fe))
            
            raise

    def _validate_response(self, data: Dict[str, Any], target: Path) -> List[Dict[str, Any]]:
        patches = data.get("patches")
        if not isinstance(patches, list) or not patches:
            raise RuntimeError("LLM JSON must contain non-empty patches list")

        normalized: List[Dict[str, Any]] = []
        for patch in patches:
            if not isinstance(patch, dict):
                continue
            file_path = patch.get("file_path")
            mode = patch.get("mode")
            if not isinstance(file_path, str) or not isinstance(mode, str):
                continue
            resolved = Path(file_path).resolve()
            if not self.patch.is_safe_target(resolved):
                raise RuntimeError(f"Unsafe target path {resolved}")
            
            normalized_patch = {"file_path": str(resolved), "mode": mode}
            if mode == "unified_diff":
                normalized_patch["diff"] = patch.get("diff", "")
            else:
                normalized_patch.update({
                    "start_line": patch.get("start_line"),
                    "end_line": patch.get("end_line"),
                    "code": patch.get("code")
                })
            normalized.append(normalized_patch)
        return normalized



class GraphGenerator:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        
    def generate_loss_graph(self, data: list) -> str:
        # Dummy implementation
        return ""

class ProcessManager:
    def __init__(self, cfg: Config, logger: Logger) -> None:
        self.cfg = cfg
        self.logger = logger

    def _start_process(self) -> subprocess.Popen:
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
        return subprocess.Popen(
            self.cfg.train_cmd,
            cwd=str(self.cfg.project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
            start_new_session=os.name != "nt",
            creationflags=creationflags,
        )

    def _pump_stream(self, stream: Any, buffer: RollingBuffer, to_stderr: bool, heartbeat: Dict[str, float], lock: threading.Lock, tracker: Optional[ProgressTracker] = None) -> None:
        try:
            for line in iter(stream.readline, ""):
                with lock:
                    heartbeat["last"] = time.time()
                buffer.add(line)
                
                if tracker and not to_stderr:
                    tracker.parse(line)
                    
                if to_stderr:
                    sys.stderr.write(line)
                    sys.stderr.flush()
                else:
                    sys.stdout.write(line)
                    sys.stdout.flush()
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def _kill_process_tree(self, proc: subprocess.Popen) -> None:
        if proc.poll() is not None:
            return
        self.logger.log("killing_process_tree", pid=proc.pid)
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
            else:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except Exception:
                    proc.kill()
        finally:
            try:
                proc.wait(timeout=10)
            except Exception:
                pass

    def run_training(self, guards: SafetyGuards, tracker: ProgressTracker, cost: CostEstimator, bot: DiscordBot) -> Tuple[int, str, str]:
        self.logger.log("start_training", cmd=self.cfg.train_cmd)
        proc = self._start_process()

        out_buf = RollingBuffer(self.cfg.log_tail_lines)
        err_buf = RollingBuffer(self.cfg.log_tail_lines)

        heartbeat = {"last": time.time()}
        hb_lock = threading.Lock()
        stop_event = threading.Event()

        t_out = threading.Thread(
            target=self._pump_stream, args=(proc.stdout, out_buf, False, heartbeat, hb_lock, tracker), daemon=True
        )
        t_err = threading.Thread(
            target=self._pump_stream, args=(proc.stderr, err_buf, True, heartbeat, hb_lock, None), daemon=True
        )
        t_out.start()
        t_err.start()

        def watchdog() -> None:
            timeout = self.cfg.heartbeat_timeout_min * 60
            while not stop_event.is_set():
                time.sleep(5)
                if proc.poll() is not None:
                    return
                
                # 1. Heartbeat Check
                if timeout > 0:
                    with hb_lock:
                        idle = time.time() - heartbeat["last"]
                    if idle >= timeout:
                        self.logger.log("heartbeat_timeout", idle_sec=idle)
                        self._kill_process_tree(proc)
                        stop_event.set()
                        return
                
                # 2. Safety Guards & Cost Check (every 60s approx)
                if int(time.time()) % 60 < 5:
                    if not guards.check_thermal():
                        self.logger.log("safety_stop", reason="thermal")
                        self._kill_process_tree(proc)
                        stop_event.set()
                        return
                    if not guards.check_disk():
                        self.logger.log("safety_stop", reason="disk_space")
                        self._kill_process_tree(proc)
                        stop_event.set()
                        return
                    
                    # Update Cost
                    cost.update(guards.get_avg_power())
                    
                    # 3. Deadline & Pacing Check
                    if tracker.should_stop_early():
                        self.logger.log("pacing_stop", target=tracker.virtual_target_step)
                        guards.discord.notify("🏁 Pacing Complete", f"Reached adjusted target {tracker.virtual_target_step} to meet deadline.", 0x00FF00)
                        # Graceful stop
                        proc.send_signal(signal.CTRL_C_EVENT if os.name == 'nt' else signal.SIGINT)
                        try:
                            proc.wait(timeout=30)
                        except subprocess.TimeoutExpired:
                            self._kill_process_tree(proc)
                        stop_event.set()
                        return

                    if self.cfg.deadline_time:
                        now_str = time.strftime("%H:%M")
                        if now_str == self.cfg.deadline_time:
                            # Hard deadline reached
                            self.logger.log("deadline_reached", deadline=self.cfg.deadline_time)
                            guards.discord.notify("⏰ Deadline Reached", f"Stopping training at {now_str}", 0xFFFF00)
                            self._kill_process_tree(proc)
                            stop_event.set()
                            return
                
                # 4. Discord Command Polling (every 10s)
                if int(time.time()) % 10 < 2:
                    bot.poll_commands()
                    if bot.stop_requested:
                        self.logger.log("discord_stop_requested")
                        # Graceful stop
                        proc.send_signal(signal.CTRL_C_EVENT if os.name == 'nt' else signal.SIGINT)
                        try:
                            proc.wait(timeout=30)
                        except subprocess.TimeoutExpired:
                            self._kill_process_tree(proc)
                        stop_event.set()
                        return
                    
                    if bot.status_requested:
                        bot.status_requested = False
                        tracker._notify_status() # Force status update
                        # Add extra stats
                        fields = [
                            {"name": "GPU Temp", "value": f"{guards.power_samples[-1] if guards.power_samples else 0}W (approx)", "inline": True},
                            {"name": "Cost", "value": f"${cost.get_cost():.4f}", "inline": True},
                        ]
                        guards.discord.notify("📊 Status Report", "On demand status update", 0x00FFFF, fields=fields)

        watchdog_thread = threading.Thread(target=watchdog, daemon=True)
        watchdog_thread.start()

        rc = proc.wait()
        stop_event.set()
        t_out.join(timeout=2)
        t_err.join(timeout=2)
        watchdog_thread.join(timeout=2)
        
        duration = time.time() - heartbeat["last"] # Approx
        self.logger.log("process_exit", rc=rc)

        return rc, err_buf.tail_text(), out_buf.tail_text()


def acquire_lock(cfg: Config, logger: Logger) -> bool:
    pid = os.getpid()
    lock_file = cfg.lock_path
    
    if lock_file.exists():
        try:
            content = lock_file.read_text().strip()
            old_pid = int(content.split()[0])
            # Check if process exists
            if os.name == "nt":
                # Simple check using tasklist
                proc = subprocess.run(["tasklist", "/FI", f"PID eq {old_pid}", "/NH"], capture_output=True, text=True)
                if str(old_pid) in proc.stdout:
                    logger.log("lock_held", pid=old_pid)
                    return False
            else:
                try:
                    os.kill(old_pid, 0)
                    logger.log("lock_held", pid=old_pid)
                    return False
                except OSError:
                    pass # Process dead
            
            logger.log("stale_lock_removed", old_pid=old_pid)
            lock_file.unlink()
        except Exception:
            pass

    try:
        lock_file.write_text(f"{pid} {_now_iso()}")
        return True
    except Exception:
        return False


def _load_dotenv() -> None:
    """Load .env file from current directory if it exists (zero-dependency)."""
    env_path = Path(".env")
    if not env_path.exists():
        return
    
    try:
        with env_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    # Remove quotes if present
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    
                    if key and key not in os.environ:
                        os.environ[key] = value
    except Exception:
        pass

def main() -> int:
    # Critical: Fix CWD before Config init to prevent System32 issues
    cwd = Path.cwd()
    script_dir = Path(__file__).parent.resolve()
    
    if "system32" in str(cwd).lower() or cwd != script_dir:
        # If we are in System32 or not in script dir (likely Task Scheduler issue),
        # switch to script directory immediately.
        try:
            os.chdir(script_dir)
            cwd = script_dir
            # We can't log yet because Config/Logger aren't ready, but this is a safety fix.
        except Exception:
            pass

    _load_dotenv() # Load env vars from .env file

    cfg = Config()
    cfg.ensure_dirs()
    redactor = Redactor(cfg)
    logger = Logger(cfg, redactor)
    
    if not acquire_lock(cfg, logger):
        print("Could not acquire lock. Exiting.")
        return 1

    state = StateStore(cfg)
    handler = ErrorHandler(cfg, logger, state)
    process_manager = ProcessManager(cfg, logger)
    guards = SafetyGuards(cfg, logger, handler.discord)
    tracker = ProgressTracker(cfg, handler.discord)
    cost = CostEstimator(cfg)
    graph_gen = GraphGenerator(cfg)
    bot = DiscordBot(cfg, logger, handler.discord, tracker, graph_gen)
    validator = DataValidator(cfg, logger, handler.discord)

    logger.log("startup", config=dataclasses.asdict(cfg), cwd=str(cwd))
    
    if not cfg.allow_modify_globs:
        logger.log("warning_empty_allowlist")
        handler.discord.notify("⚠️ Security Warning", "PHOENIX_ALLOWLIST is empty. No files will be modified.", 0xFFFF00)
        
    # Data Validation
    if not validator.validate():
        logger.log("data_validation_failed")
        # We don't exit, just warn.
    
    # Hardware Recommendations
    vram = cfg.specs.get("gpu_vram_gb", 0)
    ram = cfg.specs.get("ram_gb", 0)
    gpu_name = cfg.specs.get("gpu_name", "Unknown")
    
    rec_model = "Phi-3 Mini / StarCoder2 3B"
    if vram >= 40:
        rec_model = "DeepSeek Coder 33B / Llama-3 70B (Quantized)"
    elif vram >= 20:
        rec_model = "Code Llama 34B (Quantized) / StarCoder2 15B"
    elif vram >= 12:
        rec_model = "Code Llama 13B / StarCoder2 7B"
        
    logger.log("hardware_detected", 
        gpu=gpu_name, 
        vram_gb=vram, 
        ram_gb=ram, 
        recommended_fallback_model=rec_model
    )

    while True:
        # Pre-flight check
        if not guards.check_disk():
            logger.log("startup_aborted", reason="low_disk")
            time.sleep(60)
            continue
        
        # Check if resume requested (if we were stopped)
        # Actually, if we are here, we are starting or restarting.
        # If stop was requested, we should wait until resume is requested.
        if bot.stop_requested:
            logger.log("paused_by_user")
            while not bot.resume_requested:
                time.sleep(10)
                bot.poll_commands()
            bot.stop_requested = False
            bot.resume_requested = False
            logger.log("resumed_by_user")

        exit_code, stderr_tail, stdout_tail = process_manager.run_training(guards, tracker, cost, bot)
        if exit_code == 0:
            logger.log("training_success")
            handler.discord.notify(
                "🎉 Training Complete", 
                f"Total Cost: ${cost.get_cost():.2f}\nDuration: {tracker.get_eta_str()}", 
                0x00FF00
            )
            return 0

        try:
            fixed = handler.handle_failure(exit_code, stderr_tail, stdout_tail)
        except Exception as exc:
            logger.log("fatal_error", error=str(exc), traceback=traceback.format_exc())
            return 2

        if not fixed:
            if cfg.cooldown_seconds_on_stop > 0:
                logger.log("cooldown", seconds=cfg.cooldown_seconds_on_stop)
                time.sleep(cfg.cooldown_seconds_on_stop)
            logger.log("give_up")
            return 1

        logger.log("restarting")


if __name__ == "__main__":
    raise SystemExit(main())
