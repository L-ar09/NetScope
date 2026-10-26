"""Configurable, application-level faults for repeatable NetScope experiments."""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

DEFAULT_FAULT_CONFIG = Path(__file__).resolve().parents[1] / "data" / "fault_config.json"
WRONG_LOOKUP_ADDRESS = "192.0.2.99"


@dataclass(frozen=True)
class FaultSettings:
    """Validated fault configuration loaded for one request."""

    delay_ms: int = 0
    udp_drop_probability: float = 0.0
    wrong_lookup: bool = False
    tcp_disconnect: bool = False

    @property
    def enabled(self) -> bool:
        return any((self.delay_ms, self.udp_drop_probability, self.wrong_lookup, self.tcp_disconnect))


class FaultInjector:
    """Reload a local JSON configuration before each request.

    These faults model application behavior only. A dropped UDP response means
    the server deliberately did not reply; it does not prove network loss.
    """

    def __init__(
        self,
        config_path: Path = DEFAULT_FAULT_CONFIG,
        random_value: Callable[[], float] = random.random,
    ) -> None:
        self.config_path = Path(config_path)
        self._random_value = random_value

    def settings(self) -> FaultSettings:
        """Read and validate the current JSON configuration."""
        if not self.config_path.exists():
            return FaultSettings()
        with self.config_path.open(encoding="utf-8") as source:
            raw = json.load(source)
        if not isinstance(raw, dict):
            raise ValueError("Fault configuration must be a JSON object")
        delay_ms = raw.get("delay_ms", 0)
        drop_probability = raw.get("udp_drop_probability", 0.0)
        if not isinstance(delay_ms, int) or delay_ms < 0 or delay_ms > 60_000:
            raise ValueError("delay_ms must be an integer from 0 to 60000")
        if not isinstance(drop_probability, (int, float)) or not 0 <= drop_probability <= 1:
            raise ValueError("udp_drop_probability must be between 0 and 1")
        return FaultSettings(
            delay_ms=delay_ms,
            udp_drop_probability=float(drop_probability),
            wrong_lookup=bool(raw.get("wrong_lookup", False)),
            tcp_disconnect=bool(raw.get("tcp_disconnect", False)),
        )

    @staticmethod
    def fault_type(settings: FaultSettings, service: str) -> str:
        """Return the most relevant configured fault label for a service."""
        if service == "lookup" and settings.udp_drop_probability:
            return "udp_response_drop"
        if service == "lookup" and settings.wrong_lookup:
            return "wrong_lookup"
        if service in {"echo", "file_transfer"} and settings.tcp_disconnect:
            return "tcp_disconnect"
        if settings.delay_ms:
            return "artificial_delay"
        return "none"

    @staticmethod
    def apply_delay(settings: FaultSettings) -> None:
        if settings.delay_ms:
            time.sleep(settings.delay_ms / 1000)

    def should_drop_udp_response(self, settings: FaultSettings) -> bool:
        return settings.udp_drop_probability > 0 and self._random_value() < settings.udp_drop_probability

    @staticmethod
    def resolve_lookup(domain: str, records: dict[str, str], settings: FaultSettings) -> str:
        if settings.wrong_lookup:
            return WRONG_LOOKUP_ADDRESS
        return records.get(domain, "NOT_FOUND")
