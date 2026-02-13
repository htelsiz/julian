"""GitHub App authentication — JWT generation and installation token exchange."""

import logging
import os
import time

import aiohttp
import jwt

logger = logging.getLogger(__name__)

# Cache installation tokens (they last 1 hour, we refresh at 50 min)
_token_cache: dict[int, tuple[str, float]] = {}
_TOKEN_TTL = 50 * 60  # 50 minutes


def _get_app_id() -> str:
    """Load GitHub App ID from secrets."""
    path = os.environ.get("GITHUB_APP_ID_FILE", "/secrets/app-id")
    with open(path) as f:
        return f.read().strip()


def _get_private_key() -> str:
    """Load GitHub App private key from secrets."""
    path = os.environ.get("GITHUB_PRIVATE_KEY_FILE", "/secrets/private-key.pem")
    with open(path) as f:
        return f.read()


def _generate_jwt() -> str:
    """Generate a JWT for GitHub App authentication."""
    app_id = _get_app_id()
    private_key = _get_private_key()

    now = int(time.time())
    payload = {
        "iat": now - 60,  # Issued 60 seconds ago (clock skew tolerance)
        "exp": now + 600,  # Expires in 10 minutes
        "iss": app_id,
    }

    return jwt.encode(payload, private_key, algorithm="RS256")


async def get_installation_token(installation_id: int) -> str:
    """Get an installation access token, using cache when valid."""
    # Check cache
    if installation_id in _token_cache:
        token, expires_at = _token_cache[installation_id]
        if time.time() < expires_at:
            return token

    # Generate new token
    app_jwt = _generate_jwt()
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {app_jwt}",
        "Accept": "application/vnd.github.v3+json",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers) as resp:
            if resp.status != 201:
                text = await resp.text()
                logger.error("[auth] Failed to get installation token: %d %s", resp.status, text)
                raise RuntimeError(f"GitHub auth failed: {resp.status}")

            data = await resp.json()
            token = data["token"]

            # Cache with TTL
            _token_cache[installation_id] = (token, time.time() + _TOKEN_TTL)
            logger.info("[auth] Generated new installation token for %d", installation_id)

            return token
