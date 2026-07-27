import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SCANNER_SETTINGS = ROOT / "config" / "scanner.json"


@dataclass(frozen=True)
class ScannerSettings:
    """Configurable defaults for scanner runs."""

    lookback_days: int = 450
    consensus_lookback_days: int = 180
    minimum_bars: int = 10
    enable_consensus: bool = True
    enable_history: bool = True
    enable_archive_reports: bool = True

    @classmethod
    def from_json(cls, path: str | Path = DEFAULT_SCANNER_SETTINGS) -> "ScannerSettings":
        config_path = Path(path)

        if not config_path.exists():
            return cls()

        with config_path.open(encoding="utf-8") as file:
            raw_settings: dict[str, Any] = json.load(file)

        return cls(
            lookback_days=int(raw_settings.get("lookback_days", cls.lookback_days)),
            consensus_lookback_days=int(
                raw_settings.get("consensus_lookback_days", cls.consensus_lookback_days)
            ),
            minimum_bars=int(raw_settings.get("minimum_bars", cls.minimum_bars)),
            enable_consensus=bool(raw_settings.get("enable_consensus", cls.enable_consensus)),
            enable_history=bool(raw_settings.get("enable_history", cls.enable_history)),
            enable_archive_reports=bool(
                raw_settings.get("enable_archive_reports", cls.enable_archive_reports)
            ),
        )
