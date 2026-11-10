"""Expanding-window challenger checks with disjoint tests and maturity purging."""
import numpy as np
from sklearn.isotonic import IsotonicRegression


def block_mean_interval(values, draws=2000, block=5):
    values = np.asarray(values, dtype=float)
    if len(values) < 20 or not np.isfinite(values).all():
        return None
    rng = np.random.default_rng(42)
    starts = rng.integers(0, len(values), size=(draws, (len(values) + block - 1) // block))
    indices = (starts[:, :, None] + np.arange(block)) % len(values)
    sampled = values[indices.reshape(draws, -1)[:, :len(values)]].mean(axis=1)
    return [float(x) for x in np.quantile(sampled, [.025, .975])]


def rolling_blocks(frame, horizon):
    frame = frame.sort_values(["session", "symbol"]).drop_duplicates(["session", "symbol"], keep="last")
    days = sorted(frame.session.unique())
    maturity = 1 if horizon == "next_day" else 20
    days = days[:-maturity]
    if len(days) < 140:
        raise ValueError(f"Rolling validation needs 140 mature sessions; available {len(days)}")
    target, resolved = horizon + "_target_hit", horizon + "_resolved_session"
    for start in range(len(days) - 60, len(days), 20):
        a, b = int(start * .6), int(start * .8)
        groups = [days[:a], days[a:b], days[b:start], days[start:start + 20]]
        blocks = [frame[frame.session.isin(group)].copy() for group in groups]
        for i in range(3):
            blocks[i] = blocks[i][blocks[i][target].notna() & (blocks[i][resolved] < groups[i + 1][0])]
            if blocks[i].session.nunique() < 5 or len(blocks[i]) < 100 or blocks[i][target].nunique() < 2:
                raise ValueError("Rolling training/tuning/calibration block too small after maturity purge")
        yield blocks


def rolling_validation(frame, horizon):
    from praecursor.ml.validation import fit_challenger, metrics
    try:
        folds = list(rolling_blocks(frame, horizon))
    except ValueError as exc:
        return dict(status="insufficient_history", passed=False, reason=str(exc), folds=[])
    reports, excess = [], []
    for train, tune, calibration, test in folds:
        xgb, lgb, weights, chosen = fit_challenger(train, tune, horizon)
        def raw(rows):
            from praecursor.ml.features import FEATURES
            return weights["xgb"] * xgb.predict_proba(rows[FEATURES])[:, 1] + weights["lgb"] * lgb.predict_proba(rows[FEATURES])[:, 1]
        calibrator = IsotonicRegression(out_of_bounds="clip").fit(raw(calibration), calibration[horizon + "_target_hit"])
        probabilities = calibrator.predict(raw(test))
        challenger = metrics(test, probabilities, horizon)
        baseline = metrics(test, test.opportunity_score.to_numpy() / 100, horizon)
        scored = test.assign(probability=probabilities)
        chosen_rows = scored.sort_values(["session", "probability", "symbol"], ascending=[True,False,True]).groupby("session").head(5)
        base_rows = test.sort_values(["session", "opportunity_score", "symbol"], ascending=[True,False,True]).groupby("session").head(5)
        target = horizon + "_net_return_pct"
        complete = challenger["execution_coverage"] == 1 and baseline["execution_coverage"] == 1
        if complete:
            delta = chosen_rows.groupby("session")[target].mean() - base_rows.groupby("session")[target].mean()
            excess.extend(delta.to_list())
        reports.append(dict(train_end=str(train.session.max()), tune_end=str(tune.session.max()),
                            calibration_end=str(calibration.session.max()), test_start=str(test.session.min()),
                            test_end=str(test.session.max()), chosen_model=chosen, challenger=challenger, baseline=baseline,
                            complete=complete))
    interval = block_mean_interval(excess)
    profitable_folds = sum((r["challenger"]["net_expectancy_pct"] or 0) > 0 and
                           (r["challenger"]["net_expectancy_pct"] or 0) > (r["baseline"]["net_expectancy_pct"] or 0) for r in reports)
    passed = all(r["complete"] for r in reports) and profitable_folds >= 2 and interval is not None and interval[0] > 0
    return dict(status="evaluated", passed=passed, folds=reports, profitable_folds=profitable_folds,
                excess_return_95pct_interval=interval, session_block_length=5,
                reason="Passed three rolling tests" if passed else "Insufficient consistent net-return advantage over technical ranking")
