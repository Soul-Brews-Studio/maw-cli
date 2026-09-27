#!/usr/bin/env python3
"""CI gate (#49): decide whether a scheduled CI run should execute the smoke matrix.

Runs the matrix when:
  - the run was started by hand (workflow_dispatch), or
  - no earlier CI run on alpha actually executed and passed its smoke jobs, or
  - alpha's head differs from the last tested head (new commits: at most hourly), or
  - the last tested run is 23h or older (a daily heartbeat when nothing changes).

"Tested" means every smoke job completed with success. A run whose smoke jobs
were skipped by this gate concludes success too, so it never counts as tested.
Writes run=true|false and reason=... to $GITHUB_OUTPUT (or stdout locally).
"""
import datetime as dt
import json
import os
import subprocess

HEARTBEAT = dt.timedelta(hours=23)


def api(path):
    return json.loads(subprocess.check_output(["gh", "api", path], text=True))


def tested(repo, run):
    jobs = api(f"repos/{repo}/actions/runs/{run['id']}/jobs?per_page=100")["jobs"]
    smoke = [job for job in jobs if job["name"].startswith("smoke")]
    return bool(smoke) and all(job["status"] == "completed" and job["conclusion"] == "success" for job in smoke)


def decide(event, head, now, runs, is_tested):
    if event == "workflow_dispatch":
        return True, "started by hand"
    for run in runs:
        if run["conclusion"] != "success" or not is_tested(run):
            continue
        created = dt.datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
        if run["head_sha"] != head:
            return True, f"alpha moved since last tested run {run['id']} ({run['head_sha'][:7]} -> {head[:7]})"
        if now - created >= HEARTBEAT:
            return True, f"daily heartbeat: last tested run {run['id']} is {now - created} old"
        return False, f"alpha unchanged since tested run {run['id']} ({head[:7]}, {now - created} ago)"
    return True, "no earlier tested run on alpha"


def main():
    repo, event, head, this_run = (os.environ[name] for name in ("REPO", "EVENT", "HEAD_SHA", "RUN_ID"))
    listed = api(f"repos/{repo}/actions/workflows/ci.yml/runs?branch=alpha&status=completed&per_page=30")
    runs = [run for run in listed["workflow_runs"] if str(run["id"]) != this_run]
    run, reason = decide(event, head, dt.datetime.now(dt.timezone.utc), runs, lambda r: tested(repo, r))
    lines = f"run={'true' if run else 'false'}\nreason={reason}\n"
    print(lines, end="")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            output.write(lines)


if __name__ == "__main__":
    main()
