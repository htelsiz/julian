# Universal Style Guide

Cross-cutting patterns enforced on every PR, regardless of language.

---

## Flat Code — Guard Clauses and Early Returns

Keep code flat. Maximum 2 levels of indentation inside a function. Use guard clauses to handle preconditions and errors early, then let the main logic flow at the top level.

### The Rule

Check for the failure case, handle it, and return. Don't nest the success path inside conditions.

```python
# Correct — guard clauses, flat flow
async def handle_request(data: dict) -> Response:
    if not data.get("user_id"):
        raise ValidationError("user_id required")

    if not data.get("action"):
        raise ValidationError("action required")

    user = await fetch_user(data["user_id"])
    if not user:
        return Response(status=404)

    result = await process_action(user, data["action"])
    return Response(data=result)

# Wrong — nested pyramid
async def handle_request(data: dict) -> Response:
    if data.get("user_id"):
        if data.get("action"):
            user = await fetch_user(data["user_id"])
            if user:
                result = await process_action(user, data["action"])
                return Response(data=result)
            else:
                return Response(status=404)
        else:
            raise ValidationError("action required")
    else:
        raise ValidationError("user_id required")
```

```go
// Correct — early return on error
func loadConfig(path string) (*Config, error) {
    data, err := os.ReadFile(path)
    if err != nil {
        return nil, fmt.Errorf("reading config: %w", err)
    }

    var cfg Config
    if err := json.Unmarshal(data, &cfg); err != nil {
        return nil, fmt.Errorf("parsing config: %w", err)
    }

    return &cfg, nil
}
```

```swift
// Correct — guard clauses exit early
func processPayment(amount: Decimal?, currency: String?) throws -> Receipt {
    guard let amount else { throw PaymentError.missingAmount }
    guard let currency else { throw PaymentError.missingCurrency }
    guard amount > 0 else { throw PaymentError.invalidAmount }

    let receipt = try chargeCard(amount: amount, currency: currency)
    return receipt
}
```

```typescript
// Correct — early returns, flat body
function validateUser(input: unknown): User {
  const parsed = UserSchema.safeParse(input);
  if (!parsed.success) {
    throw new ValidationError(parsed.error.message);
  }

  if (!parsed.data.isActive) {
    throw new InactiveUserError(parsed.data.id);
  }

  return parsed.data;
}
```

### Rules

- **No `else` after `return`** — the `if` handled the exit, the rest is the happy path
- **Guard clauses at the top** — validate preconditions before any business logic
- **Max 2 levels of indentation** inside any function body
- **Extract instead of nesting** — if a block needs another level, extract a helper function
- **Keep `try` blocks minimal** — only wrap the line that can throw, not 20 lines of logic

## DRY — Don't Repeat Yourself

```
If you write the same code 3+ times, extract it.
If two modules do similar things, find the common pattern.
```

- Extract repeated logic into shared helpers
- Parameterize differences, don't copy-paste
- One source of truth for constants and configuration

## Feature + Layer Organization

Group by feature, not by file type.

```
# Correct — feature-based
project/
├── auth/
│   ├── models.py
│   ├── service.py
│   └── api.py
├── billing/
│   ├── models.py
│   ├── service.py
│   └── api.py
└── shared/
    ├── database.py
    └── logging.py

# Wrong — type-based
project/
├── models/
│   ├── auth.py
│   └── billing.py
├── services/
│   ├── auth.py
│   └── billing.py
└── api/
    ├── auth.py
    └── billing.py
```

## Service Client Pattern

Every external service gets a client class. This applies across all languages. The pattern:

1. **Factory constructor** — `from_env()` / `NewFromEnv()` creates the client from config
2. **Response handler** — `_handle_response()` raises typed errors for non-success
3. **Typed methods** — each API call is a method with typed params and return
4. **Error hierarchy** — service-specific typed errors, not generic exceptions

```python
# Python — from_env() + _handle_response()
class PaymentClient:
    service_name = "payments"

    @classmethod
    def from_env(cls) -> "PaymentClient":
        settings = PaymentSettings()
        return cls(base_url=settings.url, api_key=settings.api_key)

    def _handle_response(self, response: httpx.Response) -> None:
        if response.status_code >= 400:
            raise ApiResponseError(self.service_name, response.status_code, response.text)

    async def charge(self, amount: int, currency: str) -> Receipt:
        response = await self._client.post("/charge", json={"amount": amount, "currency": currency})
        self._handle_response(response)
        return Receipt.model_validate(response.json())
```

```go
// Go — constructor + typed errors
func NewPaymentClient(cfg PaymentConfig) *PaymentClient {
    return &PaymentClient{
        baseURL: cfg.BaseURL,
        client:  &http.Client{Timeout: 30 * time.Second},
    }
}

func (c *PaymentClient) Charge(ctx context.Context, amount int, currency string) (*Receipt, error) {
    resp, err := c.client.Post(c.baseURL+"/charge", "application/json", body)
    if err != nil {
        return nil, fmt.Errorf("payment charge request: %w", err)
    }
    defer resp.Body.Close()

    if resp.StatusCode >= 400 {
        return nil, &APIError{Service: "payments", StatusCode: resp.StatusCode}
    }

    var receipt Receipt
    if err := json.NewDecoder(resp.Body).Decode(&receipt); err != nil {
        return nil, fmt.Errorf("decoding payment receipt: %w", err)
    }
    return &receipt, nil
}
```

## Error Handling at Boundaries

Validate at system edges. Trust internal code.

- **Validate**: user input, external API responses, file contents
- **Trust**: internal function calls, already-validated data
- Don't wrap every function call in try/except
- Let errors propagate naturally to the boundary handler

```python
# Correct — validate at boundary, trust internal code
@app.post("/api/users")
async def create_user(request: UserRequest):
    validated = validate_input(request)     # boundary validation
    return await user_service.create(validated)  # internal — trusted

# Wrong — defensive everywhere
async def create_user(request):
    try:
        if request:
            try:
                validated = validate_input(request)
                if validated:
                    try:
                        return await user_service.create(validated)
                    except:
                        pass
            except:
                pass
    except:
        pass
```

## Comments Explain WHY

The code shows WHAT. Comments explain WHY.

```python
# Wrong — explains what
# Increment counter by 1
counter += 1

# Correct — explains why
# Rate limit: max 100 requests per window
counter += 1

# Wrong — redundant
# Loop through items
for item in items:

# Correct — context
# Process in reverse to resolve dependencies bottom-up
for item in reversed(items):
```

## Delete, Don't Deprecate

Remove unused code. Don't maintain backwards-compatibility shims.

- No `_old_function` aliases
- No `# deprecated` comments on kept code
- No re-exports for renamed modules
- If it's unused, delete it

## Tests Near Code

Colocate test files with the code they test.

```
src/
├── auth/
│   ├── service.py
│   └── test_service.py
├── billing/
│   ├── calculator.py
│   └── test_calculator.py
```

- Tests in the same directory as the source
- Test file mirrors source file name
- Integration tests in a separate `tests/` directory if needed

## Naming

- Functions: verb phrases (`fetch_user`, `validate_input`, `handleKey`)
- Variables: noun phrases (`user_count`, `activeConnections`)
- Booleans: question form (`is_valid`, `hasPermission`, `shouldRetry`)
- Constants: UPPER_SNAKE_CASE or language convention
- No abbreviations unless universally understood (`url`, `id`, `ctx`)

## File Size

- Split files over 300 lines (200-300 for TypeScript/Swift)
- One primary responsibility per file
- Extract helpers into separate modules when a file grows

## Logging

- Use the language's standard logging — not print statements
- Structured context (module name, request ID, user ID)
- Log levels: DEBUG for diagnostics, INFO for operations, WARNING for recoverable issues, ERROR for failures
- Never log secrets, tokens, or PII

## Code Review Checklist

1. **Flat code** — guard clauses, early returns, max 2 levels of indentation
2. **No `else` after `return`** — if the guard handled it, the rest flows flat
3. No duplicated code (DRY)
4. Feature-based organization
5. Service clients use factory constructors + typed error handling
6. Validation at boundaries, trust internally
7. Comments explain WHY, not WHAT
8. No deprecated/unused code lingering
9. Tests colocated with source
10. Descriptive names — no single-letter variables outside loops
11. Files under 300 lines
12. Standard logging — no print statements
13. Consistent formatting per language standards
