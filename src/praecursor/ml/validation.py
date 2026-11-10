"""Session-grouped, maturity-purged model validation and versioned promotion."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
import xgboost as xgb
import lightgbm as lgb
from praecursor.ml.features import FEATURES, FEATURE_VERSION
from praecursor.analysis.outcomes import LABEL_VERSION

ROOT=Path(__file__).resolve().parents[3]


def chronological_blocks(frame, horizon):
    frame=frame.sort_values(["session","symbol"]).drop_duplicates(["session","symbol"],keep="last")
    target=horizon+"_target_hit"
    resolved=horizon+"_resolved_session"
    days=sorted(frame.session.unique())
    # Mature by elapsed market sessions, never by future return or availability.
    horizon_sessions = 1 if horizon == "next_day" else 20
    if len(days) > horizon_sessions:
        frame=frame[frame.session<=days[-horizon_sessions-1]].copy()
        days=sorted(frame.session.unique())
    if len(days)<40:
        raise ValueError(f"Only {len(days)} labelled sessions; need at least 40 before four-way validation")
    a,b,c=[int(len(days)*x) for x in (.55,.7,.85)]
    blocks=[frame[frame.session.isin(d)] for d in (days[:a],days[a:b],days[b:c],days[c:])]
    for i in range(3):
        # Purge overlapping horizons; only completed outcomes known before next block.
        blocks[i]=blocks[i][blocks[i][target].notna() & (blocks[i][resolved]<blocks[i+1].session.min())]
    for name, block in zip(("train","tune","calibration","test"),blocks):
        if block.session.nunique()<5 or len(block)<100 or block[target].nunique()<2:
            raise ValueError(f"Insufficient {name} block after outcome-maturity purge: {len(block)} rows, {block.session.nunique()} sessions")
    return blocks


def metrics(frame, probabilities, horizon, threshold=0):
    known=frame[horizon+"_target_hit"].notna()
    y=frame.loc[known,horizon+"_target_hit"].to_numpy(dtype=int)
    known_p=np.asarray(probabilities)[known.to_numpy()]
    scored=frame.assign(probability=np.asarray(probabilities))
    selected=scored[scored.probability>=threshold].sort_values(["session","probability","symbol"],ascending=[True,False,True]).groupby("session").head(5)
    daily=selected.groupby("session")[horizon+"_target_hit"].mean().dropna()
    interval=None
    if len(daily)>=5:
        rng=np.random.default_rng(42)
        boot=rng.choice(daily.to_numpy(),(2000,len(daily)),replace=True).mean(axis=1)
        interval=[float(x) for x in np.quantile(boot,[.025,.975])]
    selected_hits=float(selected[horizon+"_target_hit"].sum())
    return dict(samples=len(frame),labelled_samples=int(known.sum()),sessions=int(frame.session.nunique()),base_rate=float(y.mean()),
        average_precision=float(average_precision_score(y,known_p) if len(y) else 0),
        brier=float(brier_score_loss(y,known_p) if len(y) else 1),
        roc_auc=float(roc_auc_score(y,known_p)) if len(set(y))>1 else None,
        selected=len(selected),resolved_selected=int(selected[horizon+"_target_hit"].notna().sum()),
        unresolved_selected=int(selected[horizon+"_target_hit"].isna().sum()),
        execution_coverage=float(selected[horizon+"_net_return_pct"].notna().mean()) if len(selected) else 0,
        precision_at_5=float(selected[horizon+"_target_hit"].mean()) if len(selected) else None,
        recall_at_5=selected_hits/float(y.sum()) if y.sum() else 0,
        session_coverage=float(selected.session.nunique()/frame.session.nunique()),
        net_expectancy_pct=float(selected[horizon+"_net_return_pct"].mean()) if len(selected) else None,
        daily_precision_95pct_interval=interval)


def predict_bundle(bundle, frame):
    probabilities=[]
    for kind, weight in bundle["weights"].items():
        if not weight:
            continue
        if kind=="xgb":
            model=xgb.XGBClassifier(); model.load_model(str(Path(bundle["directory"])/"xgb.json"))
            p=model.predict_proba(frame[FEATURES])[:,1]
        else:
            model=lgb.Booster(model_file=str(Path(bundle["directory"])/"lgb.txt"))
            p=model.predict(frame[FEATURES])
        probabilities.append(weight*p)
    raw=sum(probabilities)
    cal=bundle["calibration"]
    return np.interp(raw,cal["x"],cal["y"])


def fit_challenger(train, tune, horizon):
    target=horizon+"_target_hit"
    xgb_model=xgb.XGBClassifier(n_estimators=300,max_depth=3,learning_rate=.04,min_child_weight=15,
        subsample=.8,colsample_bytree=.8,reg_lambda=5,eval_metric="logloss",early_stopping_rounds=25,
        random_state=42,n_jobs=2)
    xgb_model.fit(train[FEATURES],train[target],eval_set=[(tune[FEATURES],tune[target])],verbose=False)
    lgb_model=lgb.LGBMClassifier(n_estimators=150,max_depth=3,num_leaves=7,learning_rate=.04,
        min_child_samples=30,reg_lambda=5,random_state=42,n_jobs=2,verbosity=-1)
    lgb_model.fit(train[FEATURES],train[target])
    xp=xgb_model.predict_proba(tune[FEATURES])[:,1]; lp=lgb_model.predict_proba(tune[FEATURES])[:,1]
    candidates={"xgb":(xp,{"xgb":1.,"lgb":0.}),"lgb":(lp,{"xgb":0.,"lgb":1.}),
                "ensemble":((xp+lp)/2,{"xgb":.5,"lgb":.5})}
    name,(p,weights)=max(candidates.items(),key=lambda item:average_precision_score(tune[target],item[1][0]))
    return xgb_model, lgb_model, weights, name


def train_validate(frame, horizon, models_root=None, input_fingerprint=None):
    models_root=Path(models_root or ROOT/"models")
    report_path=ROOT/"reports"/(horizon+"_validation.json")
    report_path.parent.mkdir(parents=True,exist_ok=True)
    try:
        train,tune,cal,test=chronological_blocks(frame,horizon)
    except ValueError as exc:
        report=dict(status="insufficient_history",reason=str(exc),horizon=horizon,promoted=False)
        report_path.write_text(json.dumps(report,indent=2),encoding="utf-8")
        return report
    fingerprint=(input_fingerprint or hashlib.sha256(pd.util.hash_pandas_object(frame,index=False).values.tobytes()).hexdigest())[:12]
    version=f"{horizon}-{FEATURE_VERSION}-labels{LABEL_VERSION}-protocol4-{fingerprint}"
    directory=models_root/"validated"/version
    manifest=directory/"manifest.json"
    if manifest.exists():
        report=json.loads(manifest.read_text(encoding="utf-8"))
        report_path.write_text(json.dumps(report,indent=2),encoding="utf-8")
        return report
    xgb_model, lgb_model, weights, name = fit_challenger(train, tune, horizon)
    def raw(df):
        return weights["xgb"]*xgb_model.predict_proba(df[FEATURES])[:,1]+weights["lgb"]*lgb_model.predict_proba(df[FEATURES])[:,1]
    calibrator=IsotonicRegression(out_of_bounds="clip").fit(raw(cal),cal[target])
    cal_p=calibrator.predict(raw(cal))
    # Select a recommendation threshold using calibration data, never test outcomes.
    options=[]
    for threshold in (0,.4,.5,.6,.7):
        m=metrics(cal,cal_p,horizon,threshold)
        if m["selected"]>=20 and m["session_coverage"]>=.5 and m["execution_coverage"]==1:
            options.append((m["net_expectancy_pct"],threshold))
    threshold=max(options)[1] if options else 1.01
    test_p=calibrator.predict(raw(test))
    result=metrics(test,test_p,horizon,threshold)
    base=metrics(test,np.full(len(test),float(train[target].mean())),horizon)
    technical=metrics(test,test.opportunity_score.to_numpy()/100,horizon)
    directory.mkdir(parents=True,exist_ok=True)
    xgb_model.save_model(str(directory/"xgb.json")); lgb_model.booster_.save_model(str(directory/"lgb.txt"))
    report=dict(status="evaluated",horizon=horizon,model_version=version,directory=str(directory.resolve()),
        feature_version=FEATURE_VERSION,label_version=LABEL_VERSION,features=FEATURES,validation_protocol=4,
        training_date=datetime.now(timezone.utc).isoformat(),data_cutoff=str(max(frame.session.max(),frame[horizon+"_resolved_session"].dropna().max())),
        training_end=str(train.session.max()),test_start=str(test.session.min()),test_end=str(test.session.max()),
        blocks={name:{"rows":len(b),"sessions":int(b.session.nunique()),"first":str(b.session.min()),"last":str(b.session.max())}
                for name,b in zip(("train","tune","calibration","test"),(train,tune,cal,test))},
        weights=weights,chosen_on_tuning=name,threshold=threshold,
        calibration={"x":calibrator.X_thresholds_.tolist(),"y":calibrator.y_thresholds_.tolist()},
        metrics=result,constant_baseline=base,technical_baseline=technical,
        probability_definition="Published target touched within horizon; not trade win probability",
        expectancy_definition="Next-open execution, 25 bps round-trip, stop-first bound on ambiguous bars, zero for unfilled",
        provenance=", ".join(sorted(frame.provenance.dropna().unique())) if "provenance" in frame else "Retrospective reconstruction",
        promoted=False)
    reasons=[]
    if "provenance" not in frame or not frame.provenance.eq("published_prediction").all():
        reasons.append("Retrospective or mixed-provenance research cannot promote a live model")
    if result["unresolved_selected"] or result["execution_coverage"] < 1:
        reasons.append("Selected outcomes are incomplete; wait for resolved execution evidence")
    if result["sessions"]<10 or result["selected"]<40:
        reasons.append("Fewer than 10 test sessions or 40 selected trades")
    if result["average_precision"]<=result["base_rate"] or result["brier"]>base["brier"]:
        reasons.append("No discrimination/calibration improvement over constant baseline")
    if (result["precision_at_5"] or 0)<(technical["precision_at_5"] or 0) or (result["net_expectancy_pct"] or 0)<=0:
        reasons.append("No profitable improvement over technical ranking")
    active=models_root/f"active_{horizon}.json"
    if active.exists():
        old=json.loads(active.read_text())
        if old.get("model_version")==version:
            reasons.append("This dataset version was already evaluated; no repeated promotion")
        elif old.get("data_cutoff","")>=str(test.session.min()):
            reasons.append("Incumbent has seen this test period; wait for new unseen sessions")
        else:
            old_metrics=metrics(test,predict_bundle(old,test),horizon,old["threshold"])
            report["incumbent_metrics"]=old_metrics
            if (result["precision_at_5"] or 0)<(old_metrics["precision_at_5"] or 0) or (result["net_expectancy_pct"] or 0)<(old_metrics["net_expectancy_pct"] or 0):
                reasons.append("Challenger does not improve incumbent on identical unseen sessions")
    report["promotion_reasons"]=reasons
    from praecursor.ml.rolling import rolling_validation
    # Avoid extra fitting when the main holdout already rejects the challenger.
    report["rolling_validation"] = (rolling_validation(frame, horizon) if not reasons else
        dict(status="not_run", passed=False, reason="Main holdout failed; expensive rolling fits skipped"))
    if not report["rolling_validation"]["passed"]:
        reasons.append(report["rolling_validation"]["reason"])
    report["promoted"]=not reasons
    (directory/"manifest.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    report_path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    if report["promoted"]:
        temp=active.with_suffix(".tmp"); temp.write_text(json.dumps(report,indent=2),encoding="utf-8"); temp.replace(active)
    return report
