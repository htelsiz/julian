"""Gemini API client for Julian pattern enforcement reviews.

Class-based client following kinoagent patterns: from_env(), typed methods.
Fixes the double-serialization bug (json=json.dumps(payload)) from the old code.
"""

import logging

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from src.config import GcpSettings, GeminiSettings

log = logging.getLogger(__name__)

# Julian persona — used when the reviewed repo has no .gemini/styleguide.md
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
- Be firm but not hostile — you're running a clean operation

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
        guidelines: str,
        styleguide: str | None = None,
        patterns: str | None = None,
    ) -> str:
        """Generate a Julian-style pattern enforcement review."""
        persona = styleguide or DEFAULT_PERSONA
        pattern_ref = patterns or DEFAULT_PATTERNS

        system_prompt = f"""{persona}

## Pattern Reference
{pattern_ref}

## Coding Guidelines
{guidelines}

## Your Task
Review this PR diff for pattern violations and style inconsistencies.
- Point out deviations from established patterns and coding guidelines
- Suggest how to align with the patterns
- Praise code that follows patterns well
- Stay in character as Julian throughout

Start with: "Alright boys, let me take a look at what we've got here..."
"""

        truncated_diff = diff[: self._settings.max_diff_chars]
        user_prompt = f"""Review this diff and enforce our coding patterns:

```diff
{truncated_diff}
```"""

        return await self.generate(system_prompt, user_prompt)

    async def generate_reply(self, comment: str, guidelines: str, patterns: str | None = None) -> str:
        """Generate a Julian-style reply to a mention."""
        pattern_ref = patterns or DEFAULT_PATTERNS

        system_prompt = f"""{DEFAULT_PERSONA}

## Pattern Reference
{pattern_ref}

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
