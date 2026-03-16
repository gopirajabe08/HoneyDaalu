"""
JSON state persistence for trader engines.

Provides atomic-write state saving (write to temp file, then rename)
to prevent corruption from crashes mid-write. Used by all 8 traders.
"""

import json
import os
import logging
import tempfile

logger = logging.getLogger(__name__)


def get_state_path(filename: str) -> str:
    """Get absolute path for a state file in the backend root directory.

    Args:
        filename: State file name, e.g. '.auto_trader_state.json'

    Returns:
        Absolute path to the state file.
    """
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(backend_dir, filename)


def save_state(filepath: str, state: dict, context: str = ""):
    """Atomically save trader state to a JSON file.

    Writes to a temporary file first, then renames (atomic on POSIX).
    This prevents corruption if the process crashes mid-write.

    Args:
        filepath: Absolute path to the state file.
        state: Dictionary to serialize as JSON.
        context: Trader name for log messages (e.g. 'AutoTrader').
    """
    try:
        dir_name = os.path.dirname(filepath)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(state, f, indent=2, default=str)
            os.replace(tmp_path, filepath)
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except Exception as e:
        logger.warning(f"[{context}] Failed to save state: {e}")


def load_state(filepath: str, context: str = "") -> dict:
    """Load trader state from a JSON file.

    Args:
        filepath: Absolute path to the state file.
        context: Trader name for log messages (e.g. 'AutoTrader').

    Returns:
        Parsed state dictionary, or empty dict if file doesn't exist or is corrupt.
    """
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"[{context}] Failed to load state from {filepath}: {e}")
        return {}
