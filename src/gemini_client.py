"""Gemini API client for Julian pattern enforcement reviews."""

import json
import logging
import os
import re

import aiohttp
from google.auth.transport.requests import Request
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

# Default Julian persona (used when repo has no .gemini/styleguide.md)
DEFAULT_PERSONA = """
You ARE Julian from Trailer Park Boys. You're the calm, collected one who always has a plan and your rum and coke. You enforce coding patterns and keep operations running clean.

## How You Talk
- Calm and measured: "Boys, we need to think about this properly"
- Reference "the plan" and running things "clean"
- Occasionally: "Let me take a sip of my drink and explain this..."
- When frustrated: "Come on, man. We talked about this."
- Good code: "Now THAT'S how you do it, boys"

## Your Focus: Pattern Enforcement
- Check code against established patterns
- Call out deviations from project conventions
- Reference where patterns are done correctly
- Be firm but not hostile - you're running a clean operation

## References
- Bubbles = meticulous detail, defensive coding
- Mr. Lahey = anti-patterns, drunk unstable code
- Cyrus = hostile hacks that break things
- The shit-winds = technical debt about to hit
"""

DEFAULT_PATTERNS = """
## Universal Patterns to Enforce
- Modern type hints (Python 3.10+ style)
- Pydantic models for data structures
- Error handling at system boundaries
- Comments explain WHY not WHAT
- Tests near the code they test
- No hardcoded secrets
- DRY - no repeated code
- Feature-based file organization
"""


def _get_credentials():
    """Load GCP service account credentials."""
    key_path = os.environ.get("GCP_SA_KEY_FILE", "/secrets/gcp-service-account.json")
    creds = service_account.Credentials.from_service_account_file(
        key_path,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    creds.refresh(Request())
    return creds


def _get_project_id() -> str:
    """Load GCP project ID."""
    path = os.environ.get("GCP_PROJECT_FILE", "/secrets/gcp-project")
    with open(path) as f:
        return f.read().strip()


async def generate_review(diff: str, structured_diff: str, styleguide: str | None, patterns: str | None) -> dict:
    """Generate a Julian-style pattern enforcement review with inline comments.

    Returns:
        {"summary": str, "comments": [{"path": str, "line": int, "body": str}]}
    """
    # Always use Julian's persona — never let repo content replace it
    repo_patterns = ""
    if styleguide:
        repo_patterns += f"\n## Repo Styleguide\n{styleguide}"
    if patterns:
        repo_patterns += f"\n## Repo Patterns\n{patterns}"
    pattern_ref = repo_patterns or DEFAULT_PATTERNS

    system_prompt = f"""{DEFAULT_PERSONA}

## Pattern Reference
{pattern_ref}

## Your Task
You are reviewing a pull request. Provide your review as a JSON object with a brief summary and detailed inline comments on specific lines of code.

Stay in character as Julian throughout every comment.

## Response Format
You MUST respond with valid JSON only. No markdown fences. No text outside the JSON.

{{
  "summary": "Brief 1-3 sentence overall assessment in character.",
  "comments": [
    {{
      "path": "src/example.py",
      "line": 42,
      "body": "The comment body in markdown format (see rules below)"
    }}
  ]
}}

## Comment Body Format
Each comment body MUST follow this structure:

1. Start with a severity badge on its own line — one of:
   `![critical](https://www.gstatic.com/codereviewagent/critical.svg)`
   `![medium](https://www.gstatic.com/codereviewagent/medium-priority.svg)`
   `![low](https://www.gstatic.com/codereviewagent/low.svg)`

2. Then a blank line followed by a detailed explanation (2-5 sentences) of the issue or praise, in character as Julian.

3. If you have a specific code fix, include a GitHub suggestion block:
   ````
   ```suggestion
   the corrected line(s) of code
   ```
   ````
   The suggestion block replaces the line you're commenting on, so write the corrected version of that line.

## Comment Rules
- "path" must EXACTLY match a file path from the changed lines below
- "line" must EXACTLY match a line number (the number after L) from the changed lines below
- Write as many comments as needed to cover all significant issues — do not limit yourself
- Focus on: security issues, bugs, pattern violations, code quality, and praise for good patterns
- Every comment must be in character as Julian
"""

    user_prompt = f"""Review this pull request and provide inline comments on specific lines.

{structured_diff}

Full diff for additional context:
```diff
{diff[:30000]}
```
"""

    raw = await _call_gemini(system_prompt, user_prompt)
    return _parse_review_response(raw)


async def generate_reply(comment: str, patterns: str | None) -> str:
    """Generate a Julian-style reply to a mention."""
    pattern_ref = patterns or DEFAULT_PATTERNS

    system_prompt = f"""
{DEFAULT_PERSONA}

## Pattern Reference
{pattern_ref}

## Your Task
Reply to this comment as Julian. If they're asking about code patterns, reference the established patterns. Stay in character.
"""

    user_prompt = f"Reply to this comment:\n\n{comment}"

    return await _call_gemini(system_prompt, user_prompt)


async def _call_gemini(system_prompt: str, user_prompt: str) -> str:
    """Call Gemini API via Vertex AI."""
    creds = _get_credentials()
    project_id = _get_project_id()

    # Use global endpoint for Gemini 3 Pro
    url = f"https://aiplatform.googleapis.com/v1beta1/projects/{project_id}/locations/global/publishers/google/models/gemini-3-pro-preview:generateContent"

    headers = {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json",
    }

    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": user_prompt}]},
        ],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 8192,
        },
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                logger.error("[gemini] API error: %d %s", resp.status, text)
                return ""

            data = await resp.json()
            try:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError) as e:
                logger.error("[gemini] Unexpected response format: %s", e)
                return ""


def _parse_review_response(raw: str) -> dict:
    """Parse Gemini's JSON response into a structured review dict.

    Falls back to a summary-only review if JSON parsing fails.
    """
    if not raw:
        return {"summary": "", "comments": []}

    # Strip markdown code fences if Gemini wrapped the JSON
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict) and "summary" in parsed:
            comments = parsed.get("comments", [])
            # Validate comment structure
            valid_comments = []
            for c in comments:
                if (
                    isinstance(c, dict)
                    and isinstance(c.get("path"), str)
                    and isinstance(c.get("line"), int)
                    and isinstance(c.get("body"), str)
                ):
                    valid_comments.append(c)
                else:
                    logger.warning("[gemini] Dropping malformed comment: %s", c)
            return {"summary": parsed["summary"], "comments": valid_comments}
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("[gemini] Failed to parse JSON review, falling back to raw text: %s", e)

    return {"summary": raw, "comments": []}
