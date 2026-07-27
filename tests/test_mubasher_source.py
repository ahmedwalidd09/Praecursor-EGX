import unittest
from datetime import date

from praecursor.collectors.mubasher_source import MubasherSource


class MubasherSourceTests(unittest.TestCase):
    def test_parse_latest_quote_from_sample_html(self):
        html = """
        <h1>EFG Holding (HRHO)</h1>
        <div>Last update: 11:57 AM market time.</div>
        <div>26.97</div>
        <div>Open26.95</div>
        <div>Previous Close26.95</div>
        <div>High27.16</div>
        <div>Low26.81</div>
        <div>Volume1,099,660</div>
        """
        source = MubasherSource()
        text = source._extract_text(html)
        bar, warnings = source._parse_latest_quote("HRHO", date(2026, 7, 27), text)

        self.assertEqual(bar.close, 26.97)
        self.assertEqual(bar.open, 26.95)
        self.assertEqual(bar.high, 27.16)
        self.assertEqual(bar.low, 26.81)
        self.assertEqual(bar.volume, 1_099_660)
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
