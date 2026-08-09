# HTML Generation Audit & Analysis Report

## Summary of Scope & Objective
Audit `src/praecursor/reporting/dashboard.py` and `src/praecursor/cli/dashboard.py` in `Praecursor-EGX` to detect broken HTML tags, unclosed elements, malformed string injections, missing boilerplate HTML, and invalid styling attributes while ensuring that the institutional dark aesthetic (black background, neon blue accents, red/green badges) is preserved.

---

## Detailed Findings & Flaw Inventory

### 1. Structural HTML Tag Imbalance (CRITICAL)
- **File**: `src/praecursor/reporting/dashboard.py`
- **Lines**: 77–80
- **Code Snippet**:
  ```python
  77:      </div>
  78:      </div>
  79:    </div>
  80:    </div> <!-- end live-pulse tab -->
  ```
- **Observation**:
  Tracing the open div elements within `<div id="live-pulse" class="tab-content">` (line 54):
  1. Line 54: `<div id="live-pulse" class="tab-content">` (Tab container)
  2. Line 58: `<div class="grid layout">` (Grid container)
  3. Line 59: `<div class="main-content">` (Main content container)
  
  Closing tags:
  - Line 77: `</div>` (closes `main-content` from line 59)
  - Line 78: `</div>` (closes `grid layout` from line 58)
  - Line 79: `</div>` (**EXTRANEOUS / UNMATCHED DIV TAG**)
  - Line 80: `</div>` (intended to close `live-pulse`)

- **Impact**:
  Because of line 79, line 80 prematurely closes `<main>` (line 53). As a result:
  - `<div id="history-view"...>` (line 82) is placed OUTSIDE `<main>`.
  - Line 133 `</main>` becomes an orphan closing tag after `<main>` was already closed.
  - Line 143 `</div>` (end of modal) closes non-existent elements or `<body>`.
  - Line 162 `</body>` becomes a duplicate closing tag.
  The generated DOM tree in `reports/dashboard.html` is severely malformed.

- **Remediation**:
  Delete line 79 (`    </div>`) in `src/praecursor/reporting/dashboard.py`.

---

### 2. Missing HTML Boilerplate in CLI Fallback Response (MEDIUM)
- **File**: `src/praecursor/cli/dashboard.py`
- **Lines**: 77–85
- **Code Snippet**:
  ```python
  77:        return HTMLResponse(
  78:            "<html><head>"
  79:            "<style>"
  ```
- **Observation**:
  When `reports/dashboard.html` does not yet exist, `get_dashboard()` returns a bare fallback HTML string that starts with `"<html><head>"`.
- **Impact**:
  Missing `<!doctype html>` declaration, `<meta charset="utf-8" />`, and `<meta name="viewport" content="width=device-width, initial-scale=1" />`. This can cause legacy quirks-mode rendering in browsers.
- **Remediation**:
  Update line 78 in `src/praecursor/cli/dashboard.py` to:
  `"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\" /><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />"`

---

### 3. Unescaped Values & Unsafe Dict Access in Historical Table Generation (MEDIUM)
- **File**: `src/praecursor/reporting/dashboard.py`
- **Lines**: 121–127
- **Code Snippet**:
  ```python
  121:              {''.join(
  122:                f"<tr><td>{r['signal_date'][:10]}</td><td><strong>{r['symbol']}</strong></td>"
  123:                f"<td>{r['next_day_label']}</td>"
  124:                f"<td style='color: {'#22c55e' if (r.get('next_day_return') or 0) >= 0 else '#ef4444'}'>{(r.get('next_day_return') or 0):+.1f}%</td>"
  125:                f"<td>{self._hit_badge(r['next_day_hit'])}</td></tr>"
  126:                for r in stats['history']
  127:              )}
  ```
- **Observation**:
  - Direct key access `r['signal_date']`, `r['symbol']`, `r['next_day_label']`, `r['next_day_hit']`, `stats['history']` will raise `KeyError` or `TypeError` if keys are missing or values are `None`.
  - `r['symbol']` and `r['next_day_label']` are injected without `escape()`, allowing raw unescaped characters in table cells.
- **Impact**:
  Potential runtime crash on missing historical attributes or XSS/HTML injection if symbol/label strings contain special characters.
- **Remediation**:
  Use `stats.get('history', [])` and safe `.get()` methods with `escape()`.
  Replace lines 121–127 with:
  ```python
  {''.join(
    f"<tr><td>{(r.get('signal_date') or '')[:10]}</td>"
    f"<td><strong>{escape(str(r.get('symbol', '')))}</strong></td>"
    f"<td>{escape(str(r.get('next_day_label', '')))}</td>"
    f"<td style='color: {'#22c55e' if (r.get('next_day_return') or 0) >= 0 else '#ef4444'}'>{(r.get('next_day_return') or 0):+.1f}%</td>"
    f"<td>{self._hit_badge(r.get('next_day_hit'))}</td></tr>"
    for r in stats.get('history', [])
  )}
  ```

---

### 4. Risk of AttributeError on Candidate AI Reasons Evaluation (LOW/MEDIUM)
- **File**: `src/praecursor/reporting/dashboard.py`
- **Lines**: 195, 243
- **Code Snippet**:
  ```python
  195:            reasons = item.next_day_reasons_text
  ...
  243:            {f"The AI model identified this as a candidate because {escape(reasons).replace(', ', ', and ')}." if reasons and "no strong" not in reasons.lower() else "The AI model did not identify strong positive technical catalysts for this symbol today."}
  ```
- **Observation**:
  If `item.next_day_reasons_text` returns `None` instead of a string, calling `reasons.lower()` will raise `AttributeError: 'NoneType' object has no attribute 'lower'`.
- **Impact**:
  Rendering `_candidate_panel` could crash when candidate predictions have no text reasons.
- **Remediation**:
  Ensure `reasons` is safely initialized to string:
  Line 195: `reasons = item.next_day_reasons_text or ""`

---

### 5. Aesthetics & Theme Verification (PASS)
- **File**: `src/praecursor/reporting/dashboard.py` (`_css()`)
- **Observation**:
  - Background palette: `#000000` (pure dark background), `#080c14` (dark panels), `#0c1220` (card highlights).
  - Accent colors: `#1e88e5` (deep blue accent), `#42a5f5` (neon blue highlights).
  - Verdict colors: `#22c55e` (neon green), `#ef4444` (neon red).
  - Typography & layout: Modern flex and grid layouts, inter font face, custom dark scrollbar, responsive card layout.
- **Verdict**: Theme and aesthetic integrity are preserved 100%. All changes are strictly structural HTML and robustness fixes.

---

## Line-by-Line Remediation Summary for Implementation Worker

| Target File | Line(s) | Original Code / Behavior | Required Remediation | Rationale |
|-------------|---------|--------------------------|----------------------|-----------|
| `src/praecursor/reporting/dashboard.py` | 79 | `    </div>` | **REMOVE LINE 79** | Eliminates extra `</div>` tag that prematurely closes `<main>` and causes domino tag misalignments across the whole document. |
| `src/praecursor/reporting/dashboard.py` | 121-127 | Direct `stats['history']` & unescaped `r['symbol']`, `r['next_day_label']` | Use `stats.get('history', [])`, `.get()` for keys, and `escape(...)` | Prevents `KeyError`/`TypeError` on missing fields and ensures proper HTML escaping. |
| `src/praecursor/reporting/dashboard.py` | 195 | `reasons = item.next_day_reasons_text` | Change to `reasons = item.next_day_reasons_text or ""` | Prevents `AttributeError` on `.lower()` if reasons text is `None`. |
| `src/praecursor/cli/dashboard.py` | 78 | `"<html><head>"` | Change to `"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\" /><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />"` | Standards compliance for fallback dashboard response. |

---

## Verification & Validation Plan
1. **Programmatic Tag Validation**:
   Parse generated `reports/dashboard.html` with Python's `html.parser.HTMLParser` or `xml.etree.ElementTree` (via `html5lib` / `BeautifulSoup`) to confirm 0 unclosed or mismatched tags.
2. **Dashboard Regeneration Test**:
   Execute `python tools/regenerate_dashboard.py` and verify exit code is 0 without warnings/stack traces.
3. **Visual Inspection**:
   Confirm tabs ("Live Pulse" and "Accuracy Tracker"), tables, modal dialog, and floating scan button operate seamlessly.
