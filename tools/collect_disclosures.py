"""Archive official public disclosures; failures preserve prior evidence and fail the job."""
from pathlib import Path
import sys
from contextlib import closing
import json
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from praecursor.storage.database import connect
from praecursor.collectors.egx_disclosures import collect

if __name__ == "__main__":
    with closing(connect()) as conn:
        result = collect(conn)
    print(json.dumps(result))
    raise SystemExit(1 if result["status"] == "unavailable" else 0)
