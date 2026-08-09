import sys
import os
from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace

# Ensure praecursor modules can be imported
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

class DetailedHTMLStructureValidator(HTMLParser):
    VOID_TAGS = {
        'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
        'link', 'meta', 'param', 'source', 'track', 'wbr', '!doctype'
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.errors = []
        self.element_locations = {}

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        pos = self.getpos()
        attrs_dict = dict(attrs)
        
        element_id = attrs_dict.get('id')
        if element_id:
            self.element_locations[element_id] = {
                'tag': t,
                'start_pos': pos,
                'ancestors': [x[0] for x in self.stack],
                'ancestor_ids': [x[1].get('id') for x in self.stack if x[1].get('id')]
            }
        elif t in ('html', 'head', 'body', 'main'):
            self.element_locations[t] = {
                'tag': t,
                'start_pos': pos,
                'ancestors': [x[0] for x in self.stack]
            }

        if t not in self.VOID_TAGS:
            self.stack.append((t, attrs_dict, pos))

    def handle_endtag(self, tag):
        t = tag.lower()
        pos = self.getpos()
        if t in self.VOID_TAGS:
            return

        if not self.stack:
            self.errors.append(f"Line {pos[0]}:{pos[1]} - Unexpected closing tag </{t}> when stack is empty")
            return

        if self.stack[-1][0] == t:
            popped = self.stack.pop()
            popped_id = popped[1].get('id')
            if popped_id in self.element_locations:
                self.element_locations[popped_id]['end_pos'] = pos
            elif t in self.element_locations:
                self.element_locations[t]['end_pos'] = pos
        else:
            open_tags = [x[0] for x in self.stack]
            if t in open_tags:
                while self.stack and self.stack[-1][0] != t:
                    popped, attrs, start_pos = self.stack.pop()
                    self.errors.append(f"Unclosed tag <{popped}> opened at line {start_pos[0]}:{start_pos[1]} (encountered </{t}> at line {pos[0]}:{pos[1]})")
                self.stack.pop()
            else:
                self.errors.append(f"Line {pos[0]}:{pos[1]} - Unexpected closing tag </{t}> (current top tag: <{self.stack[-1][0]}> opened at line {self.stack[-1][2][0]}:{self.stack[-1][2][1]})")

    def validate(self, html_content: str):
        self.errors = []
        self.stack = []
        self.element_locations = {}
        
        lines = html_content.splitlines(True)
        for line in lines:
            self.feed(line)
        self.close()

        if self.stack:
            for tag, attrs, start_pos in self.stack:
                self.errors.append(f"Unclosed tag <{tag}> opened at line {start_pos[0]}:{start_pos[1]}")

        nesting_errors = []
        for required_elem in ['html', 'head', 'body', 'main', 'live-pulse', 'history-view']:
            if required_elem not in self.element_locations:
                nesting_errors.append(f"Missing required element or ID: '{required_elem}'")
        
        if not nesting_errors:
            head_anc = self.element_locations['head']['ancestors']
            if 'html' not in head_anc:
                nesting_errors.append(f"<head> is not nested inside <html> (ancestors: {head_anc})")
                
            body_anc = self.element_locations['body']['ancestors']
            if 'html' not in body_anc:
                nesting_errors.append(f"<body> is not nested inside <html> (ancestors: {body_anc})")

            main_anc = self.element_locations['main']['ancestors']
            if 'body' not in main_anc or 'html' not in main_anc:
                nesting_errors.append(f"<main> is not nested inside <html> -> <body> (ancestors: {main_anc})")

            live_pulse_anc = self.element_locations['live-pulse']['ancestors']
            if 'main' not in live_pulse_anc:
                nesting_errors.append(f"<div id='live-pulse'> is not nested inside <main> (ancestors: {live_pulse_anc})")

            hist_view_anc = self.element_locations['history-view']['ancestors']
            if 'main' not in hist_view_anc:
                nesting_errors.append(f"<div id='history-view'> is not nested inside <main> (ancestors: {hist_view_anc})")

            lp_end = self.element_locations['live-pulse'].get('end_pos')
            hv_start = self.element_locations['history-view']['start_pos']
            if lp_end and hv_start:
                if lp_end[0] > hv_start[0]:
                    nesting_errors.append(f"<div id='live-pulse'> ends at line {lp_end[0]}, after <div id='history-view'> starts at line {hv_start[0]}")

        is_valid = len(self.errors) == 0 and len(nesting_errors) == 0
        return is_valid, self.errors, nesting_errors, self.element_locations

def run_tests():
    print("=== TEST 1: Validating reports/dashboard.html ===")
    report_path = Path(__file__).resolve().parents[2] / "reports" / "dashboard.html"
    if not report_path.exists():
        print(f"ERROR: {report_path} does not exist!")
        return False
    
    content = report_path.read_text(encoding="utf-8")
    validator = DetailedHTMLStructureValidator()
    is_valid, errors, nesting_errors, locs = validator.validate(content)
    
    print(f"Total lines parsed: {len(content.splitlines())}")
    print(f"Elements detected: {list(locs.keys())}")
    for elem, data in locs.items():
        print(f"  - <{data['tag']}" + (f" id='{elem}'" if elem != data['tag'] else "") + f">: lines {data['start_pos'][0]} -> {data.get('end_pos', (0,0))[0]}")
    
    if is_valid:
        print("PASS: reports/dashboard.html is perfectly well-formed with zero tag errors and correct nesting.")
    else:
        print(f"FAIL: Syntax errors ({len(errors)}): {errors}")
        print(f"FAIL: Nesting errors ({len(nesting_errors)}): {nesting_errors}")
    
    print("\n=== TEST 2: Edge-Case Data Inputs & Synthetic Stress Tests ===")
    from praecursor.reporting.dashboard import ScannerDashboardWriter
    writer = ScannerDashboardWriter()

    # Edge Case 1: Empty stats & empty symbol results
    print("Subtest 2.1: Empty stats, empty symbol_results, database_path=None")
    mock_result_empty = SimpleNamespace(
        database_path=Path("non_existent.db"),
        generated_at=datetime.now(timezone.utc),
        symbol_results=[],
        next_day_results=[],
        source_name="mock_source"
    )
    html_empty = writer._html(mock_result_empty)
    v1 = DetailedHTMLStructureValidator()
    valid1, errs1, n_errs1, _ = v1.validate(html_empty)
    print(f"  Result: valid={valid1}, tag_errors={len(errs1)}, nesting_errors={len(n_errs1)}")
    if not valid1:
        print(f"  Errors: {errs1 + n_errs1}")

    # Edge Case 2: Special Characters in symbols, company names, reasons, components
    print("Subtest 2.2: Special characters (<script>, HTML tags, quotes, ampersands, unicode) in symbols, company, reasons")
    mock_component = SimpleNamespace(
        name="<Tag>&'\"Test",
        score=8.5,
        max_score=10.0,
        reason="Score reason with <alert> alert('xss') </alert> & symbols"
    )
    mock_opp_score = SimpleNamespace(
        company="Company & Co <script>alert(1)</script>",
        score_percent=88.5,
        components=[mock_component]
    )
    mock_prediction = SimpleNamespace(
        latest_close=100.5,
        target_price=110.0,
        stop_loss_price=95.0
    )
    mock_item = SimpleNamespace(
        symbol="SYM<BAD>&'\"",
        next_day_score=75.0,
        next_day_label="Explosion <Candidate>",
        next_day_reasons_text="Rebound <confirmed>, high volume & breakout 'quote' \"double\"",
        next_day_prediction=mock_prediction,
        opportunity_score=mock_opp_score,
        data_quality_score=95.0,
        consensus_result=SimpleNamespace(agreeing_source_count=2, source_count=2, accepted=True),
        final_predictor_score=80.0
    )
    mock_result_special = SimpleNamespace(
        database_path=Path("non_existent.db"),
        generated_at=datetime.now(timezone.utc),
        symbol_results=[mock_item],
        next_day_results=[mock_item],
        source_name="source&<special>"
    )
    html_special = writer._html(mock_result_special)
    v2 = DetailedHTMLStructureValidator()
    valid2, errs2, n_errs2, _ = v2.validate(html_special)
    print(f"  Result: valid={valid2}, tag_errors={len(errs2)}, nesting_errors={len(n_errs2)}")
    if not valid2:
        print(f"  Errors: {errs2 + n_errs2}")

    # Edge Case 3: None values / 0 prices / missing stats dict keys
    print("Subtest 2.3: Zero prices, None reasons, None hit value in history")
    mock_prediction_zero = SimpleNamespace(
        latest_close=0.0,
        target_price=0.0,
        stop_loss_price=0.0
    )
    mock_item_zero = SimpleNamespace(
        symbol="ZERO",
        next_day_score=0.0,
        next_day_label="Neutral",
        next_day_reasons_text=None,
        next_day_prediction=mock_prediction_zero,
        opportunity_score=SimpleNamespace(company="Zero Inc", score_percent=0.0, components=[]),
        data_quality_score=0.0,
        consensus_result=None,
        final_predictor_score=0.0
    )
    mock_result_zero = SimpleNamespace(
        database_path=Path("non_existent.db"),
        generated_at=datetime.now(timezone.utc),
        symbol_results=[mock_item_zero],
        next_day_results=[mock_item_zero],
        source_name="zero_source"
    )
    html_zero = writer._html(mock_result_zero)
    v3 = DetailedHTMLStructureValidator()
    valid3, errs3, n_errs3, _ = v3.validate(html_zero)
    print(f"  Result: valid={valid3}, tag_errors={len(errs3)}, nesting_errors={len(n_errs3)}")
    if not valid3:
        print(f"  Errors: {errs3 + n_errs3}")

    all_passed = is_valid and valid1 and valid2 and valid3
    print(f"\nOVERALL RESULT: {'ALL PASSED' if all_passed else 'SOME TESTS FAILED'}")
    return all_passed

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
