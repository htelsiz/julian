# Python Style Guide

Synthesized from kinoagent and layerstep coding standards. Julian enforces these patterns on all Python PRs.

---

## Type Safety

Use Python 3.10+ type syntax everywhere. No `typing` imports for builtins.

```python
# Correct
def process(items: list[str], config: dict[str, Any] | None = None) -> bool: ...

# Wrong — old-style typing imports
from typing import List, Optional, Dict
def process(items: List[str], config: Optional[Dict[str, Any]] = None) -> bool: ...
```

- Return types on every function
- `X | None` not `Optional[X]`
- `list[str]` not `List[str]`
- `dict[str, int]` not `Dict[str, int]`
- Use `Any` sparingly — prefer concrete types

## Pydantic Everywhere

BaseModel for data, BaseSettings for config. No raw dicts for structured data.

### Configuration

```python
from pydantic_settings import BaseSettings

class ServiceSettings(BaseSettings):
    url: str = "http://localhost:8080"
    api_key: str

    model_config = {"env_prefix": "SERVICE_"}
```

- Every service gets its own settings class with `env_prefix`
- Settings loaded lazily via `from_env()` on the client
- Never scatter `os.environ.get()` across modules

### Data Models

```python
from pydantic import BaseModel, Field, field_validator, model_validator

class WebhookContext(BaseModel):
    owner: str
    repo_name: str
    pr_number: int
    installation_id: int

    @classmethod
    def from_webhook(cls, data: dict) -> "WebhookContext":
        """Parse raw GitHub webhook payload into typed context."""
        ...
```

- `model_validator` for flattening nested structures
- `Field(default_factory=list)` not mutable defaults
- `field_validator` for custom validation logic

## Client Pattern

Every external service gets a client class. No bare functions with `aiohttp.ClientSession()` inline.

```python
class ServiceClient:
    service_name: str = "myservice"

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    @classmethod
    def from_env(cls) -> "ServiceClient":
        settings = ServiceSettings()
        return cls(base_url=settings.url, api_key=settings.api_key)

    async def _handle_response(self, response: httpx.Response) -> None:
        if response.status_code == 401:
            raise AuthenticationError(self.service_name, "invalid credentials")
        if response.status_code >= 400:
            raise ApiResponseError(self.service_name, response.status_code, response.text)
```

- `from_env()` classmethod creates instance from BaseSettings
- `_handle_response()` raises typed errors
- Use `httpx.AsyncClient` — not `aiohttp`

### Response Parsing

Parse API responses into Pydantic models at the client layer. Don't return raw dicts.

```python
async def fetch_user(self, user_id: int) -> User:
    response = await self._client.get(f"/users/{user_id}")
    self._handle_response(response)
    return User.model_validate(response.json())

async def list_items(self) -> list[Item]:
    response = await self._client.get("/items")
    self._handle_response(response)
    return [Item.model_validate(i) for i in response.json()]
```

- `model_validate()` on response data — typed from the boundary
- Client methods return typed models, not `dict` or `Any`
- Parse at the client, not in the caller

## Error Hierarchy

Typed exceptions with service context. No bare `RuntimeError` or `Exception`.

```python
class AppError(Exception):
    """Base for all app errors."""

class ServiceError(AppError):
    def __init__(self, service: str, message: str) -> None:
        self.service = service
        super().__init__(f"{service}: {message}")

class ApiResponseError(ServiceError):
    def __init__(self, service: str, status_code: int, body: str = "") -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(service, f"HTTP {status_code}: {body[:200]}")
```

## Async

- `async/await` for all I/O (network, disk, database)
- `sync` for CPU-bound work (hashing, parsing)
- `asyncio.gather()` for parallel independent operations
- `asyncio.Semaphore` for rate limiting

```python
# Parallel fetches
results = await asyncio.gather(
    client.fetch("/a"),
    client.fetch("/b"),
)
```

## Logging

```python
import logging

log = logging.getLogger(__name__)

# Lazy formatting — only evaluated if the level is enabled
log.info("Processing PR #%d in %s/%s", pr_number, owner, repo)
log.error("API call failed: %s", error)
```

- `log = logging.getLogger(__name__)` — not `logger`, not custom names
- Lazy `%s` formatting — not f-strings in log calls
- No `[prefix]` tags — `__name__` provides the module context
- `exc_info=True` on error logs when you need the traceback

## Imports

```python
# stdlib
import asyncio
import logging
from pathlib import Path

# third-party
import httpx
from pydantic import BaseModel

# local
from myapp.config import Settings
from myapp.errors import ServiceError
```

- Always at the top of the file — no inline imports
- Absolute imports — no relative imports except within a package
- stdlib > third-party > local, separated by blank lines

## Code Organization

- Private helpers prefixed with `_`
- Public API at the top, helpers below
- One responsibility per module
- Split files over 300 lines

```python
# Public API
async def handle_webhook(event: str, data: dict) -> None:
    ctx = WebhookContext.from_webhook(data)
    await _handle_pr_review(ctx)

# Private helpers
async def _handle_pr_review(ctx: WebhookContext) -> None:
    ...
```

## Anti-Patterns

- **Bare `except:`** — always catch specific exceptions
- **Defensive nesting** — nested try/except/if chains hide bugs
- **`os.environ` sprawl** — use BaseSettings, not scattered `os.environ.get()`
- **Module-level singletons** — use `from_env()` factory pattern
- **Backwards-compat shims** — delete unused code, don't deprecate
- **`json=json.dumps(payload)`** — double serialization; `json=` already serializes
- **Inline `aiohttp.ClientSession()`** — use a client class with connection reuse
- **Missing return types** — every function needs a return type annotation

## Testing

```python
import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def mock_client() -> AsyncMock:
    return AsyncMock(spec=httpx.AsyncClient)

@pytest.mark.parametrize("status,expected", [
    (200, True),
    (404, False),
    (500, False),
])
def test_is_success(status: int, expected: bool) -> None:
    assert is_success(status) == expected

@pytest.mark.asyncio
async def test_fetch_user(mock_client: AsyncMock) -> None:
    result = await fetch_user(1, client=mock_client)
    assert result.id == 1
```

- pytest + fixtures for reusable setup
- `@pytest.mark.parametrize` for multiple cases
- `AsyncMock` for async dependencies
- `@pytest.mark.integration` for tests requiring external services

## Code Review Checklist

1. **Guard clauses and early returns** — flat code, no nested if/try pyramids
2. All functions have type hints (params + return)
3. Pydantic models for structured data — no raw dicts
4. Client methods return typed models via `model_validate()` — not raw dicts
5. BaseSettings for configuration — no `os.environ` sprawl
6. Client classes with `from_env()` and `_handle_response()`
7. Typed error hierarchy — no bare RuntimeError
8. Async for I/O, sync for CPU
9. `log = logging.getLogger(__name__)` with lazy formatting
10. No inline imports, no bare except, no defensive nesting
11. `ruff check .` and `ruff format .` pass
12. `mypy .` passes with strict mode
