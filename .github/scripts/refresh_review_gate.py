import json
import os
from pathlib import Path
import subprocess
import time


WORKFLOW_PATH = ".github/workflows/review-gate.yml"


def api(endpoint, method="GET", paginate=False):
    command = ["gh", "api", "--method", method, endpoint]
    if paginate:
        command.extend(["--paginate", "--slurp"])
    result = subprocess.run(command, check=True, text=True, capture_output=True)
    if method == "GET":
        return json.loads(result.stdout)


def same_revision(pull, source, repo):
    return (
        pull["base"]["repo"]["full_name"] == repo
        and pull["base"]["ref"] == "main"
        and pull["head"]["sha"] == source["head_sha"]
        and pull["head"]["ref"] == source["head_branch"]
    )


def validate_run(run, repo, workflow_id, event):
    if (
        run["repository"]["full_name"] != repo or run["workflow_id"] != workflow_id
        or run["path"] != WORKFLOW_PATH or run["event"] != event
    ):
        raise ValueError("Wrong review-gate run identity")


def refresh(event, repo):
    source_id = event["workflow_run"]["id"]
    workflow = api(f"repos/{repo}/actions/workflows/review-gate.yml")
    source = api(f"repos/{repo}/actions/runs/{source_id}")
    validate_run(source, repo, workflow["id"], "pull_request_review")
    if (
        event["action"] != "completed" or source["status"] != "completed"
        or any(source[key] != event["workflow_run"][key] for key in ("id", "head_sha", "head_branch"))
    ):
        raise ValueError("Source differs from lock or is not completed")
    pages = api(
        f"repos/{repo}/commits/{source['head_sha']}/pulls?per_page=100",
        paginate=True,
    )
    matches = [pull for page in pages for pull in page if same_revision(pull, source, repo)]
    if not matches:
        print("No current PR revision matches this review event")
        return
    if len(matches) != 1:
        raise ValueError("Ambiguous PR association")
    number = matches[0]["number"]
    pull_endpoint = f"repos/{repo}/pulls/{number}"
    pull = api(pull_endpoint)
    if pull["number"] != number:
        raise ValueError("Wrong PR returned")
    if pull["state"] != "open" or not same_revision(pull, source, repo):
        print("PR closed or head changed; ignoring stale review event")
        return
    fork = pull["head"]["repo"]["full_name"]
    if source["head_repository"]["full_name"] not in (repo, fork):
        raise ValueError("Wrong source repository")
    pages = api(
        f"repos/{repo}/actions/workflows/{workflow['id']}/runs"
        f"?event=pull_request&head_sha={source['head_sha']}&per_page=100",
        paginate=True,
    )
    targets = [
        run for page in pages for run in page["workflow_runs"]
        if run["head_sha"] == source["head_sha"] and run["head_branch"] == source["head_branch"]
        and run["head_repository"]["full_name"] == fork
    ]
    if not targets:
        raise ValueError("No matching original pull_request gate run")
    for target in targets:
        endpoint = f"repos/{repo}/actions/runs/{target['id']}"
        for attempt in range(60):
            current = api(pull_endpoint)
            if current["number"] != number:
                raise ValueError("Wrong current PR returned")
            if (
                current["state"] != "open" or not same_revision(current, source, repo)
                or current["head"]["repo"]["full_name"] != fork
            ):
                print("PR closed or head changed while waiting")
                return
            run = api(endpoint)
            validate_run(run, repo, workflow["id"], "pull_request")
            if (
                run["id"] != target["id"] or run["head_sha"] != source["head_sha"]
                or run["head_branch"] != source["head_branch"]
                or run["head_repository"]["full_name"] != fork
            ):
                raise ValueError("Target revision changed")
            if any(item["number"] != number for item in run["pull_requests"]):
                raise ValueError("Target PR association changed")
            if run["status"] == "completed":
                api(endpoint + "/rerun", method="POST")
                print(f"Requested refresh of PR gate run {run['id']}")
                break
            time.sleep(5)
        else:
            raise TimeoutError("PR gate still active; refusing an overlapping rerun")


if __name__ == "__main__":
    refresh(json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text()), os.environ["GITHUB_REPOSITORY"])
