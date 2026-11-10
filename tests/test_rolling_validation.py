import pandas as pd
import pytest
from praecursor.ml.rolling import rolling_blocks, rolling_validation, block_mean_interval


def test_rolling_folds_have_disjoint_tests_and_no_future_labels():
    days = pd.date_range("2025-01-01",periods=160)
    frame = pd.DataFrame([dict(session=d.date().isoformat(),symbol=str(i),next_day_target_hit=i%2,
                              next_day_resolved_session=(d+pd.Timedelta(days=2)).date().isoformat()) for d in days for i in range(25)])
    folds = list(rolling_blocks(frame,"next_day"))
    seen=set()
    for train,tune,cal,test in folds:
        for left,right in zip((train,tune,cal),(tune,cal,test)):
            assert left.next_day_resolved_session.max() < right.session.min()
        assert not seen.intersection(test.session)
        seen.update(test.session)
    assert len(seen)==60


def test_insufficient_history_does_not_fit_models():
    frame=pd.DataFrame(columns=["session","symbol"])
    result=rolling_validation(frame,"next_day")
    assert not result["passed"] and result["status"]=="insufficient_history"
    assert block_mean_interval([1]*19) is None
    assert block_mean_interval([0]*60)==[0,0]
    assert block_mean_interval([1]*60)==[1,1]


def test_three_rolling_fits_detect_a_known_synthetic_edge():
    from praecursor.ml.features import FEATURES
    rows=[]
    for day in pd.date_range("2025-01-01",periods=141):
        for i in range(20):
            hit=i%2
            rows.append(dict(dict.fromkeys(FEATURES,float(hit)),session=day.date().isoformat(),symbol=str(i),
                             opportunity_score=0,next_day_target_hit=hit,
                             next_day_resolved_session=(day+pd.Timedelta(days=1)).date().isoformat(),
                             next_day_net_return_pct=2 if hit else -1))
    report=rolling_validation(pd.DataFrame(rows),"next_day")
    assert report["passed"] and report["profitable_folds"]==3
    assert report["excess_return_95pct_interval"][0]>0
