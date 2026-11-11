"""Recover missing/failed scheduled cloud work once; never depend on a desktop process."""
from datetime import datetime, time, timezone
import json
import os
import subprocess


def due_workflows(now):
    day = now.weekday()  # Monday=0, Sunday=6; all cron timestamps below are UTC.
    due = []
    if day in (5,6,0,1,2):
        due.append(("daily_scan.yml",time(18,30)))
    if day in (6,0,1,2,3):
        due.extend([("model_learning.yml",time(17,15)),("disclosures.yml",time(17,12))])
    if day in (3,4):
        due.append(("weekly_review.yml",time(20,15) if day==3 else time(8,15)))
    return [(name,datetime.combine(now.date(),stamp,timezone.utc)) for name,stamp in due
            if datetime.combine(now.date(),stamp,timezone.utc)<=now]


def needs_recovery(runs, due):
    recent = [r for r in runs if datetime.fromisoformat(r["created_at"].replace("Z","+00:00"))>=due]
    # Manual previews are not proof that a scheduled Telegram delivery happened.
    recent = [r for r in recent if r["event"]=="schedule" or r.get("display_title","").startswith("Watchdog recovery")]
    if any(r["status"]!="completed" or r["conclusion"]=="success" for r in recent):
        return False
    return not any(r.get("display_title","").startswith("Watchdog recovery") for r in recent)


def main():
    repo = os.environ["GITHUB_REPOSITORY"]
    now = datetime.now(timezone.utc)
    preview = os.environ.get("PREVIEW") == "true"
    candidates = []
    busy = False
    for workflow,due in due_workflows(now):
        response = subprocess.run(["gh","api",f"repos/{repo}/actions/workflows/{workflow}/runs?per_page=30"],
                                  check=True,capture_output=True,text=True)
        runs = json.loads(response.stdout)["workflow_runs"]
        busy = busy or any(r["status"]!="completed" for r in runs)
        recover = needs_recovery(runs,due)
        print(f"{workflow}: {'recovery needed' if recover else 'scheduled run present'}")
        if recover:
            candidates.append(workflow)
    # GitHub concurrency holds only one pending job. Never flood the shared database queue.
    if candidates and not busy and not preview:
        subprocess.run(["gh","workflow","run",candidates[0],"--repo",repo,"--ref","main",
                        "-f", "recovery=true"],check=True)
    elif busy:
        print("Cloud work is still active; recovery deferred to the next watchdog check")


if __name__ == "__main__":
    main()
