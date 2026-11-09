"""Expanding-window replay; candidate selection never reads future outcome values."""
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
import xgboost as xgb
from praecursor.ml.features import FEATURES


def replay(frame, horizon="next_day"):
    frame=frame.sort_values(["session","symbol"]).drop_duplicates(["session","symbol"])
    target=horizon+"_target_hit"; maturity=horizon+"_resolved_session"
    records=[]
    for day in sorted(frame.session.unique()):
        known=frame[(frame.session<day)&(frame[maturity]<day)&frame[target].notna()]
        dates=sorted(known.session.unique())
        if len(dates)<30:
            continue
        calibration=known[known.session.isin(dates[-10:])]
        train=known[(known.session<dates[-10])&(known[maturity]<dates[-10])]
        if train.session.nunique()<15 or min(train[target].nunique(),calibration[target].nunique())<2:
            continue
        model=xgb.XGBClassifier(n_estimators=120,max_depth=3,learning_rate=.04,min_child_weight=15,
                                reg_lambda=5,n_jobs=2,random_state=42,eval_metric="logloss")
        model.fit(train[FEATURES],train[target])
        calibrator=IsotonicRegression(out_of_bounds="clip").fit(model.predict_proba(calibration[FEATURES])[:,1],calibration[target])
        # All eligible feature rows compete, including those whose future outcome is missing.
        today=frame[frame.session==day].copy()
        today["probability"]=calibrator.predict(model.predict_proba(today[FEATURES])[:,1])
        top=today.sort_values(["probability","symbol"],ascending=[False,True]).head(5)
        for _,row in top.iterrows():
            records.append(dict(session=day,symbol=row.symbol,probability=row.probability,
                                target_hit=row[target],net_return_pct=row[horizon+"_net_return_pct"],
                                status=row[horizon+"_status"],training_end=str(train.session.max()),
                                calibration_end=str(calibration.session.max())))
    return pd.DataFrame(records)
