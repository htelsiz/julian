# Julian

Pattern enforcement GitHub App that reviews PRs as Julian from Trailer Park Boys. Powered by Gemini 3 Pro via Vertex AI.

Julian enforces coding patterns and style consistency across your repos. Technical advice is correct — the delivery is Julian: calm, collected, always with a plan (and his rum and coke).

## What Julian Does

Unlike Ricky (who provides general code reviews), Julian focuses on **pattern enforcement**:

- Checks code against centralized coding patterns
- Flags deviations from established conventions
- References where patterns are done correctly in other projects
- Enforces consistency across your codebase

## Architecture

```
GitHub PR Event
  → Tailscale Funnel (public HTTPS)
  → NixOS MicroVM (QEMU via microvm.nix)
  → FastAPI webhook handler (uvicorn :8000)
  → Gemini 3 Pro Preview (Vertex AI)
  → GitHub API (posts review as Julian app)
```

## Patterns Julian Enforces

Julian's pattern knowledge comes from `.gemini/patterns.md` in each repo. The centralized patterns include:

### Python
- Modern type hints (Python 3.10+: `list[]` not `List[]`, `| None` not `Optional`)
- Pydantic models for type safety
- Builder pattern, factory functions
- Async-first with proper `await`
- Logging with prefixes like `[module_name]`

### Swift
- Service pattern with `@MainActor final class`
- `os.Logger` not `print()`
- Theme colors from `GlyxTheme`
- async/await, not completion handlers

### Go
- Table-driven tests
- Error wrapping with `%w`
- Accept interfaces, return concrete types
- `internal/` for private packages

### Nix
- Feature-based organization
- Module function pattern
- 2-space indentation
- Comments explain "why"

### TypeScript
- Enums over string literal unions
- snake_case for database types, camelCase for app types
- Minimal entry files
- Split files > 200-300 lines

### Universal
- DRY — no repeated code
- Feature + layer organization
- Error handling at boundaries
- Comments explain WHY not WHAT
- Tests near the code

## Webhook Handler

| File | Purpose |
|------|---------|
| `src/main.py` | FastAPI app, webhook endpoint, signature verification |
| `src/github_auth.py` | GitHub App JWT auth, installation token caching |
| `src/webhook_handler.py` | Event routing, diff/file fetching, review posting |
| `src/gemini_client.py` | Vertex AI client, Julian persona prompts |

### Events Handled

- **`pull_request`** (`opened`, `synchronize`, `reopened`): Fetches diff, loads patterns, generates pattern-focused review
- **`issue_comment`** (`created`): If comment contains `@julian`, generates in-character reply

### Endpoints

- `GET /health` — health check
- `GET /debug/logs` — recent logs (last 200 entries)
- `POST /webhook` — GitHub webhook receiver (HMAC-verified)

## Julian's Persona

The persona lives in `.gemini/styleguide.md`. Julian:

- Stays calm and measured
- References "the plan" and running things "clean"
- Uses TPB character references:
  - Bubbles = meticulous detail
  - Mr. Lahey = anti-patterns, drunk code
  - Cyrus = hostile hacks
  - The shit-winds = incoming tech debt

## Adding Julian to a Repo

1. Install the Julian GitHub App on the repo
2. Add `.gemini/patterns.md` with your coding patterns (or use defaults)
3. Optionally add `.gemini/styleguide.md` to customize Julian's persona
4. Open a PR — Julian will enforce patterns automatically
5. Mention `@julian` in comments for pattern guidance

## Setup

Same infrastructure as Ricky. See [ricky/README.md](../ricky/README.md) for:

1. GitHub App creation
2. GCP service account setup
3. NixOS MicroVM configuration
4. Tailscale Funnel setup
5. Secrets management

Use a separate GitHub App (different app ID, webhook secret, etc.) so Julian has his own identity.

## Ricky vs Julian

| Aspect | Ricky | Julian |
|--------|-------|--------|
| Focus | General code review | Pattern enforcement |
| Personality | Chaotic, butchers sayings | Calm, has a plan |
| Reviews | Catches bugs, suggests fixes | Enforces conventions |
| When to use | Any PR | PRs in pattern-enforced repos |

Run both on the same repo for comprehensive reviews: Ricky catches bugs, Julian enforces patterns.
