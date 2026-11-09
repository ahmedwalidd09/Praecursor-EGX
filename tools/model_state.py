"""Transfer accepted models and validation reports between isolated Actions runners."""
import argparse
import json
from pathlib import Path
import re
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
HORIZONS = ("next_day", "swing")


def pack(root=ROOT, archive=None):
    archive = archive or root / "data/model-state.zip"
    archive.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive, "w", ZIP_DEFLATED) as bundle:
        for horizon in HORIZONS:
            report = root / "reports" / f"{horizon}_validation.json"
            if report.exists():
                bundle.write(report, f"{horizon}/report.json")
            active = root / "models" / f"active_{horizon}.json"
            if not active.exists():
                continue
            manifest = json.loads(active.read_text(encoding="utf-8"))
            bundle.write(active, f"{horizon}/active.json")
            for name in ("xgb.json", "lgb.txt"):
                bundle.write(Path(manifest["directory"]) / name, f"{horizon}/{name}")
    return archive


def restore(root=ROOT, archive=None):
    archive = archive or root / "data/model-state.zip"
    with ZipFile(archive) as bundle:
        writes = []
        for horizon in HORIZONS:
            if f"{horizon}/report.json" in bundle.namelist():
                writes.append((root / "reports" / f"{horizon}_validation.json", bundle.read(f"{horizon}/report.json")))
            if f"{horizon}/active.json" not in bundle.namelist():
                continue
            manifest = json.loads(bundle.read(f"{horizon}/active.json"))
            version = manifest["model_version"]
            if not re.fullmatch(r"[A-Za-z0-9_-]+", version) or not manifest.get("promoted"):
                raise ValueError("Invalid accepted model manifest")
            directory = root / "models/validated" / version
            manifest["directory"] = str(directory.resolve())
            for name in ("xgb.json", "lgb.txt"):
                writes.append((directory / name, bundle.read(f"{horizon}/{name}")))
            payload = json.dumps(manifest, indent=2).encode()
            writes.append((directory / "manifest.json", payload))
            writes.append((root / "models" / f"active_{horizon}.json", payload))
        for path, content in writes:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(".tmp")
            temp.write_bytes(content)
            temp.replace(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("pack", "restore"))
    args = parser.parse_args()
    (pack if args.action == "pack" else restore)()
