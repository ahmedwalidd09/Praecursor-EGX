import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from praecursor.core.settings import ScannerSettings


class ScannerSettingsTests(unittest.TestCase):
    def test_defaults_when_file_missing(self):
        settings = ScannerSettings.from_json("missing-file.json")
        self.assertEqual(settings.lookback_days, 450)
        self.assertTrue(settings.enable_consensus)

    def test_loads_json_settings(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "scanner.json"
            path.write_text(
                json.dumps(
                    {
                        "lookback_days": 100,
                        "consensus_lookback_days": 50,
                        "minimum_bars": 5,
                        "enable_consensus": False,
                    }
                ),
                encoding="utf-8",
            )
            settings = ScannerSettings.from_json(path)

        self.assertEqual(settings.lookback_days, 100)
        self.assertEqual(settings.consensus_lookback_days, 50)
        self.assertEqual(settings.minimum_bars, 5)
        self.assertFalse(settings.enable_consensus)


if __name__ == "__main__":
    unittest.main()
