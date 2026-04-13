"""
Sleep prevention — no-op on EC2 Linux server.
Kept as a stub so all engines that import it don't break.
"""

import logging

logger = logging.getLogger(__name__)


class SleepManager:
    def __init__(self, name: str):
        self.name = name
        self._sleep_mode = "linux"

    @property
    def mode(self):
        return self._sleep_mode

    def prevent_sleep(self):
        pass

    def allow_sleep(self):
        pass
