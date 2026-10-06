"""Call Claude on Vertex AI without giving the model a shell or credentials."""

import os

import requests


VERTEX_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
ANTHROPIC_VERSION = "vertex-2023-10-16"
DEFAULT_MODEL = "claude-opus-4-6"


def complete(prompt, system, max_tokens, *, model=None, project_id=None,
             region=None, credentials=None, session=None):
    """Return Claude's text response and usage metadata.

    The Vertex credential is used only by this trusted HTTP client. The
    request has no tools, and the model response is returned as data; it is
    never passed to a shell or an agent runner.
    """
    if credentials is None:
        import google.auth
        from google.auth.transport.requests import Request

        credentials, discovered_project = google.auth.default(
            scopes=[VERTEX_SCOPE]
        )
        if not project_id:
            project_id = discovered_project
        credentials.refresh(Request())

    project_id = project_id or os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID")
    region = region or os.environ.get("CLOUD_ML_REGION", "global")
    model = model or os.environ.get("TP_REVIEW_MODEL", DEFAULT_MODEL)
    if not project_id:
        raise RuntimeError("ANTHROPIC_VERTEX_PROJECT_ID is not set")
    if not credentials.token:
        raise RuntimeError("Google credentials did not provide an access token")

    api_host = (
        "aiplatform.googleapis.com"
        if region == "global"
        else f"{region}-aiplatform.googleapis.com"
    )
    endpoint = (
        f"https://{api_host}/v1/projects/{project_id}/locations/{region}/"
        f"publishers/anthropic/models/{model}:rawPredict"
    )
    body = {
        "anthropic_version": ANTHROPIC_VERSION,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }

    client = session or requests
    response = client.post(
        endpoint,
        headers={
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        json=body,
        timeout=(10, 300),
    )
    if not response.ok:
        raise RuntimeError(
            f"Vertex AI request failed with HTTP {response.status_code}"
        )

    result = response.json()
    text_blocks = [
        block.get("text", "")
        for block in result.get("content", [])
        if block.get("type") == "text"
    ]
    text = "\n".join(part for part in text_blocks if part).strip()
    if not text:
        raise RuntimeError("Vertex AI response did not contain text output")
    usage = dict(result.get("usage", {}))
    usage["stop_reason"] = result.get("stop_reason")
    return text, usage
