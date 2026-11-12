import json
import os
from pathlib import Path
import re
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


def require(condition, message):
    if not condition:
        raise ValueError(message)


def positive_id(value):
    return type(value) is int and value > 0


def list_items(pages, key=None):
    require(isinstance(pages, list), "Expected paginated response")
    items = []
    for page in pages:
        batch = page[key] if key else page
        require(isinstance(batch, list), "Expected an array on each page")
        require(all(isinstance(item, dict) for item in batch), "Invalid list item")
        items.extend(batch)
    return items


def same_revision(pull, source, repo):
    return (
        pull["base"]["repo"]["full_name"] == repo
        and pull["base"]["ref"] == "main"
        and pull["head"]["sha"] == source["head_sha"]
        and pull["head"]["ref"] == source["head_branch"]
    )


def validate_run(run, repo, workflow_id, event):
    require(positive_id(run["id"]), "Invalid run ID")
    require(run["repository"]["full_name"] == repo, "Wrong run repository")
    require(run["workflow_id"] == workflow_id, "Wrong workflow ID")
    require(run["path"] == WORKFLOW_PATH, "Wrong workflow path")
    require(run["event"] == event, "Wrong triggering event")
    require(re.fullmatch(r"[0-9a-f]{40}", run["head_sha"]), "Invalid head SHA")
    require(bool(run["head_branch"]), "Missing head branch")


def refresh(event, repo):
    require(re.fullmatch(r"[\w.-]+/[\w.-]+", repo), "Invalid repository")
    require(event["action"] == "completed", "Expected completed workflow")
    source_id = event["workflow_run"]["id"]
    require(positive_id(source_id), "Invalid source run ID")
    workflow = api(f"repos/{repo}/actions/workflows/review-gate.yml")
    require(workflow["path"] == WORKFLOW_PATH, "Wrong workflow")
    require(positive_id(workflow["id"]), "Invalid workflow ID")
    source = api(f"repos/{repo}/actions/runs/{source_id}")
    require(source["id"] == source_id, "Wrong source run")
    validate_run(source, repo, workflow["id"], "pull_request_review")
    require(source["status"] == "completed", "Source is not completed")
    pulls = list_items(api(
        f"repos/{repo}/commits/{source['head_sha']}/pulls?per_page=100",
        paginate=True,
    ))
    matches = [pull for pull in pulls if same_revision(pull, source, repo)]
    if not matches:
        print("No current PR revision matches this review event")
        return
    require(len(matches) == 1, "Ambiguous PR association")
    pull = matches[0]
    require(positive_id(pull["number"]), "Invalid PR number")
    pull_endpoint = f"repos/{repo}/pulls/{pull['number']}"
    pull = api(pull_endpoint)
    if pull["state"] != "open" or not same_revision(pull, source, repo):
        print("PR closed or head changed; ignoring stale review event")
        return
    fork = pull["head"]["repo"]["full_name"]
    require(source["head_repository"]["full_name"] in (repo, fork), "Wrong source repository")
    runs = list_items(api(
        f"repos/{repo}/actions/workflows/{workflow['id']}/runs"
        f"?event=pull_request&head_sha={source['head_sha']}&per_page=100",
        paginate=True,
    ), "workflow_runs")
    targets = []
    for run in runs:
        validate_run(run, repo, workflow["id"], "pull_request")
        if (
            run["head_sha"] == source["head_sha"]
            and run["head_branch"] == source["head_branch"]
            and run["head_repository"]["full_name"] == fork
        ):
            associations = run["pull_requests"]
            require(isinstance(associations, list), "Invalid run PR association")
            if associations:
                require(
                    all(item["number"] == pull["number"] for item in associations),
                    "Wrong target PR",
                )
            targets.append(run)
    require(bool(targets), "No matching original pull_request gate run")
    for target in targets:
        endpoint = f"repos/{repo}/actions/runs/{target['id']}"
        for attempt in range(60):
            current = api(pull_endpoint)
            if current["state"] != "open" or not same_revision(current, source, repo):
                print("PR closed or head changed while waiting")
                return
            run = api(endpoint)
            validate_run(run, repo, workflow["id"], "pull_request")
            require(run["id"] == target["id"], "Wrong target run")
            require(run["head_sha"] == source["head_sha"], "Target head changed")
            require(run["head_branch"] == source["head_branch"], "Target branch changed")
            require(run["head_repository"]["full_name"] == fork, "Target repository changed")
            if run["status"] == "completed":
                api(endpoint + "/rerun", method="POST")
                print(f"Requested refresh of PR gate run {run['id']}")
                break
            time.sleep(5)
        else:
            raise TimeoutError("PR gate still active; refusing an overlapping rerun")


if __name__ == "__main__":
    refresh(json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text()), os.environ["GITHUB_REPOSITORY"])
