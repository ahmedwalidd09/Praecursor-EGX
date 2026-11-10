import pandas as pd
from praecursor.analysis.research import frozen_evidence


def test_matched_complete_sessions_and_cost_stress():
    frame=pd.DataFrame([dict(session="2026-10-01",symbol=str(i),candidate_rank=i+1 if i<5 else None,
                            next_day_target_hit=1,next_day_net_return_pct=2 if i<5 else 0,
                            next_day_status="target") for i in range(10)])
    result=frozen_evidence(frame)
    assert result["sessions"]==1 and result["selections"]==5
    assert result["mean_net_return_pct"]==2 and result["universe_mean_net_return_pct"]==1
    assert result["stressed_net_return_pct"]==1.5 and result["excess_95pct_interval"] is None
    frame.loc[0,"next_day_net_return_pct"]=None
    assert frozen_evidence(frame)["sessions"]==0
