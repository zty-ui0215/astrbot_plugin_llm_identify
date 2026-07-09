from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode


DEFAULT_REPOSITORY = "zty-ui0215/llm-identify-trusted-references"
DEFAULT_ISSUE_URL = f"https://github.com/{DEFAULT_REPOSITORY}/issues/new"


def build_github_issue_url(package: dict[str, Any], issue_url: str = DEFAULT_ISSUE_URL) -> str:
    title = f"Trusted reference candidate: {package.get('endpoint', {}).get('provider', 'unknown')} / {package.get('model', {}).get('claimed_by_official_endpoint', 'unknown')}"
    body = "Paste this sanitized evidence package into the issue form for maintainer review.\n\n```json\n" + json.dumps(package, ensure_ascii=True, indent=2) + "\n```"
    return issue_url + "?" + urlencode({"title": title[:180], "body": body})
