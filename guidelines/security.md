# Security Guide

OWASP-informed, cross-language security checklist. Julian enforces these on every PR.

---

## Input Validation

Validate at system boundaries. Trust internal code.

- **Pydantic models** at API boundaries (Python)
- **Typed interfaces** at API boundaries (TypeScript)
- Never trust raw user input — validate, sanitize, constrain
- Allowlist over denylist for input filtering

```python
# Correct — validated at boundary
class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")

# Wrong — raw dict drilling
username = data.get("username", "")  # no validation
```

## Secrets Management

### Never in Code

- No hardcoded secrets, tokens, or API keys
- No secrets in environment variables referenced directly in code
- Use file-based secrets (`/secrets/`) or secret managers

```python
# Correct — file-based
class Settings(BaseSettings):
    api_key: str
    model_config = {"env_prefix": "SERVICE_"}

# Wrong — hardcoded
API_KEY = "sk-abc123..."

# Wrong — scattered os.environ
key = os.environ.get("API_KEY")
```

### Secret Files

- Secrets directory: `/secrets/` with restrictive permissions (0600)
- One secret per file
- Never log secret values

## Authentication

### JWT

- Validate signature, issuer, audience, and expiry
- Use asymmetric keys (RS256) for service-to-service
- Clock skew tolerance (60 seconds)
- Short-lived tokens (10 minutes for JWTs)

### HMAC Verification

- Constant-time comparison (`hmac.compare_digest`)
- Verify before processing any payload
- Reject missing or malformed signatures immediately

```python
# Correct — constant-time comparison
expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
return hmac.compare_digest(f"sha256={expected}", signature)

# Wrong — timing attack vulnerable
return f"sha256={expected}" == signature
```

### Token Caching

- Cache tokens with TTL shorter than actual expiry
- Example: 50-minute cache for 1-hour tokens
- Invalidate on auth failure

## Injection Prevention

### SQL

- Parameterized queries only — never string interpolation
- Use ORM query builders

```python
# Correct
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))

# Wrong — SQL injection
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
```

### Command Injection

- Never pass user input to shell commands
- Use `subprocess.run()` with argument lists, not shell strings
- Avoid `shell=True`

```python
# Correct
subprocess.run(["git", "clone", repo_url], check=True)

# Wrong — shell injection
subprocess.run(f"git clone {repo_url}", shell=True)
```

### Path Traversal

- Validate file paths against a base directory
- Reject `..` components
- Use `pathlib.Path.resolve()` and check prefix

## Dependencies

- Pin exact versions in lock files
- Audit dependencies regularly
- Minimal dependency surface — fewer deps = smaller attack surface
- Review transitive dependencies

## OWASP Top 10 Mapping

| OWASP Category | Code Review Check |
|---|---|
| A01 Broken Access Control | Auth checks on every endpoint, role validation |
| A02 Cryptographic Failures | No hardcoded secrets, proper key management |
| A03 Injection | Parameterized queries, no shell interpolation |
| A04 Insecure Design | Typed models at boundaries, error hierarchy |
| A05 Security Misconfiguration | No debug in prod, restrictive defaults |
| A06 Vulnerable Components | Pinned deps, regular audits |
| A07 Auth Failures | JWT validation, HMAC verification, token expiry |
| A08 Data Integrity Failures | Signature verification, input validation |
| A09 Logging Failures | Structured logging, no secrets in logs |
| A10 SSRF | Validate URLs, restrict outbound requests |

## Logging Safety

- Never log secrets, tokens, API keys, or passwords
- Never log PII (emails, names) at INFO level
- Sanitize error messages before logging
- Use structured logging with context fields

```python
# Correct
log.info("Token refreshed for installation %d", installation_id)

# Wrong — logs the actual token
log.info("Got token: %s", token)
```

## Code Review Checklist

1. No hardcoded secrets or tokens
2. Input validated at system boundaries with typed models
3. HMAC/JWT signatures verified before processing
4. Constant-time comparison for secrets
5. Parameterized queries — no string interpolation
6. No `shell=True` or user input in commands
7. Dependencies pinned and audited
8. No secrets or PII in log output
9. Auth checks on every endpoint
10. File paths validated against base directory
