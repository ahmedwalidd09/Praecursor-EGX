# Handoff Report: HTML Generation Audit & Remediation Strategy

## 1. Observation
- **Inspected Files**:
  - `src/praecursor/reporting/dashboard.py` (Lines 1–668)
  - `src/praecursor/cli/dashboard.py` (Lines 1–256)
  - `tools/regenerate_dashboard.py` (Lines 1–154)
  - `reports/dashboard.html` (Generated dashboard output)
- **Verbatim Code & Flaws Discovered**:
  1. `src/praecursor/reporting/dashboard.py` lines 77–80:
     ```python
     77:      </div>
     78:      </div>
     79:    </div>
     80:    </div> <!-- end live-pulse tab -->
     ```
     An extra `</div>` on line 79 causes line 80 to close `<main>` prematurely.
  2. `src/praecursor/reporting/dashboard.py` lines 121–127:
     ```python
     121:              {''.join(
     122:                f"<tr><td>{r['signal_date'][:10]}</td><td><strong>{r['symbol']}</strong></td>"
     123:                f"<td>{r['next_day_label']}</td>"
     124:                f"<td style='color: {'#22c55e' if (r.get('next_day_return') or 0) >= 0 else '#ef4444'}'>{(r.get('next_day_return') or 0):+.1f}%</td>"
     125:                f"<td>{self._hit_badge(r['next_day_hit'])}</td></tr>"
     126:                for r in stats['history']
     127:              )}
     ```
     Direct indexing on `stats['history']`, `r['symbol']`, `r['next_day_label']`, `r['signal_date']`, and `r['next_day_hit']` without `.get()` defaults and without `html.escape()`.
  3. `src/praecursor/reporting/dashboard.py` line 195: `reasons = item.next_day_reasons_text` evaluated with `"no strong" not in reasons.lower()` on line 243. Will raise `AttributeError` if `reasons` is `None`.
  4. `src/praecursor/cli/dashboard.py` line 78: `"<html><head>"` missing `<!doctype html>` declaration and meta tags.

## 2. Logic Chain
1. **Observation 1** shows 4 closing `</div>` tags for 3 opening `<div>` tags within the `live-pulse` tab content block (`live-pulse`, `grid layout`, `main-content`).
   - Line 77 closes `main-content`.
   - Line 78 closes `grid layout`.
   - Line 79 has no corresponding opening `<div>` tag inside `live-pulse`.
   - Therefore, line 79 closes `<div id="live-pulse">`.
   - Line 80 then closes `<main>`.
   - This cascades into placing `history-view` tab outside `<main>`, creating unclosed/mismatched tags through the rest of the HTML document.
2. **Observation 2** demonstrates unsafe direct key access and string interpolation without HTML escaping.
   - Injecting raw strings like `r['symbol']` or `r['next_day_label']` risks malformed HTML if special characters exist.
   - Missing key fallbacks risk `KeyError` or `TypeError` crashes during dashboard rendering.
3. **Observation 3** shows `reasons.lower()` executed without a null check on `item.next_day_reasons_text`.
   - Replacing `reasons` with `reasons = item.next_day_reasons_text or ""` guarantees string type and prevents runtime exception.
4. **Observation 4** shows incomplete boilerplate in fallback `HTMLResponse`.
   - Adding `<!doctype html>` and responsive meta tags standardizes rendering across browsers.

## 3. Caveats
- Read-only investigation: No Python source files were directly modified during this step.
- Database scan outcome data availability was tested via existing `reports/dashboard.html` and `tools/regenerate_dashboard.py` logic.

## 4. Conclusion
The HTML generation logic in `src/praecursor/reporting/dashboard.py` contains a critical tag duplication bug on line 79 and secondary string escaping/null safety vulnerabilities. Removing line 79, adding HTML escaping in historical signal rendering, safeguarding reasons string handling, and updating CLI fallback HTML will fully resolve HTML structural flaws while preserving the institutional dark (black, blue, red) visual style.

## 5. Verification Method
1. **Source Code Inspection**:
   Verify line 79 of `src/praecursor/reporting/dashboard.py` has been removed.
2. **Dashboard Regeneration**:
   Run `python tools/regenerate_dashboard.py`. Output `reports/dashboard.html` must exit cleanly (exit code 0).
3. **HTML Tree Validation Script**:
   Run a Python HTML parser test:
   ```python
   from html.parser import HTMLParser
   class TagChecker(HTMLParser):
       def __init__(self):
           super().__init__()
           self.stack = []
           self.errors = []
       def handle_starttag(self, tag, attrs):
           if tag not in ["meta", "br", "hr", "img", "input", "link"]:
               self.stack.append(tag)
       def handle_endtag(self, tag):
           if tag in ["meta", "br", "hr", "img", "input", "link"]: return
           if self.stack and self.stack[-1] == tag:
               self.stack.pop()
           else:
               self.errors.append(f"Mismatched closing tag </{tag}>, current open: {self.stack[-1] if self.stack else 'NONE'}")
   
   checker = TagChecker()
   checker.feed(open("reports/dashboard.html", "r", encoding="utf-8").read())
   assert len(checker.stack) == 0, f"Unclosed tags: {checker.stack}"
   assert len(checker.errors) == 0, f"Tag errors: {checker.errors}"
   ```
   Must pass with 0 unclosed tags and 0 errors.

## 6. Remaining Work (Soft Handoff to Worker)
1. Apply line-by-line fixes specified in `C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\.agents\explorer_html_1\analysis.md` to `src/praecursor/reporting/dashboard.py` and `src/praecursor/cli/dashboard.py`.
2. Run `python tools/regenerate_dashboard.py` to regenerate `reports/dashboard.html`.
3. Validate HTML structure using the verification parser script.
