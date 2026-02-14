"""GitHub API client with App JWT authentication.

Merges the old github_auth.py and inline aiohttp calls into a single client
class following the kinoagent pattern: from_env(), _handle_response(), typed methods.
"""

import base64
import logging
import time

import httpx
import jwt

from src.config import GithubSettings
from src.errors import ApiResponseError, AuthenticationError, NotFoundError

log = logging.getLogger(__name__)

# Installation token cache: {installation_id: (token, expires_at)}
_token_cache: dict[int, tuple[str, float]] = {}
_TOKEN_TTL = 50 * 60  # 50 minutes (tokens last 1 hour)


class GitHubClient:
    """GitHub API client with App authentication."""

    service_name: str = "github"

    def __init__(self, app_id: str, private_key: str) -> None:
        self._app_id = app_id
        self._private_key = private_key
        self._client = httpx.AsyncClient(
            base_url="https://api.github.com",
            timeout=30,
        )

    @classmethod
    def from_env(cls) -> "GitHubClient":
        settings = GithubSettings()
        return cls(app_id=settings.app_id, private_key=settings.private_key)

    def _generate_jwt(self) -> str:
        """Generate a short-lived JWT for GitHub App authentication."""
        now = int(time.time())
        payload = {
            "iat": now - 60,   # 60s in the past for clock skew
            "exp": now + 600,  # 10 minute expiry
            "iss": self._app_id,
        }
        return jwt.encode(payload, self._private_key, algorithm="RS256")

    async def _get_installation_token(self, installation_id: int) -> str:
        """Get an installation access token, caching for reuse."""
        if installation_id in _token_cache:
            token, expires_at = _token_cache[installation_id]
            if time.time() < expires_at:
                return token

        app_jwt = self._generate_jwt()
        response = await self._client.post(
            f"/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        if response.status_code != 201:
            raise AuthenticationError(
                self.service_name,
                f"failed to get installation token: HTTP {response.status_code}",
            )

        data = response.json()
        token = data["token"]
        _token_cache[installation_id] = (token, time.time() + _TOKEN_TTL)
        log.info("Generated new installation token for %d", installation_id)
        return token

    def _handle_response(self, response: httpx.Response) -> None:
        """Raise typed errors for non-success responses."""
        if response.status_code == 401:
            raise AuthenticationError(self.service_name, "invalid credentials")
        if response.status_code == 404:
            raise NotFoundError(self.service_name, "resource not found")
        if response.status_code >= 400:
            raise ApiResponseError(self.service_name, response.status_code, response.text)

    def _auth_headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        }

    async def fetch_diff(self, installation_id: int, owner: str, repo: str, pr_number: int) -> str:
        """Fetch PR diff from GitHub API."""
        token = await self._get_installation_token(installation_id)
        response = await self._client.get(
            f"/repos/{owner}/{repo}/pulls/{pr_number}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3.diff",
            },
        )
        if response.status_code != 200:
            log.error("Failed to fetch diff: %d", response.status_code)
            return ""
        return response.text

    async def fetch_file_raw(
        self, installation_id: int, owner: str, repo: str, path: str, ref: str,
    ) -> str | None:
        """Fetch file contents from a repo. Returns None if not found."""
        token = await self._get_installation_token(installation_id)
        response = await self._client.get(
            f"/repos/{owner}/{repo}/contents/{path}",
            params={"ref": ref},
            headers=self._auth_headers(token),
        )
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            log.warning("Failed to fetch %s: %d", path, response.status_code)
            return None

        data = response.json()
        content = data.get("content", "")
        return base64.b64decode(content).decode("utf-8")

    async def post_review(
        self, installation_id: int, owner: str, repo: str, pr_number: int, body: str,
    ) -> None:
        """Post a PR review comment."""
        token = await self._get_installation_token(installation_id)
        response = await self._client.post(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
            headers=self._auth_headers(token),
            json={"body": body, "event": "COMMENT"},
        )
        if response.status_code not in (200, 201):
            log.error("Failed to post review: %d %s", response.status_code, response.text)

    async def post_issue_comment(
        self, installation_id: int, owner: str, repo: str, issue_number: int, body: str,
    ) -> None:
        """Post an issue/PR comment."""
        token = await self._get_installation_token(installation_id)
        response = await self._client.post(
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            headers=self._auth_headers(token),
            json={"body": body},
        )
        if response.status_code not in (200, 201):
            log.error("Failed to post comment: %d %s", response.status_code, response.text)

    async def _fetch_paginated(
        self, installation_id: int, path: str, max_pages: int = 3,
    ) -> list[dict]:
        """Fetch a paginated list endpoint, returning up to max_pages of results."""
        token = await self._get_installation_token(installation_id)
        all_items: list[dict] = []
        per_page = 100
        for page in range(1, max_pages + 1):
            response = await self._client.get(
                path,
                headers=self._auth_headers(token),
                params={"per_page": per_page, "page": page},
            )
            if response.status_code != 200:
                log.warning("Failed to fetch %s: %d", path, response.status_code)
                break
            items = response.json()
            all_items.extend(items)
            if len(items) < per_page:
                break
        return all_items

    async def get_pr_comments(
        self, installation_id: int, owner: str, repo: str, pr_number: int,
    ) -> list[dict]:
        """Fetch inline review comments on a PR."""
        return await self._fetch_paginated(
            installation_id, f"/repos/{owner}/{repo}/pulls/{pr_number}/comments",
        )

    async def get_pr_reviews(
        self, installation_id: int, owner: str, repo: str, pr_number: int,
    ) -> list[dict]:
        """Fetch top-level reviews on a PR."""
        return await self._fetch_paginated(
            installation_id, f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
        )

    async def get_issue_comments(
        self, installation_id: int, owner: str, repo: str, issue_number: int,
    ) -> list[dict]:
        """Fetch issue-level comments on a PR/issue."""
        return await self._fetch_paginated(
            installation_id, f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
