"""Refresh the cloud news index without loading scanner state or credentials."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from praecursor.collectors.news import collect, load_snapshot, write_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    previous = load_snapshot(args.previous.read_bytes()) if args.previous else {}
    state = collect(previous, datetime.now(timezone.utc))
    print(json.dumps({"sources": state["sources"], "items": len(state["items"])}, ensure_ascii=False))
    if not previous and not any(feed["status"] == "ok" for feed in state["sources"].values()):
        parser.exit(1, "No news sources available for the initial snapshot\n")
    write_snapshot(args.output, state)


if __name__ == "__main__":
    main()
