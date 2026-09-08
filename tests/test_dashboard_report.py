import unittest
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory

from praecursor.collectors.fake_market_data_source import FakeMarketDataSource
from praecursor.data.data_manager import DataManager
from praecursor.reporting.dashboard import DEFAULT_DASHBOARD_REPORT, ScannerDashboardWriter
from praecursor.storage.price_cache import PriceCache
from praecursor.workflows.scanner import ScannerWorkflow


class StrictHTMLValidator(HTMLParser):
    VOID_TAGS = {
        'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
        'link', 'meta', 'param', 'source', 'track', 'wbr', '!doctype'
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t not in self.VOID_TAGS:
            self.stack.append((t, self.getpos()))

    def handle_endtag(self, tag):
        t = tag.lower()
        if t in self.VOID_TAGS:
            return
        if not self.stack:
            self.errors.append(f"Line {self.getpos()[0]}:{self.getpos()[1]} - Unexpected </{t}> with empty stack")
        elif self.stack[-1][0] == t:
            self.stack.pop()
        else:
            open_tags = [x[0] for x in self.stack]
            if t in open_tags:
                while self.stack and self.stack[-1][0] != t:
                    popped, pos = self.stack.pop()
                    self.errors.append(f"Unclosed tag <{popped}> from line {pos[0]}:{pos[1]} when encountering </{t}>")
                self.stack.pop()
            else:
                self.errors.append(f"Line {self.getpos()[0]}:{self.getpos()[1]} - Unexpected </{t}> (stack top: <{self.stack[-1][0]}>)")

    def validate(self, content: str) -> tuple[bool, list[str]]:
        self.feed(content)
        if self.stack:
            for tag, pos in self.stack:
                self.errors.append(f"Unclosed tag <{tag}> opened at line {pos[0]}:{pos[1]}")
        return len(self.errors) == 0, self.errors


class DashboardReportTests(unittest.TestCase):
    def test_dashboard_writer_creates_html(self):
        with TemporaryDirectory() as directory:
            directory_path = Path(directory)
            cache = PriceCache(database_path=directory_path / "dashboard.db")
            DataManager([FakeMarketDataSource()], minimum_bars=200, price_cache=cache).fetch_history(
                "COMI",
                date(2025, 1, 1),
                date(2026, 7, 27),
            )
            result = ScannerWorkflow(
                lookback_days=450,
                minimum_bars=200,
                source_name="fake_market_data",
                market_data_source=FakeMarketDataSource(),
                price_cache=cache,
                enable_consensus=False,
                enable_history=False,
            ).run(
                symbols=["COMI"],
                end_date=date(2026, 7, 27),
                report_path=directory_path / "ranking.csv",
                next_day_report_path=directory_path / "next.csv",
                markdown_report_path=directory_path / "ranking.md",
                dashboard_report_path=directory_path / "dashboard.html",
            )
            output_path = ScannerDashboardWriter().write(result, directory_path / "dashboard2.html")
            html = output_path.read_text(encoding="utf-8")

        self.assertTrue("PRAECURSOR" in html.upper())
        self.assertTrue("NEXT-DAY" in html.upper())
        self.assertTrue("OPPORTUNITY" in html.upper())

        validator = StrictHTMLValidator()
        is_valid, errors = validator.validate(html)
        self.assertTrue(is_valid, f"Generated HTML has malformed or unclosed tags: {errors}")

    def test_reports_dashboard_html_has_zero_unclosed_or_malformed_tags(self):
        if DEFAULT_DASHBOARD_REPORT.exists():
            html = DEFAULT_DASHBOARD_REPORT.read_text(encoding="utf-8")
            validator = StrictHTMLValidator()
            is_valid, errors = validator.validate(html)
            self.assertTrue(is_valid, f"reports/dashboard.html has malformed or unclosed tags: {errors}")


class TestMissionControlEndpoints(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from praecursor.cli.dashboard import app
        self.client = TestClient(app)

    def test_mission_control_homepage_renders_and_validates(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("PRAECURSOR", res.text)
        self.assertIn("v6.3 Institutional Alpha", res.text)
        self.assertIn("RUN SCAN", res.text)
        self.assertIn("Browse Previous Scan Dashboard", res.text)

        validator = StrictHTMLValidator()
        is_valid, errors = validator.validate(res.text)
        self.assertTrue(is_valid, f"Mission Control HTML has unclosed tags: {errors}")

    def test_api_status_endpoint_structure(self):
        res = self.client.get("/api/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        for expected_key in ["running", "stage", "stage_name", "processed", "total", "percent", "telegram_status", "completed"]:
            self.assertIn(expected_key, data, f"Missing key '{expected_key}' in /api/status")

    def test_dashboard_terminal_route(self):
        res = self.client.get("/dashboard", follow_redirects=False)
        self.assertIn(res.status_code, (200, 303))
        if res.status_code == 200:
            self.assertIn("MISSION CONTROL", res.text)


if __name__ == "__main__":
    unittest.main()


