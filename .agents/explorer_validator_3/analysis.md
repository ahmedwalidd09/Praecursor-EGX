# Praecursor-EGX HTML Validation & Test Strategy Analysis

**Author:** teamwork_preview_explorer (explorer_validator_3)  
**Date:** 2026-08-08  
**Working Directory:** `C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\.agents\explorer_validator_3`  
**Target Project:** `Praecursor-EGX`  

---

## 1. Executive Summary

This report provides a comprehensive analysis of HTML report generation, pipeline stability, test suite architecture, and programmatic HTML validation for Praecursor-EGX.

### Key Discoveries:
1. **HTML Structural Bug Found**: In `src/praecursor/reporting/dashboard.py` (line 80), there is an extra unmatched closing `</div>` tag (`</div> <!-- end live-pulse tab -->`), which causes the generated `reports/dashboard.html` to contain an unexpected `</div>` closing tag at line 563 that mismatches the document structure (attempting to close `<main>` with `</div>`).
2. **Existing Test Coverage Gaps**: Existing test in `tests/test_dashboard_report.py` only performs simple substring assertions (`assertIn("Praecursor-EGX", html)`) without verifying HTML tree structural validity or unclosed/mismatched tags.
3. **Network Isolation & Mocking Standard**: `tests/conftest.py` provides an `autouse=True` fixture `block_network_access` that intercepts `socket.socket.connect` and blocks outbound external connections, raising `RuntimeError`. This guarantees 100% mocked API calls and zero API credit usage during automated test runs.
4. **Validator Empirical Verification**: We designed a Python standard library `html.parser.HTMLParser` validator and ran it against the generated `reports/dashboard.html`. The validator successfully detected and flagged the exact extra `</div>` tag with line and column precision.

---

## 2. Codebase Audit Findings

### 2.1 Existing Tests (`tests/`)
- **`tests/test_dashboard_report.py`**:
  - Sets up `ScannerWorkflow` with `FakeMarketDataSource()` and generates a dashboard via `ScannerDashboardWriter().write()`.
  - Verifies presence of strings: `"Praecursor-EGX"`, `"Next-Day Candidates"`, `"Swing Candidates"`.
  - *Limitation*: Does not perform tag hierarchy validation or syntax checking.
- **`tests/conftest.py`**:
  - Implements `block_network_access(monkeypatch)` fixture.
  - Automatically active for all tests (`autouse=True`).
  - Allows loopback (`127.0.0.1`, `localhost`, `::1`), blocks external IPs.
  - Fulfills R3 (Zero API credit burn / 100% mocked API calls during testing).
- **`tests/test_network_isolation.py`**:
  - Unit test explicitly confirming that external network socket attempts raise `RuntimeError`.

### 2.2 Dashboard Generation Mechanics
- **`src/praecursor/reporting/dashboard.py`**:
  - Class `ScannerDashboardWriter`: Renders dark-themed HTML report containing top bar, tabs ("Live Pulse" and "Accuracy Tracker"), candidate panels, score heatmap table, ranking table, and TradingView modal.
  - Line 54: `<div id="live-pulse" class="tab-content">` (opens level 1 div)
  - Line 58: `<div class="grid layout">` (opens level 2 div)
  - Line 59: `<div class="main-content">` (opens level 3 div)
  - Line 77: `</div>` (closes main-content)
  - Line 78: `</div>` (closes grid layout)
  - Line 79: `</div>` (closes live-pulse)
  - **Line 80**: `</div> <!-- end live-pulse tab -->` (**BUG**: Extra 4th closing div tag!)
- **`src/praecursor/cli/dashboard.py`**:
  - FastAPI CLI server wrapper that serves `reports/dashboard.html` and injects auto-refresh meta tag and a Floating Action Button (FAB) `triggerScan()` script.

### 2.3 Pipeline Execution Tools
- **`tools/regenerate_dashboard.py`**:
  - Fetches latest scanner run from `SignalHistoryStore` (SQLite DB) and calls `ScannerDashboardWriter().write(run_result)`.
  - Execution test result: Exit code 0, completed in ~1.5s.
- **`tools/run_autonomous_pipeline.py`**:
  - Autonomous 4-stage pipeline runner (Scanner -> Retraining -> Regenerate Dashboard -> Telegram Broadcast).
  - Accepts `--date YYYY-MM-DD` and `--force`.
  - Execution test result: Checks trading day logic (`is_egx_trading_day`), executes sub-tools with retry logic and logs status.

---

## 3. Programmatic HTML Validator Mechanism Design

### 3.1 Standard Library Choice: `html.parser.HTMLParser` vs `xml.etree.ElementTree`

| Criteria | `xml.etree.ElementTree` | `html.parser.HTMLParser` (Recommended) |
|---|---|---|
| Standard Library | Yes | Yes |
| HTML5 Void Tags (`<meta>`, `<br>`, `<img>`) | Fails (requires explicit XHTML self-closing `<meta ... />`) | Natively supported without false errors |
| Named Entities (`&times;`, `&nbsp;`) | Fails (`ParseError: undefined entity`) | Supported (`convert_charrefs=True`) |
| DOCTYPE Declaration (`<!doctype html>`) | Fails on doctype parsing | Supported via `handle_decl` |
| Tag Stack Diagnostics | Generic `ParseError` at character offset | Precise line number, column offset, and unclosed tag stack trace |

**Conclusion**: `html.parser.HTMLParser` is superior for HTML5 dashboard validation as it understands HTML5 void tag semantics and named character entities while enforcing strict start/end tag matching.

### 3.2 Programmatic HTML Validator Implementation

Below is the complete implementation design for `StrictHTMLValidator` using Python standard library:

```python
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Tuple


class StrictHTMLValidator(HTMLParser):
    """
    Standard-library based HTML5 tag validator for Praecursor-EGX reports.
    Ensures zero unclosed, mismatched, or unexpected closing tags.
    """

    # HTML5 standard void elements (must NOT have closing tags)
    VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img",
        "input", "link", "meta", "param", "source", "track", "wbr"
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: List[Tuple[str, Tuple[int, int]]] = []  # List of (tag_name, (line, col))
        self.errors: List[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        tag_lower = tag.lower()
        if tag_lower not in self.VOID_TAGS:
            self.stack.append((tag_lower, self.getpos()))

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in self.VOID_TAGS:
            return

        if not self.stack:
            line, col = self.getpos()
            self.errors.append(f"Line {line}:{col} - Unexpected closing tag </{tag_lower}> with empty tag stack.")
            return

        top_tag, (start_line, start_col) = self.stack[-1]
        if top_tag == tag_lower:
            self.stack.pop()
        else:
            line, col = self.getpos()
            open_tags = [t[0] for t in self.stack]
            if tag_lower in open_tags:
                unclosed = []
                while self.stack and self.stack[-1][0] != tag_lower:
                    unclosed.append(self.stack.pop())
                self.stack.pop()  # Pop matching start tag
                unclosed_str = ", ".join([f"<{t[0]}> (line {t[1][0]})" for t in unclosed])
                self.errors.append(
                    f"Line {line}:{col} - Closing tag </{tag_lower}> auto-closed unclosed tags: {unclosed_str}"
                )
            else:
                self.errors.append(
                    f"Line {line}:{col} - Unexpected closing tag </{tag_lower}> (expected </{top_tag}> matching line {start_line})"
                )

    def validate(self, html_content: str) -> Tuple[bool, List[str]]:
        self.errors.clear()
        self.stack.clear()
        try:
            self.feed(html_content)
            self.close()
        except Exception as exc:
            self.errors.append(f"HTML Parser exception: {exc}")

        if self.stack:
            unclosed_fmt = ", ".join([f"<{t[0]}> (line {t[1][0]})" for t in self.stack])
            self.errors.append(f"Unclosed tags remaining at end of file: {unclosed_fmt}")

        return len(self.errors) == 0, list(self.errors)


def validate_html_file(file_path: Path) -> Tuple[bool, List[str]]:
    validator = StrictHTMLValidator()
    content = file_path.read_text(encoding="utf-8")
    return validator.validate(content)
```

### 3.3 Test Suite Integration (`tests/test_dashboard_report.py`)

Integrate `StrictHTMLValidator` directly into `tests/test_dashboard_report.py`:

```python
def test_dashboard_html_has_zero_malformed_or_unclosed_tags(self):
    """Verify that generated reports/dashboard.html has zero unclosed or malformed tags."""
    output_path = DEFAULT_DASHBOARD_REPORT
    if not output_path.exists():
        # Regenerate if missing
        from tools.regenerate_dashboard import main as regen_main
        regen_main()
    
    valid, errors = validate_html_file(output_path)
    self.assertTrue(
        valid,
        f"HTML Validation failed with {len(errors)} error(s):\n" + "\n".join(errors)
    )
```

---

## 4. Empirical Test Verification Protocol for Reviewers & Challengers

The following verification steps MUST be performed by Reviewers and Challengers to validate the fix and pipeline stability:

### Step 1: Regenerate Dashboard Script Execution
- **Command**: `python tools/regenerate_dashboard.py`
- **Verification Criteria**:
  - Exit code is `0`.
  - Stdout logs: `INFO:__main__:Dashboard instantly regenerated from history!`.
  - Zero Python tracebacks or uncaught exceptions.

### Step 2: Autonomous Pipeline Date Trigger Execution
- **Command**: `python tools/run_autonomous_pipeline.py --date 2026-08-01`
- **Verification Criteria**:
  - Exit code is `0`.
  - Log output confirms execution or graceful non-trading day skip handling (`SKIPPED: Non-trading day...` or `PROCESSING: ...`).
  - All 4 stages (Scanner -> Retraining -> Regenerate Dashboard -> Telegram Broadcast) execute without crashing.

### Step 3: Zero Unclosed / Malformed Tags in `reports/dashboard.html`
- **Command**: `pytest tests/test_dashboard_report.py`
- **Verification Criteria**:
  - Test suite passes with 100% success.
  - `StrictHTMLValidator` returns `valid == True` and `len(errors) == 0` for `reports/dashboard.html`.

### Step 4: Low Credit Usage / 100% Mocked API Calls Audit
- **Command**: `pytest`
- **Verification Criteria**:
  - The `block_network_access` fixture in `tests/conftest.py` is active.
  - Any unmocked external network connection attempt triggers `RuntimeError`, guaranteeing zero LLM/API credit consumption during testing.

---

## 5. Summary Table of Requirements & Solutions

| Requirement | Audit Finding | Recommended Solution |
|---|---|---|
| **R1. HTML Generation Logic** | Line 80 of `src/praecursor/reporting/dashboard.py` contains extra `</div> <!-- end live-pulse tab -->` | Remove extra `</div>` at line 80 in `src/praecursor/reporting/dashboard.py`. |
| **R2. Pipeline Execution Stability** | `tools/regenerate_dashboard.py` and `tools/run_autonomous_pipeline.py` run cleanly | Maintain existing error handling and retry mechanisms in `run_autonomous_pipeline.py`. |
| **R3. Output HTML Verification** | `tests/test_dashboard_report.py` lacks structural validation | Integrate standard library `StrictHTMLValidator` (`html.parser.HTMLParser`) into pytest suite. |
| **R4. Zero API Credit Burn** | `tests/conftest.py` contains `block_network_access` socket guard | Retain monkeypatched socket guard to ensure 100% mocked test execution. |

