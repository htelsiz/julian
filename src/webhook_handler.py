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

        # Fetch repo-specific overrides (fallback for custom per-repo patterns)
        styleguide = await github.fetch_file_raw(
            ctx.installation_id, ctx.owner, ctx.repo_name,
            ".gemini/styleguide.md", ctx.pr_head_ref,
        )
        patterns = await github.fetch_file_raw(
            ctx.installation_id, ctx.owner, ctx.repo_name,
            ".gemini/patterns.md", ctx.pr_head_ref,
        )

        review_body = await gemini.generate_review(diff, guidelines, styleguide, patterns)

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

        # Fetch repo-specific patterns
        patterns = await github.fetch_file_raw(
            ctx.installation_id, ctx.owner, ctx.repo_name,
            ".gemini/patterns.md", ctx.default_branch,
        )

        reply = await gemini.generate_reply(ctx.comment_body, guidelines, patterns)

        await github.post_issue_comment(
            ctx.installation_id, ctx.owner, ctx.repo_name, ctx.issue_number, reply,
        )
        log.info("Posted reply on %s/%s#%d", ctx.owner, ctx.repo_name, ctx.issue_number)
    finally:
        await github.close()
        await gemini.close()
