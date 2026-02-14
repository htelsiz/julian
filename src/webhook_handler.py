"""Webhook event routing for Julian pattern enforcement.

Loads relevant guidelines based on file extensions in the PR diff,
then passes them to Gemini alongside the diff for review.
"""

import logging
from pathlib import Path

from src.clients.github import GitHubClient
from src.config import JulianSettings
from src.gemini_client import GeminiClient
from src.models.github import WebhookContext

log = logging.getLogger(__name__)

# Map file extensions to guideline files
_EXT_TO_GUIDE: dict[str, str] = {
    ".py": "python.md",
    ".go": "go.md",
    ".swift": "swift.md",
    ".ts": "typescript.md",
    ".tsx": "typescript.md",
    ".js": "typescript.md",
    ".jsx": "typescript.md",
    ".nix": "nix.md",
}

# Always included regardless of file extensions
_ALWAYS_INCLUDE = ("universal.md", "security.md")

_MAX_COMMENT_LEN = 200
_MAX_TOTAL_LEN = 4000


def _format_existing_comments(
    pr_comments: list[dict],
    reviews: list[dict],
    issue_comments: list[dict],
) -> str:
    """Format existing PR feedback into a summary for the Gemini prompt."""
    lines: list[str] = []

    for c in pr_comments:
        login = c.get("user", {}).get("login", "unknown")
        tag = login.replace("[bot]", "") if login.endswith("[bot]") else "human"
        path = c.get("path", "")
        line_num = c.get("line") or c.get("original_line") or "?"
        body = (c.get("body") or "")[:_MAX_COMMENT_LEN]
        lines.append(f"[{tag}] {path}:{line_num} — {body}")

    for r in reviews:
        body = (r.get("body") or "").strip()
        if not body:
            continue
        login = r.get("user", {}).get("login", "unknown")
        tag = login.replace("[bot]", "") if login.endswith("[bot]") else "human"
        lines.append(f"[{tag} review] {body[:_MAX_COMMENT_LEN]}")

    for c in issue_comments:
        login = c.get("user", {}).get("login", "unknown")
        tag = login.replace("[bot]", "") if login.endswith("[bot]") else "human"
        body = (c.get("body") or "")[:_MAX_COMMENT_LEN]
        lines.append(f"[{tag} comment] {body}")

    if not lines:
        return ""

    result = "\n".join(lines)
    if len(result) > _MAX_TOTAL_LEN:
        result = result[:_MAX_TOTAL_LEN] + "\n...(truncated)"
    return result


def _load_guidelines(diff: str, guidelines_dir: str) -> str:
    """Load relevant guideline files based on file extensions in the diff.

    Parses diff headers (--- a/path and +++ b/path) to extract file extensions,
    maps them to guideline files, and concatenates the contents.
    Always includes universal.md and security.md.
    """
    base = Path(guidelines_dir)
    if not base.is_dir():
        log.warning("Guidelines directory not found: %s", guidelines_dir)
        return ""

    # Extract unique guideline filenames from diff file extensions
    guide_files: set[str] = set()
    for line in diff.splitlines():
        if line.startswith("+++ b/") or line.startswith("--- a/"):
            path = line.split("/", 1)[-1] if "/" in line else line
            for ext, guide in _EXT_TO_GUIDE.items():
                if path.endswith(ext):
                    guide_files.add(guide)
                    break

    # Always include universal + security
    for name in _ALWAYS_INCLUDE:
        guide_files.add(name)

    # Read and concatenate
    parts: list[str] = []
    for name in sorted(guide_files):
        filepath = base / name
        if filepath.exists():
            parts.append(filepath.read_text())
        else:
            log.warning("Guideline file missing: %s", filepath)

    return "\n\n---\n\n".join(parts)


async def handle_webhook(event_type: str, data: dict) -> None:
    """Route GitHub webhook events to appropriate handlers."""
    ctx = WebhookContext.from_webhook(event_type, data)

    if ctx.is_pr_review:
        await _handle_pr_review(ctx)
    elif ctx.is_mention:
        await _handle_comment_mention(ctx)
    else:
        log.debug("Ignoring event: %s/%s", event_type, ctx.action)


async def _handle_pr_review(ctx: WebhookContext) -> None:
    """Generate and post a pattern-focused code review."""
    log.info("Processing PR #%d in %s/%s", ctx.pr_number, ctx.owner, ctx.repo_name)

    github = GitHubClient.from_env()
    gemini = GeminiClient.from_env()
    settings = JulianSettings()

    try:
        diff = await github.fetch_diff(ctx.installation_id, ctx.owner, ctx.repo_name, ctx.pr_number)
        if not diff:
            log.warning("Empty diff for PR #%d", ctx.pr_number)
            return

        # Load guidelines based on file extensions in the diff
        guidelines = _load_guidelines(diff, settings.guidelines_dir)

        # Fetch existing comments to avoid repeating feedback
        pr_comments = await github.get_pr_comments(
            ctx.installation_id, ctx.owner, ctx.repo_name, ctx.pr_number,
        )
        reviews = await github.get_pr_reviews(
            ctx.installation_id, ctx.owner, ctx.repo_name, ctx.pr_number,
        )
        issue_comments = await github.get_issue_comments(
            ctx.installation_id, ctx.owner, ctx.repo_name, ctx.pr_number,
        )
        existing_feedback = _format_existing_comments(pr_comments, reviews, issue_comments)

        review_body = await gemini.generate_review(diff, guidelines, existing_feedback)

        await github.post_review(ctx.installation_id, ctx.owner, ctx.repo_name, ctx.pr_number, review_body)
        log.info("Posted review on PR #%d", ctx.pr_number)
    finally:
        await github.close()
        await gemini.close()


async def _handle_comment_mention(ctx: WebhookContext) -> None:
    """Reply to @julian mentions in comments."""
    log.info("Julian mentioned in %s/%s#%d", ctx.owner, ctx.repo_name, ctx.issue_number)

    github = GitHubClient.from_env()
    gemini = GeminiClient.from_env()
    settings = JulianSettings()

    try:
        # Load universal guidelines for reply context
        guidelines = _load_guidelines("", settings.guidelines_dir)

        reply = await gemini.generate_reply(ctx.comment_body, guidelines)

        await github.post_issue_comment(
            ctx.installation_id, ctx.owner, ctx.repo_name, ctx.issue_number, reply,
        )
        log.info("Posted reply on %s/%s#%d", ctx.owner, ctx.repo_name, ctx.issue_number)
    finally:
        await github.close()
        await gemini.close()
