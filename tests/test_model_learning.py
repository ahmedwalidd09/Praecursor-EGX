import json
import sqlite3
from zipfile import ZipFile
import pandas as pd
import pytest
from praecursor.analysis.outcomes import LABEL_VERSION
from praecursor.ml.features import FEATURES, FEATURE_VERSION, INDICATOR_TO_FEATURE
from praecursor.ml.published import published_samples, feedback_summary
from praecursor.ml.validation import train_validate
from tools.model_state import pack, restore


def test_saved_features_and_outcomes_are_joined_without_rerun_or_future_leakage(tmp_path):
    db = tmp_path / "learning.db"
    values = dict.fromkeys(INDICATOR_TO_FEATURE, 1)
    values.update(AvgTurnover20=1_000_000, RSI14=42)
    with sqlite3.connect(db) as c:
        c.executescript('''CREATE TABLE scanner_signals(run_id, symbol, generated_at, feature_session,
          feature_version, indicator_values_json, opportunity_score, data_quality_score, latest_close, candidate_rank);
          CREATE TABLE verified_outcomes(run_id,symbol,label_version,next_day_hit,next_day_net_return,
          next_day_status,resolved_session,swing_hit,swing_net_return,swing_status,swing_resolved_session);''')
        for run, symbol, stamp, version, hit in [
            (1,"HIT","2026-11-05T18:00:00Z",FEATURE_VERSION,1),
            (2,"HIT","2026-11-07T18:00:00Z",FEATURE_VERSION,0),
            (3,"MISS","2026-11-07T18:00:00Z",FEATURE_VERSION,0),
            (4,"UNKNOWN","2026-11-07T18:00:00Z",FEATURE_VERSION,None),
            (5,"LATE","2026-11-08T18:00:00Z",FEATURE_VERSION,1),
            (6,"LEGACY","2026-11-07T18:00:00Z","old",1),
            (7,"EARLY","2026-11-08T04:00:00Z",FEATURE_VERSION,None),
            (8,"CUTOFF","2026-11-08T07:00:00Z",FEATURE_VERSION,1),
            (9,"NEW","2026-11-08T04:00:00Z",FEATURE_VERSION,None)]:
            c.execute('INSERT INTO scanner_signals VALUES (?,?,?,?,?,?,?,?,?,?)',
                      (run,symbol,stamp,"2026-11-05",version,json.dumps(values),70,100,100,1))
            if symbol == "NEW":
                continue  # Not yet visited by the after-close outcome tracker.
            c.execute('INSERT INTO verified_outcomes VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                      (run,symbol,LABEL_VERSION,hit,2 if hit else None,"target" if hit else "pending",
                       "2026-11-08" if hit is not None else None,None,None,"pending",None))
    frame = published_samples(db).set_index("symbol", drop=False)
    assert set(frame.index) == {"HIT","MISS","UNKNOWN","EARLY","NEW"}
    assert frame.loc["HIT", "next_day_target_hit"] == 1
    assert frame.loc["HIT", "rsi14"] == 42
    assert frame.loc["MISS", "next_day_target_hit"] == 0
    assert pd.isna(frame.loc["UNKNOWN", "next_day_target_hit"])
    assert frame.loc["NEW", "next_day_status"] == "pending"
    assert feedback_summary(frame) == dict(examples=5,sessions=1,candidates=5,hits=1,misses=1,unresolved=3,
        provenance="Original published features; first prediction per symbol/session; incompatible legacy features excluded")


def test_insufficient_feedback_never_replaces_incumbent(tmp_path, monkeypatch):
    from praecursor.ml import validation
    monkeypatch.setattr(validation, "ROOT", tmp_path)
    models = tmp_path / "models"; models.mkdir()
    active = models / "active_next_day.json"; active.write_text('{"model_version":"keep-me"}')
    frame = pd.DataFrame(columns=["session","symbol","next_day_target_hit","next_day_resolved_session"])
    report = train_validate(frame, "next_day", models)
    assert report["status"] == "insufficient_history" and not report["promoted"]
    assert json.loads(active.read_text())["model_version"] == "keep-me"


def test_model_bundle_moves_between_runner_paths_and_keeps_no_failed_challengers(tmp_path):
    source=tmp_path/"source"; target=tmp_path/"runner"
    model=source/"models/validated/good-v1";model.mkdir(parents=True)
    (model/"xgb.json").write_text("weights");(model/"lgb.txt").write_text("weights")
    active=dict(model_version="good-v1",directory=str(model),promoted=True)
    (source/"models/active_next_day.json").write_text(json.dumps(active))
    (source/"reports").mkdir();(source/"reports/next_day_validation.json").write_text('{"promoted":false}')
    archive=pack(source)
    restore(target,archive)
    restored=json.loads((target/"models/active_next_day.json").read_text())
    assert restored["directory"]==str((target/"models/validated/good-v1").resolve())
    assert (target/"models/validated/good-v1/xgb.json").read_text()=="weights"
    assert not (target/"models/active_swing.json").exists()


def test_model_bundle_rejects_path_escape_before_writing(tmp_path):
    archive=tmp_path/"bad.zip"
    with ZipFile(archive,"w") as z:
        z.writestr("next_day/active.json", json.dumps(dict(model_version="../escape",promoted=True)))
    with pytest.raises(ValueError):restore(tmp_path/"runner",archive)
    assert not (tmp_path/"runner").exists()
