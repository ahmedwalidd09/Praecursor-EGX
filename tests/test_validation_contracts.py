"""Regression checks for the evidence used to publish scanner predictions."""
from datetime import datetime, timedelta
import hashlib
import json
import sqlite3
import numpy as np
import pandas as pd
import pytest

from praecursor.ml.features import FEATURES, FEATURE_VERSION
from praecursor.analysis.outcomes import LABEL_VERSION
from praecursor.ml.validation import chronological_blocks, metrics, train_validate


def samples():
    dates = pd.date_range("2025-01-01", periods=101)
    return pd.DataFrame([
        dict(session=d.date().isoformat(), symbol=str(i), next_day_target_hit=i % 2,
             next_day_resolved_session=(d + timedelta(days=2)).date().isoformat(),
             next_day_net_return_pct=1 if i % 2 else -1, opportunity_score=i)
        for d in dates for i in range(20)
    ])


def test_date_groups_and_outcome_maturity_are_isolated():
    frame = samples()
    blocks = chronological_blocks(pd.concat([frame, frame.iloc[:50]]), "next_day")
    for first, second in zip(blocks, blocks[1:]):
        assert first.next_day_resolved_session.max() < second.session.min()
        assert not set(first.session) & set(second.session)
    assert all(not b.duplicated(["session", "symbol"]).any() for b in blocks)
    assert blocks[-1].session.max() < frame.session.max()


def test_unknown_outcome_does_not_remove_candidate_from_top_five():
    frame = samples().iloc[:6].copy()
    frame.loc[frame.index[0], ["next_day_target_hit", "next_day_net_return_pct"]] = np.nan
    result = metrics(frame, [.9, .8, .7, .6, .5, .4], "next_day")
    assert result["selected"] == 5
    assert result["resolved_selected"] == 4
    assert result["unresolved_selected"] == 1
    assert result["execution_coverage"] == .8
    assert result["precision_at_5"] == .5


def test_existing_model_version_is_never_overwritten(tmp_path, monkeypatch):
    import praecursor.ml.validation as validation
    monkeypatch.setattr(validation, "ROOT", tmp_path)
    frame = samples()
    fingerprint = hashlib.sha256(pd.util.hash_pandas_object(frame, index=False).values.tobytes()).hexdigest()[:12]
    version = f"next_day-{FEATURE_VERSION}-labels{LABEL_VERSION}-protocol4-{fingerprint}"
    directory = tmp_path / "models" / "validated" / version
    directory.mkdir(parents=True)
    original = '{"promoted": false, "reason": "Already evaluated"}'
    (directory / "manifest.json").write_text(original)
    monkeypatch.setattr(validation.xgb.XGBClassifier, "fit", lambda *a, **k: pytest.fail("Repeated fitting"))
    assert train_validate(frame, "next_day", tmp_path / "models")["reason"] == "Already evaluated"
    assert (directory / "manifest.json").read_text() == original


@pytest.mark.parametrize("changes,session", [
    ({}, "2026-09-01"),
    ({"label_version": "old"}, "2026-09-02"),
    ({"feature_version": "old"}, "2026-09-02"),
    ({"promoted": False}, "2026-09-02"),
])
def test_live_prediction_rejects_future_or_incompatible_model(tmp_path, monkeypatch, changes, session):
    import praecursor.ml.prediction as prediction
    monkeypatch.setattr(prediction, "ROOT", tmp_path)
    (tmp_path / "models").mkdir()
    (tmp_path / "models/active_next_day.json").write_text("{}")
    manifest = dict(promoted=True, feature_version=FEATURE_VERSION, label_version=LABEL_VERSION,
                    features=FEATURES, data_cutoff="2026-09-01")
    manifest.update(changes)
    monkeypatch.setattr(prediction, "_models", lambda *a: (manifest, {}))
    probability, reason = prediction.predict_validated({}, 80, "next_day", session)
    assert probability is None and reason["reason"]


def test_verified_outcomes_are_asof_bounded_and_idempotent(tmp_path):
    from praecursor.analysis.accuracy_tracker import AccuracyTracker
    from praecursor.storage.signal_history import SignalHistoryStore
    from praecursor.storage.price_cache import PriceCache
    path = tmp_path / "test.db"
    SignalHistoryStore(path)
    PriceCache(path)
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO scanner_runs VALUES (1,'2026-09-13T17:00:00','test','[]',1,0,NULL,NULL,NULL,NULL)")
        conn.execute("""INSERT INTO scanner_signals
            (run_id,generated_at,rank,symbol,company,opportunity_score,final_predictor_score,
             predictor_label,latest_close,consensus_confidence,data_quality_score,feature_session,
             next_day_target,next_day_stop_loss)
            VALUES (1,'2026-09-13T17:00:00',1,'TEST','Test',50,50,'Watch',100,100,100,'2026-09-13',105,0)""")
        conn.execute("""INSERT INTO source_prices
            (ticker,trade_date,source,open,high,low,close,volume,confidence,collected_at)
            VALUES ('TEST','2026-09-14','tradingview',100,106,99,101,1000,1,'2026-09-14T17:00:00')""")
    tracker = AccuracyTracker(path)
    assert tracker.evaluate_outcomes("2026-09-13") == 0
    assert tracker.evaluate_outcomes("2026-09-14") == 1
    assert tracker.evaluate_outcomes("2026-09-14") == 0
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT next_day_hit,next_day_trade_hit,next_day_status FROM verified_outcomes").fetchone() == (1, None, "no_recorded_stop")
        assert conn.execute("SELECT count(*) FROM scanner_signal_outcomes").fetchone()[0] == 0


def test_optimized_indicators_keep_numeric_definition():
    from praecursor.core.stock import Stock
    from praecursor.core.price_bar import PriceBar
    from praecursor.scoring.keltner import KeltnerSqueezeIndicator
    from praecursor.scoring.zscore import RollingZScoreIndicator
    from praecursor.scoring.atr import calculate_true_ranges
    rng = np.random.default_rng(7)
    closes = 100 + np.cumsum(rng.normal(0, .7, 350))
    stock = Stock("TEST", "Test", history=[PriceBar(datetime(2025,1,1)+timedelta(days=i), c, c+1, c-1, c, 1000) for i,c in enumerate(closes)])
    indicator = KeltnerSqueezeIndicator()
    ranges = calculate_true_ranges(stock)
    widths = []
    for i in range(20, len(closes)+1):
        ema = indicator._calculate_ema(list(closes[:i]), 20)
        atr = sum(ranges[:20])/20
        for tr in ranges[20:i]:
            atr = (atr*19+tr)/20
        widths.append(4*atr/ema*100)
    assert indicator.calculate(stock).value == pytest.approx(widths[-1]/np.mean(widths[-50:]))
    series = pd.Series(closes)
    delta = series.diff()
    gain, loss = delta.clip(lower=0).fillna(0), -delta.clip(upper=0).fillna(0)
    ag, al = gain.rolling(14).mean(), loss.rolling(14).mean()
    for i in range(14,len(series)):
        ag.iloc[i]=(ag.iloc[i-1]*13+gain.iloc[i])/14
        al.iloc[i]=(al.iloc[i-1]*13+loss.iloc[i])/14
    rsi=100-100/(1+ag/al)
    momentum=series.diff(20)
    result=RollingZScoreIndicator().calculate(stock).value
    assert result["RSI14_ZScore"] == pytest.approx((rsi.iloc[-1]-rsi.iloc[-250:].mean())/rsi.iloc[-250:].std())
    assert result["Momentum20_ZScore"] == pytest.approx((momentum.iloc[-1]-momentum.iloc[-250:].mean())/momentum.iloc[-250:].std())


def test_dashboard_actions_require_local_header_and_authorization(monkeypatch):
    from fastapi.testclient import TestClient
    from praecursor.cli import dashboard
    client=TestClient(dashboard.app)
    monkeypatch.setattr(dashboard, "is_machine_whitelisted", lambda: True)
    assert client.post("/api/scan").status_code == 403
    monkeypatch.setattr(dashboard, "scan_status", dict(running=False, error=None))
    calls=[]
    monkeypatch.setattr(dashboard, "run_scanner_sync", lambda: calls.append("scan"))
    assert client.post("/api/scan",headers={"X-Praecursor":"local"}).status_code == 200
    assert calls == ["scan"]
    monkeypatch.setattr(dashboard, "is_machine_whitelisted", lambda: False)
    assert client.post("/api/train",headers={"X-Praecursor":"local"}).status_code == 403
    assert client.get("/api/overview").status_code == 403


def test_desktop_reuses_matching_server(monkeypatch):
    from tools import desktop
    opened=[]
    monkeypatch.setattr(desktop, "ready", lambda: True)
    monkeypatch.setattr(desktop.subprocess, "Popen", lambda *a,**k: pytest.fail("Started duplicate server"))
    monkeypatch.setattr(desktop.webbrowser, "open", opened.append)
    assert desktop.main() == 0
    assert opened == [desktop.URL]


@pytest.mark.parametrize("hour,minimum,fetches", [(17, 1, 0), (14, 1, 1), (17, 2, 1)])
def test_cache_requires_finalized_session_and_sufficient_history(tmp_path, monkeypatch, hour, minimum, fetches):
    from datetime import date
    from types import SimpleNamespace
    from praecursor.core.price_bar import PriceBar
    from praecursor.core.sessions import CAIRO
    from praecursor.collectors.collection_result import CollectionResult
    from praecursor.storage.price_cache import PriceCache
    from praecursor.data import data_manager
    day = date(2026, 11, 5)
    collected = datetime(2026, 11, 5, hour, tzinfo=CAIRO)
    bars = [PriceBar(datetime(2026, 11, 5), 100, 102, 99, 101, 1000)]
    cache = PriceCache(tmp_path / "prices.db")
    cache.save(CollectionResult("TEST", "tradingview", bars, collected_at=collected))
    calls = []
    def fetch(*args):
        calls.append(args)
        return CollectionResult("TEST", "tradingview", [PriceBar(datetime(2026, 11, 4), 99, 101, 98, 100, 1000)] + bars)
    source = SimpleNamespace(name="tradingview", fetch_history=fetch)
    monkeypatch.setattr(data_manager, "completed_session", lambda: day)
    result = data_manager.DataManager([source], minimum_bars=minimum, price_cache=cache).fetch_history("TEST", date(2026, 11, 1), date(2026, 11, 7))
    assert len(calls) == fetches
    if not fetches:
        assert result.collected_at == collected


def test_weekly_trend_uses_thursday_week_end(monkeypatch):
    from praecursor.core.stock import Stock
    from praecursor.core.price_bar import PriceBar
    from praecursor.scoring.mtf import MultiTimeframeIndicator
    dates = [d for d in pd.date_range("2024-01-01", periods=510) if d.weekday() not in (4, 5)]
    bars = [PriceBar(d.to_pydatetime(), i+100, i+101, i+99, i+100, 1000) for i,d in enumerate(dates)]
    expected = pd.Series([b.close for b in bars], index=dates).resample("W-THU").last().tolist()
    seen = []
    indicator = MultiTimeframeIndicator()
    monkeypatch.setattr(indicator, "_calculate_ema", lambda values, period: seen.append(values) or 100)
    indicator.calculate(Stock("TEST", "Test", history=bars))
    assert seen == [expected, expected]


def test_saved_dashboard_has_safe_json_and_missing_measurements(tmp_path):
    import re
    from praecursor.reporting.dashboard import ScannerDashboardWriter
    data = {"signals": [{"company": "</script><script>alert(1)</script>", "next_day_probability": float("nan"), "next_day_stop_loss": None}]}
    html = ScannerDashboardWriter().write_snapshot(data, tmp_path / "snapshot.html").read_text(encoding="utf-8")
    payload = re.search(r'<script id="saved-snapshot" type="application/json">(.*?)</script>', html).group(1)
    assert "<" not in payload
    row = json.loads(payload)["signals"][0]
    assert row["company"] == data["signals"][0]["company"]
    assert row["next_day_probability"] is None and row["next_day_stop_loss"] is None


def test_dashboard_rejects_untrusted_host():
    from fastapi.testclient import TestClient
    from praecursor.cli.dashboard import app
    assert TestClient(app).get("/api/health", headers={"Host": "attacker.example"}).status_code == 400


def test_training_rebuilds_after_same_session_vendor_revision():
    from tools.retrain_models import dataset_is_current
    metadata = dict(feature_version=FEATURE_VERSION, label_version=LABEL_VERSION,
                    last_source_session="2026-11-05", price_rows=100, last_collection="2026-11-05T17:00:00")
    assert dataset_is_current(metadata, "2026-11-05", 100, "2026-11-05T17:00:00")
    assert not dataset_is_current(metadata, "2026-11-05", 100, "2026-11-06T17:00:00")
    assert not dataset_is_current(metadata, "2026-11-05", 101, "2026-11-05T17:00:00")
