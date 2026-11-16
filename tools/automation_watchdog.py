"""Recover missing/failed scheduled cloud work once; never depend on a desktop process."""
from datetime import datetime, time, timedelta, timezone
import json
import os
import subprocess
from zoneinfo import ZoneInfo


DATABASE_WORKFLOWS = ("daily_scan.yml", "model_learning.yml", "disclosures.yml", "weekly_review.yml")


def due_workflows(now):
    # GitHub may start the evening watchdog after UTC midnight. Check its
    # preceding evening cycle while the scanner can still publish pre-open.
    cycle = now.date()
    local = now.astimezone(ZoneInfo("Africa/Cairo"))
    if local.time() < time(9):
        cycle = local.date() - timedelta(days=1)
    day = cycle.weekday()
    due = []
    if day in (5,6,0,1,2):
        due.append(("daily_scan.yml",time(18,30)))
    if day in (6,0,1,2,3):
        due.extend([("model_learning.yml",time(17,15)),("disclosures.yml",time(17,12))])
    if day in (3,4):
        due.append(("weekly_review.yml",time(20,15) if day==3 else time(8,15)))
    return [(name,datetime.combine(cycle,stamp,timezone.utc)) for name,stamp in due
            if datetime.combine(cycle,stamp,timezone.utc)<=now]


def needs_recovery(runs, due):
    recent = [r for r in runs if r["head_branch"] == "main"
              and datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) >= due]
    # Manual previews are not proof that a scheduled Telegram delivery happened.
    recent = [r for r in recent if r["event"]=="schedule" or r.get("display_title","").startswith("Watchdog recovery")]
    if any(r["status"]!="completed" or r["conclusion"]=="success" for r in recent):
        return False
    return not any(r.get("display_title","").startswith("Watchdog recovery") for r in recent)


def main():
    repo = os.environ["GITHUB_REPOSITORY"]
    now = datetime.now(timezone.utc)
    preview = os.environ.get("PREVIEW") == "true"
    due_by_workflow = dict(due_workflows(now))
    candidates = []
    statuses = {}
    busy = False
    for workflow in DATABASE_WORKFLOWS:
        response = subprocess.run(["gh","api",f"repos/{repo}/actions/workflows/{workflow}/runs?per_page=30"],
                                  check=True,capture_output=True,text=True)
        runs = json.loads(response.stdout)["workflow_runs"]
        busy = busy or any(r["status"]!="completed" for r in runs)
        due = due_by_workflow.get(workflow)
        production = [r for r in runs if r.get("head_branch") == "main" and
                      (r.get("event") == "schedule" or r.get("display_title","").startswith("Watchdog recovery"))]
        last_success = max((r["created_at"] for r in production if r.get("conclusion") == "success"), default=None)
        recover = due is not None and needs_recovery(runs,due)
        status = dict(due_at=due.isoformat() if due else None, last_success_run_created_at=last_success,
                      state="outside_due_window", reason=None)
        if due is not None:
            recent = [r for r in production if datetime.fromisoformat(r["created_at"].replace("Z","+00:00")) >= due]
            if any(r["conclusion"] == "success" for r in recent):
                status["state"] = "healthy"
            elif any(r["status"] != "completed" for r in recent):
                status["state"] = "waiting"
            else:
                status.update(state="failed", reason="Scheduled run missing or unsuccessful" if recover else "Recovery attempt exhausted")
        statuses[workflow] = status
        if recover:
            candidates.append(workflow)
    # GitHub concurrency holds only one pending job. Never flood the shared database queue.
    action = ("defer_active_writer" if busy and candidates else "preview_recovery" if candidates and preview
              else "dispatch_recovery" if candidates else "none")
    print(json.dumps(dict(as_of=now.isoformat(), workflows=statuses, action=action,
                          next_workflow=candidates[0] if candidates else None)), flush=True)
    if action == "dispatch_recovery":
        subprocess.run(["gh","workflow","run",candidates[0],"--repo",repo,"--ref","main",
                        "-f", "recovery=true"],check=True)
    elif busy:
        print("Cloud work is still active; recovery deferred to the next watchdog check")


if __name__ == "__main__":
    main()
