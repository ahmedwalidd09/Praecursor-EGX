"""Load only promoted feature-compatible models that predate the prediction session."""
from functools import lru_cache
from pathlib import Path
import json
import logging
import numpy as np
import pandas as pd
from praecursor.ml.features import FEATURES, FEATURE_VERSION, feature_row
from praecursor.analysis.outcomes import LABEL_VERSION

ROOT=Path(__file__).resolve().parents[3]
log=logging.getLogger(__name__)


@lru_cache(maxsize=8)
def _models(manifest_path, mtime):
    import xgboost as xgb
    import lightgbm as lgb
    manifest=json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    models={}
    for kind,weight in manifest["weights"].items():
        if not weight:
            continue
        if kind=="xgb":
            model=xgb.XGBClassifier(); model.load_model(str(Path(manifest["directory"])/"xgb.json"))
        else:
            model=lgb.Booster(model_file=str(Path(manifest["directory"])/"lgb.txt"))
        models[kind]=model
    return manifest,models


def predict_validated(values, setup_score, horizon, session):
    path=ROOT/"models"/f"active_{horizon}.json"
    if not path.exists():
        return None, {"reason":"No model has passed independent session validation"}
    try:
        manifest,models=_models(str(path),path.stat().st_mtime_ns)
        if (not manifest.get("promoted") or manifest.get("feature_version")!=FEATURE_VERSION
                or manifest.get("label_version")!=LABEL_VERSION or manifest.get("features")!=FEATURES):
            return None,{"reason":"Model feature contract is incompatible"}
        if manifest.get("validation_protocol") != 4 or not manifest.get("rolling_validation", {}).get("passed"):
            return None,{"reason":"Model has not passed the current rolling-validation protocol"}
        if not session or str(session)<=manifest["data_cutoff"]:
            return None,{"reason":"Model contains data from this session or later"}
        row=pd.DataFrame([feature_row(values,setup_score)],columns=FEATURES)
        if row.isna().mean(axis=1).iloc[0]>.2:
            return None,{"reason":"Too many unavailable features"}
        raw=0.
        for kind,model in models.items():
            p=float(model.predict_proba(row)[0,1]) if kind=="xgb" else float(model.predict(row)[0])
            raw+=manifest["weights"][kind]*p
        cal=manifest["calibration"]
        p=float(np.interp(raw,cal["x"],cal["y"]))
        if not np.isfinite(p) or not 0<=p<=1:
            raise ValueError("Invalid probability")
        return p,manifest
    except Exception as exc:
        log.warning("Validated %s model unavailable: %s",horizon,exc)
        return None,{"reason":str(exc)}
