"""Webhook event routing for Julian pattern enforcement."""

import logging

from .gemini_client import generate_review, generate_reply
from .github_auth import get_installation_token

logger = logging.getLogger(__name__)


async def handle_webhook(event_type: str, data: dict) -> None:
    """Route GitHub webhook events to appropriate handlers."""
    action = data.get("action", "")

    if event_type == "pull_request" and action in ("opened", "synchronize", "reopened"):
        await _handle_pr_review(data)
    elif event_type == "issue_comment" and action == "created":
        await _handle_comment_mention(data)
    else:
        logger.debug("[webhook] Ignoring event: %s/%s", event_type, action)


async def _handle_pr_review(data: dict) -> None:
    """Generate and post a pattern-focused code review."""
    pr = data["pull_request"]
    repo = data["repository"]
    installation_id = data["installation"]["id"]

    owner = repo["owner"]["login"]
    repo_name = repo["name"]
    pr_number = pr["number"]

    logger.info("[review] Processing PR #%d in %s/%s", pr_number, owner, repo_name)

    token = await get_installation_token(installation_id)

    # Fetch the diff
    diff = await _fetch_diff(token, owner, repo_name, pr_number)
    if not diff:
        logger.warning("[review] Empty diff for PR #%d", pr_number)
        return

    # Fetch styleguide and patterns from repo (if present)
    styleguide = await _fetch_file(token, owner, repo_name, ".gemini/styleguide.md", pr["head"]["ref"])
    patterns = await _fetch_file(token, owner, repo_name, ".gemini/patterns.md", pr["head"]["ref"])

    # Generate review via Gemini
    review_body = await generate_review(diff, styleguide, patterns)

    # Post the review
    await _post_review(token, owner, repo_name, pr_number, review_body)
    logger.info("[review] Posted review on PR #%d", pr_number)


async def _handle_comment_mention(data: dict) -> None:
    """Reply to @julian mentions in comments."""
    comment = data["comment"]
    body = comment.get("body", "")

    if "@julian" not in body.lower():
        return

    issue = data["issue"]
    repo = data["repository"]
    installation_id = data["installation"]["id"]

    owner = repo["owner"]["login"]
    repo_name = repo["name"]
    issue_number = issue["number"]

    logger.info("[mention] Julian mentioned in %s/%s#%d", owner, repo_name, issue_number)

    token = await get_installation_token(installation_id)

    # Fetch patterns for context
    patterns = await _fetch_file(token, owner, repo_name, ".gemini/patterns.md", "main")

    # Generate reply
    reply = await generate_reply(body, patterns)

    # Post comment
    await _post_comment(token, owner, repo_name, issue_number, reply)
    logger.info("[mention] Posted reply on %s/%s#%d", owner, repo_name, issue_number)


async def _fetch_diff(token: str, owner: str, repo: str, pr_number: int) -> str:
    """Fetch PR diff from GitHub API."""
    import aiohttp

    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3.diff",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                logger.error("[github] Failed to fetch diff: %d", resp.status)
                return ""
            return await resp.text()


async def _fetch_file(token: str, owner: str, repo: str, path: str, ref: str) -> str | None:
    """Fetch file contents from repo, returns None if not found."""
    import aiohttp
    import base64

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={ref}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 404:
                return None
            if resp.status != 200:
                logger.warning("[github] Failed to fetch %s: %d", path, resp.status)
                return None
            data = await resp.json()
            content = data.get("content", "")
            return base64.b64decode(content).decode("utf-8")


async def _post_review(token: str, owner: str, repo: str, pr_number: int, body: str) -> None:
    """Post a PR review comment."""
    import aiohttp

    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    payload = {"body": body, "event": "COMMENT"}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status not in (200, 201):
                text = await resp.text()
                logger.error("[github] Failed to post review: %d %s", resp.status, text)


async def _post_comment(token: str, owner: str, repo: str, issue_number: int, body: str) -> None:
    """Post an issue/PR comment."""
    import aiohttp

    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    payload = {"body": body}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status not in (200, 201):
                text = await resp.text()
                logger.error("[github] Failed to post comment: %d %s", resp.status, text)
