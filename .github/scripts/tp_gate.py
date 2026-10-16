"""Test-plan gate policy and read-only grounding evidence."""

import json
import re
import subprocess
import tempfile
from pathlib import Path

SCORE_KEYS = {"specificity", "grounding", "scope_fidelity",
              "actionability", "consistency"}
PLAN_NAMES = ("testplan.md", "TestPlan.md")
DESIGN_NAMES = ("design.md", "Design.md", "DESIGN.md", "README.md")
DOCUMENT_NAMES = {*PLAN_NAMES, *DESIGN_NAMES, "prd.md"}
COMPONENTS = (
    "fulfillment-service", "osac-operator", "osac-aap", "osac-installer",
    "bare-metal-fulfillment-operator", "osac-csi-driver", "osac-metering",
    "osac-ui", "proto", "tests/e2e",
)


def write_json(path, data):
    """Publish a complete report without exposing a partially written file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(data, stream, indent=2)
            stream.write("\n")
            stream.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def affected_enhancements(files):
    """Include both sides of document renames, without accepting traversal."""
    pattern = re.compile(r"enhancements/([A-Za-z0-9][A-Za-z0-9._-]*)/([^/]+)")
    affected = set()
    for file in files:
        for key in ("filename", "previous_filename"):
            match = pattern.fullmatch(file.get(key) or "")
            if match and match[2] in DOCUMENT_NAMES:
                affected.add(match[1])
    return sorted(affected)


def validate_verdict(verdict):
    """Validate shape and Ready eligibility without overriding rubric vetoes."""
    errors = []
    if not isinstance(verdict, dict):
        return ["verdict must be a JSON object"]
    scores = verdict.get("scores")
    if not isinstance(scores, dict) or set(scores) != SCORE_KEYS:
        return ["scores must contain exactly the five rubric dimensions"]
    if any(type(value) is not int or value not in range(3)
           for value in scores.values()):
        return ["scores must be integers from 0 to 2 (booleans are invalid)"]
    total = verdict.get("total")
    if type(total) is not int or total != sum(scores.values()):
        errors.append("total must equal the sum of the five scores")
    result = verdict.get("verdict")
    if result not in {"Ready", "Revise", "Rework"}:
        errors.append("unknown or missing verdict")
    if result == "Ready" and (sum(scores.values()) < 8 or 0 in scores.values()):
        errors.append("Ready requires 8-10 with no zero dimension")
    notes = verdict.get("criterionNotes")
    if (not isinstance(notes, dict) or set(notes) != SCORE_KEYS
            or any(not isinstance(note, str) or not note.strip()
                   for note in notes.values())):
        errors.append("criterionNotes must explain each dimension")
    for key in ("summary", "feedback"):
        if not isinstance(verdict.get(key), str) or not verdict[key].strip():
            errors.append(f"missing {key}")
    findings = verdict.get("findings")
    if not isinstance(findings, dict):
        errors.append("findings must be an object")
    else:
        for key in ("critical", "important", "suggestions"):
            items = findings.get(key)
            if not isinstance(items, list) or any(not isinstance(x, str) for x in items):
                errors.append(f"findings.{key} must be a list of strings")
        if result == "Ready" and findings.get("critical"):
            errors.append("Ready cannot contain an unresolved critical finding")
    return errors


def git_sha(root):
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True,
    ).strip()


def grounding_context(root, documents):
    """Read tracked guidance and cited source files, never execute PR content."""
    root = Path(root).resolve()
    tracked = set(subprocess.check_output(
        ["git", "-C", str(root), "ls-files"], text=True,
    ).splitlines())
    required = {"AGENTS.md", "docs/INTEGRATION-TESTING.md"}
    required.update(f"{component}/AGENTS.md" for component in COMPONENTS)
    missing = required - tracked
    if missing:
        raise RuntimeError("Missing OSAC guidance: " + ", ".join(sorted(missing)))
    paths = required | ({"Makefile"} & tracked)
    paths.update(f"{component}/Makefile" for component in COMPONENTS
                 if f"{component}/Makefile" in tracked)
    # Only literal paths under known component roots are candidates. Paths
    # that are absent are disclosed, not guessed or executed as commands.
    prefixes = "|".join(re.escape(x) for x in COMPONENTS)
    cited = set(re.findall(
        rf"(?:{prefixes})/[A-Za-z0-9_./-]+",
        "\n".join(documents.values()),
    ))
    files = {}
    unavailable = []
    for name in sorted(paths | cited):
        path = root / name
        if name not in tracked or not path.is_file():
            unavailable.append(name)
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise RuntimeError(f"Unsafe grounding source: {name}")
        try:
            files[name] = path.read_text()
        except UnicodeDecodeError:
            unavailable.append(name)
    payload = {"osac_sha": git_sha(root), "files": files,
               "unavailable_cited_paths": unavailable}
    if len(json.dumps(payload)) > 600_000:
        raise RuntimeError("Grounding context exceeds the review budget; narrow the plan")
    return payload
