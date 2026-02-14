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

    system_prompt = f"""
{DEFAULT_PERSONA}

## Pattern Reference
{pattern_ref}

## Your Task
Review these code changes and provide feedback as inline comments on specific lines.
- Point out deviations from established patterns
- Suggest how to align with the patterns
- Praise code that follows patterns well
- Stay in character as Julian throughout

You MUST respond with valid JSON only, no markdown fences, no extra text.
Use this exact format:
{{
  "summary": "Brief overall assessment of the PR in character as Julian. Start with: Alright boys, let me take a look at what we've got here...",
  "comments": [
    {{"path": "src/example.py", "line": 42, "body": "Your inline comment in character as Julian"}}
  ]
}}

Rules for comments:
- "path" must exactly match one of the file paths shown below
- "line" must exactly match one of the line numbers (L__) shown below for that file
- "body" should be a focused comment about that specific line/change, in character
- Include 1-5 comments targeting the most important issues or praise-worthy patterns
- If the code looks clean, include at least one comment praising a good pattern
"""

    user_prompt = f"""Review these changes and provide inline comments.

{structured_diff}

Full diff for context:
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
            "maxOutputTokens": 4096,
        },
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                logger.error("[gemini] API error: %d %s", resp.status, text)
                return "Boys, something went sideways with the plan. Give me a minute to figure this out."

            data = await resp.json()
            try:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError) as e:
                logger.error("[gemini] Unexpected response format: %s", e)
                return "The plan hit a snag, boys. Let me regroup."


def _parse_review_response(raw: str) -> dict:
    """Parse Gemini's JSON response into a structured review dict.

    Falls back to a summary-only review if JSON parsing fails.
    """
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
