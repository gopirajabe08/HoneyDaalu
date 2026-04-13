"""
macOS sleep prevention for live trading engines.

Prevents the Mac from sleeping during active trading sessions.
Uses 'sudo pmset disablesleep 1' for lid-close protection,
falls back to 'caffeinate' if pmset is not available.

Used by AutoTrader and SwingTrader (live engines only).
"""

import subprocess
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SleepManager:
    """Manages macOS sleep prevention for a trading engine.

    Args:
        name: Trader identifier for log messages (e.g. 'AutoTrader').
    """

    def __init__(self, name: str):
        self.name = name
        self._caffeinate_proc: Optional[subprocess.Popen] = None
        self._sleep_mode: Optional[str] = None  # "pmset" | "caffeinate" | None

    @property
    def mode(self) -> Optional[str]:
        """Current sleep prevention mode."""
        return self._sleep_mode

    def prevent_sleep(self):
        """Enable sleep prevention (macOS only, no-op on Linux)."""
        import platform
        if platform.system() == "Linux":
            self._sleep_mode = "linux"
            logger.info(f"[{self.name}] Linux server — no sleep prevention needed")
            return

        self.allow_sleep()  # Clean up any previous state

        # Try pmset (requires setup_sleep_prevention.sh)
        try:
            result = subprocess.run(
                ["sudo", "-n", "pmset", "disablesleep", "1"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                self._sleep_mode = "pmset"
                logger.info(f"[{self.name}] Sleep prevention ENABLED (pmset — lid-close safe)")
                return
            else:
                logger.warning(f"[{self.name}] pmset failed ({result.stderr.strip()}), falling back to caffeinate")
        except Exception as e:
            logger.warning(f"[{self.name}] pmset exception: {e}, falling back to caffeinate")

        # Fallback: caffeinate (lid must stay open)
        try:
            self._caffeinate_proc = subprocess.Popen(
                ["caffeinate", "-d", "-i", "-s"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            self._sleep_mode = "caffeinate"
            logger.info(f"[{self.name}] Sleep prevention ENABLED (caffeinate PID: {self._caffeinate_proc.pid} — lid must stay open)")
        except Exception as e:
            self._sleep_mode = None
            logger.warning(f"[{self.name}] No sleep prevention available: {e}")

    def allow_sleep(self):
        """Disable sleep prevention and clean up."""
        if self._sleep_mode == "pmset":
            try:
                subprocess.run(
                    ["sudo", "-n", "pmset", "disablesleep", "0"],
                    capture_output=True, text=True, timeout=5,
                )
                logger.info(f"[{self.name}] Sleep prevention DISABLED (pmset)")
            except Exception as e:
                logger.warning(f"[{self.name}] Failed to re-enable sleep: {e}")

        if self._caffeinate_proc is not None:
            try:
                self._caffeinate_proc.terminate()
                self._caffeinate_proc.wait(timeout=3)
            except Exception:
                try:
                    self._caffeinate_proc.kill()
                except Exception:
                    pass
            self._caffeinate_proc = None

        self._sleep_mode = None
