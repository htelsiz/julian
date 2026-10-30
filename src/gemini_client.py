"""Gemini API client for Julian pattern enforcement reviews.

Class-based client following kinoagent patterns: from_env(), typed methods.
Fixes the double-serialization bug (json=json.dumps(payload)) from the old code.
"""

import json
import logging
import re

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from src.config import GcpSettings, GeminiSettings

log = logging.getLogger(__name__)

# Julian's persona — always used, never overridden by reviewed repos
JULIAN_PERSONA = """
You ARE Julian from Trailer Park Boys — calm, measured, always have a plan and a drink in hand. You enforce coding patterns and conventions and keep the operation running clean.

## Voice
- Calm, in control, a little weary of repeat offenders. Firm but not hostile.
- Stay in character, but keep it SHORT: a touch of Julian flavor, then the point. No rambling.
- CRITICAL — VARY YOUR PHRASING EVERY TIME. Do NOT use a stock opening or signature line.
  Never say "Alright boys, let me take a sip of my drink and look at what we've got here",
  and never narrate "*sips rum and coke*" or any drinking stage-direction. Those are banned.
  Rotate naturally and differently each comment: the plan, running it clean, Bubbles' eye for
  detail, Lahey's shit-winds / drunk code, Ricky's hacks, Randy's gut, the trailer park. Never
  reuse the same reference or opener twice in one review.

## Your Focus: PATTERNS (Ricky handles bugs/security/logic — stay out of his lane)
- Established project patterns and conventions, naming, structure, DRY, consistency.
- Deviations from the coding guidelines; point to where it's done right elsewhere.
- Do NOT flag correctness, security, or runtime bugs — that's Ricky's job.

## Shorthand
- Bubbles = meticulous detail / clean defensive code
- Mr. Lahey = anti-patterns, unstable "drunk" code, the shit-winds (technical debt)
- Ricky = hacks that technically work but aren't clean
"""



class GeminiClient:
    """Vertex AI Gemini client for generating pattern enforcement reviews."""

    service_name: str = "gemini"

    def __init__(self, project_id: str, credentials: service_account.Credentials, settings: GeminiSettings) -> None:
        self._project_id = project_id
        self._credentials = credentials
        self._settings = settings
        self._client = httpx.AsyncClient(timeout=120)

    @classmethod
    def from_env(cls) -> "GeminiClient":
        gcp = GcpSettings()
        gemini = GeminiSettings()

        credentials = service_account.Credentials.from_service_account_file(
            gcp.sa_key_file,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        credentials.refresh(Request())

        return cls(project_id=gcp.project_id, credentials=credentials, settings=gemini)

    def _refresh_credentials(self) -> None:
        """Refresh GCP credentials if expired."""
        if not self._credentials.valid:
            self._credentials.refresh(Request())

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Call Gemini API via Vertex AI and return the text response."""
        self._refresh_credentials()

        url = (
            f"https://aiplatform.googleapis.com/v1beta1/projects/{self._project_id}"
            f"/locations/global/publishers/google/models/{self._settings.model}:generateContent"
        )

        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": user_prompt}]},
            ],
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {
                "temperature": self._settings.temperature,
                "maxOutputTokens": self._settings.max_output_tokens,
            },
        }

        response = await self._client.post(
            url,
            headers={
                "Authorization": f"Bearer {self._credentials.token}",
                "Content-Type": "application/json",
            },
            json=payload,  # httpx handles serialization — no json.dumps()
        )

        if response.status_code != 200:
            log.error("API error: %d %s", response.status_code, response.text[:500])
            return "Boys, something went sideways with the plan. Give me a minute to figure this out."

        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            log.error("Unexpected response format: %s", exc)
            return "The plan hit a snag, boys. Let me regroup."

    async def generate_review(
        self,
        diff: str,
        structured_diff: str,
        guidelines: str,
        pr_title: str = "",
        pr_body: str = "",
        existing_feedback: str = "",
    ) -> dict:
        """Generate a structured, line-level pattern-enforcement review.

        Returns:
            {"summary": str, "comments": [{"path": str, "line": int, "body": str}]}
        """
        system_prompt = f"""{JULIAN_PERSONA}

## Coding Guidelines
{guidelines}

## Your Task
Review this pull request for pattern and convention issues. Write DETAILED, line-level
inline comments — NOT one big blob of text. Return JSON only.

## Response Format
Respond with valid JSON only. No markdown fences. No text outside the JSON.

{{
  "summary": "1-2 sentence Julian verdict. Phrase it differently every single review.",
  "comments": [
    {{"path": "src/example.py", "line": 42, "body": "<comment body, see format below>"}}
  ]
}}

## Comment body format
1. Start with a severity badge on its own line — one of:
   `![medium](https://www.gstatic.com/codereviewagent/medium-priority.svg)`
   `![low](https://www.gstatic.com/codereviewagent/low.svg)`
   (reserve `![critical](https://www.gstatic.com/codereviewagent/critical.svg)` for a serious
   pattern violation)
2. A blank line, then 2-4 sentences in Julian's voice: name the pattern/convention issue and how
   to align it. Keep it tight.
3. If there's a concrete fix, add a GitHub suggestion block with the corrected line(s):
   ```suggestion
   corrected line here
   ```

## Rules
- "path" must EXACTLY match a file path from the changed lines below.
- "line" must EXACTLY match a line number (the number after L) from the changed lines below.
- Focus on patterns, naming, structure, DRY, convention/guideline consistency.
  Do NOT comment on bugs, security, or runtime correctness — that is Ricky's lane.
- VARY your wording across every comment and the summary; never reuse an opener or catchphrase,
  and never narrate drinking.
- Do NOT repeat anything already in the "Existing comments" section. On follow-ups, cover only
  NEW code and NEW issues.
- If there is nothing worth flagging, return an empty comments list with a brief summary.
"""

        existing_section = ""
        if existing_feedback:
            existing_section = f"""
**Existing comments on this PR (DO NOT repeat these points):**
{existing_feedback}

"""

        truncated_diff = diff[: self._settings.max_diff_chars]
        user_prompt = f"""Review this pull request and give inline, line-level pattern comments.

**Title:** {pr_title}

**Description:**
{pr_body}
{existing_section}**Changed lines by file:**
{structured_diff}

**Full diff for context:**
```diff
{truncated_diff}
```"""

        raw = await self.generate(system_prompt, user_prompt)
        return _parse_review_response(raw)

    async def generate_reply(self, comment: str, guidelines: str) -> str:
        """Generate a Julian-style reply to a mention."""
        system_prompt = f"""{JULIAN_PERSONA}

## Coding Guidelines
{guidelines}

## Your Task
Reply to this comment as Julian. If they're asking about code patterns, reference the established patterns and guidelines. Stay in character.
"""

        user_prompt = f"Reply to this comment:\n\n{comment}"

        return await self.generate(system_prompt, user_prompt)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()


def _parse_review_response(raw: str) -> dict:
    """Parse Gemini's JSON response into a structured review dict.

    Falls back to a summary-only review if JSON parsing fails, so a malformed
    model response still surfaces *something* rather than nothing.
    """
    if not raw:
        return {"summary": "", "comments": []}

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError) as exc:
        log.warning("Failed to parse JSON review, falling back to raw text: %s", exc)
        return {"summary": raw, "comments": []}

    if not (isinstance(parsed, dict) and "summary" in parsed):
        return {"summary": raw, "comments": []}

    valid_comments = []
    for c in parsed.get("comments", []):
        if (
            isinstance(c, dict)
            and isinstance(c.get("path"), str)
            and isinstance(c.get("line"), int)
            and isinstance(c.get("body"), str)
        ):
            valid_comments.append(c)
        else:
            log.warning("Dropping malformed comment: %s", c)

    return {"summary": parsed["summary"], "comments": valid_comments}
