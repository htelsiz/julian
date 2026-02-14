"""Julian GitHub App — FastAPI webhook endpoint with signature verification."""

import collections
import hashlib
import hmac
import logging
import traceback

from fastapi import FastAPI, Header, HTTPException, Request

from src.config import GithubSettings, JulianSettings
from src.webhook_handler import handle_webhook

settings = JulianSettings()

# In-memory ring buffer for debug logs
_log_buffer: collections.deque = collections.deque(maxlen=settings.log_buffer_size)


class _BufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        _log_buffer.append(self.format(record))


logging.basicConfig(level=getattr(logging, settings.log_level))
_bh = _BufferHandler()
_bh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logging.getLogger().addHandler(_bh)

log = logging.getLogger(__name__)

app = FastAPI(title="Julian", description="Trailer Park Boys Pattern Enforcer")

_webhook_secret: bytes | None = None


def _get_webhook_secret() -> bytes:
    global _webhook_secret
    if _webhook_secret is None:
        gh = GithubSettings()
        _webhook_secret = gh.webhook_secret.encode()
    return _webhook_secret


def _verify_signature(payload: bytes, signature: str) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature."""
    if not signature or not signature.startswith("sha256="):
        return False
    expected = hmac.new(
        _get_webhook_secret(), payload, hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "persona": "julian"}


@app.get("/debug/logs")
async def debug_logs() -> dict[str, list]:
    return {"logs": list(_log_buffer)}


@app.post("/webhook")
async def webhook(
    request: Request,
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None),
) -> dict[str, str]:
    payload = await request.body()

    if not _verify_signature(payload, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    event_data = await request.json()
    log.info("Received event: %s, action: %s", x_github_event, event_data.get("action"))

    try:
        await handle_webhook(x_github_event, event_data)
    except Exception:
        log.error("Handler failed:\n%s", traceback.format_exc())
        raise

    return {"status": "ok"}
