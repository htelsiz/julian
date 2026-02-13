# Centralized Coding Patterns

This is the master reference for coding patterns across all operations. Julian uses this to enforce consistency.

---

## Python Patterns

**Source:** skills/CODESTYLE.md, bldrspec-ai/CLAUDE.md, pal-mcp-server/CLAUDE.md

### Type Hints (Python 3.10+)
```python
# CORRECT
def process(items: list[str], config: dict[str, Any] | None = None) -> bool:
    ...

# WRONG - old style
from typing import List, Optional, Dict
def process(items: List[str], config: Optional[Dict[str, Any]] = None) -> bool:
    ...
```

### Pydantic Models
```python
# Data classes use Pydantic
from pydantic import BaseModel, Field

class ProjectConfig(BaseModel):
    name: str
    version: str = Field(default="1.0.0")
    tags: list[str] = Field(default_factory=list)
```

### Builder Pattern
```python
class ReportBuilder:
    def __init__(self):
        self._title: str = ""
        self._sections: list[Section] = []

    def with_title(self, title: str) -> "ReportBuilder":
        self._title = title
        return self

    def add_section(self, section: Section) -> "ReportBuilder":
        self._sections.append(section)
        return self

    def build(self) -> Report:
        return Report(title=self._title, sections=self._sections)
```

### Factory Functions for Test Data
```python
def sample_user(
    name: str = "Test User",
    email: str = "test@example.com",
    **overrides
) -> User:
    return User(name=name, email=email, **overrides)
```

### Private Helpers
```python
def public_function():
    result = _internal_helper()
    return _format_output(result)

def _internal_helper():
    """Private - underscore prefix."""
    ...

def _format_output(data):
    """Private - underscore prefix."""
    ...
```

### Logging with Prefixes
```python
import logging
logger = logging.getLogger(__name__)

# Use prefixes for categorization
logger.info("[extraction] Starting document processing")
logger.error("[azure] Connection failed: %s", error)
logger.debug("[api] Request payload: %s", payload)
```

### Async-First
```python
# Prefer async/await
async def fetch_data(url: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

# Parallel execution
results = await asyncio.gather(
    fetch_data(url1),
    fetch_data(url2),
    fetch_data(url3),
)
```

---

## Swift Patterns

**Source:** glyx-ios/CODESTYLE.md

### Service Pattern
```swift
@MainActor
final class AuthService: ObservableObject {
    @Published private(set) var isAuthenticated = false

    func signIn(email: String, password: String) async throws {
        // Implementation
    }
}
```

### Actor Pattern (Thread Safety)
```swift
actor DataCache {
    private var cache: [String: Data] = [:]

    func get(_ key: String) -> Data? {
        cache[key]
    }

    func set(_ key: String, data: Data) {
        cache[key] = data
    }
}
```

### Logging (os.Logger, not print)
```swift
import os

private let logger = Logger(subsystem: "com.app.feature", category: "FeatureName")

func doSomething() {
    logger.info("Starting operation")
    logger.error("Failed with error: \(error.localizedDescription)")
}
```

### Theme Colors
```swift
// CORRECT - use theme
Text("Hello")
    .foregroundColor(GlyxTheme.primaryText)
    .background(GlyxTheme.background)

// WRONG - hardcoded
Text("Hello")
    .foregroundColor(.blue)
    .background(Color(hex: "#FF0000"))
```

### MARK Comments
```swift
// MARK: - Properties

private let service: AuthService

// MARK: - Lifecycle

override func viewDidLoad() {
    super.viewDidLoad()
}

// MARK: - Private Methods

private func configureUI() {
    // ...
}
```

### Async/Await (not completion handlers)
```swift
// CORRECT
func fetchUser() async throws -> User {
    let data = try await api.fetch("/user")
    return try JSONDecoder().decode(User.self, from: data)
}

// WRONG - completion handler style
func fetchUser(completion: @escaping (Result<User, Error>) -> Void) {
    // Don't do this
}
```

---

## Go Patterns

**Source:** skitz/AGENTS.md

### Table-Driven Tests
```go
func TestParse(t *testing.T) {
    tests := []struct {
        name    string
        input   string
        want    Result
        wantErr bool
    }{
        {"empty", "", Result{}, true},
        {"valid", "hello", Result{Value: "hello"}, false},
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := Parse(tt.input)
            if (err != nil) != tt.wantErr {
                t.Errorf("Parse() error = %v, wantErr %v", err, tt.wantErr)
                return
            }
            if got != tt.want {
                t.Errorf("Parse() = %v, want %v", got, tt.want)
            }
        })
    }
}
```

### Error Wrapping
```go
// CORRECT - wrap with context
if err != nil {
    return fmt.Errorf("failed to connect to database: %w", err)
}

// WRONG - losing context
if err != nil {
    return err
}
```

### Interface Acceptance
```go
// Accept interface
func Process(r io.Reader) error {
    // Can accept any Reader
}

// Return concrete type
func NewBuffer() *Buffer {
    return &Buffer{}
}
```

### Package Organization
```
myapp/
├── cmd/
│   └── myapp/
│       └── main.go
├── internal/           # Private packages
│   ├── auth/
│   └── storage/
├── pkg/                # Public packages (if any)
└── go.mod
```

### Channel Direction
```go
// Specify direction in signatures
func producer(out chan<- int) {
    out <- 42
}

func consumer(in <-chan int) {
    val := <-in
}
```

---

## Nix Patterns

**Source:** nixos-config/CODESTYLE.md, nixos-config/CLAUDE.md

### Module Function Pattern
```nix
{ config, pkgs, lib, ... }:

{
  options.services.myservice = {
    enable = lib.mkEnableOption "my service";
    port = lib.mkOption {
      type = lib.types.port;
      default = 8080;
    };
  };

  config = lib.mkIf config.services.myservice.enable {
    systemd.services.myservice = {
      # ...
    };
  };
}
```

### Feature-Based Organization
```
nixos-config/
├── modules/
│   ├── audio.nix          # By feature, not type
│   ├── networking.nix
│   ├── gaming.nix
│   └── development.nix
├── hosts/
│   ├── phoenix/           # Per-machine config
│   └── macbook/
└── flake.nix
```

### Documentation Headers
```nix
# =============================================================================
# Audio Configuration
# =============================================================================
# Pipewire setup with low-latency audio for music production.
# Includes JACK compatibility layer for DAW software.
# =============================================================================
```

### With Bindings
```nix
{ pkgs, ... }:

{
  environment.systemPackages = with pkgs; [
    git
    neovim
    ripgrep
  ];
}
```

### Shared Modules (NixOS + Darwin)
```nix
# Must work on both platforms
{ config, pkgs, lib, ... }:

{
  # Use lib.mkIf for platform-specific parts
  config = lib.mkMerge [
    {
      # Common config
    }
    (lib.mkIf pkgs.stdenv.isLinux {
      # Linux-only
    })
    (lib.mkIf pkgs.stdenv.isDarwin {
      # macOS-only
    })
  ];
}
```

---

## TypeScript Patterns

**Source:** glyx/CLAUDE.md, cozygraph/AGENTS.md

### Enums over String Literals
```typescript
// CORRECT
enum Status {
  Pending = "pending",
  Active = "active",
  Completed = "completed",
}

// WRONG
type Status = "pending" | "active" | "completed";
```

### Case Conventions
```typescript
// Database/Supabase types: snake_case
interface DbUser {
  user_id: string;
  created_at: string;
  is_active: boolean;
}

// Application types: camelCase
interface User {
  userId: string;
  createdAt: Date;
  isActive: boolean;
}
```

### Minimal Entry Files
```typescript
// main.ts - lifecycle only, no business logic
import { App } from "./app";

const app = new App();
app.onload();

export default app;
```

### File Size Limits
```
// Split files > 200-300 lines
src/
├── components/
│   ├── Button.tsx        // < 200 lines each
│   ├── Modal.tsx
│   └── Form/
│       ├── index.tsx
│       ├── FormField.tsx
│       └── validation.ts
```

---

## Universal Patterns

### DRY (Don't Repeat Yourself)
```
If you write the same code 3+ times, extract it.
If two modules do similar things, find the common pattern.
```

### Feature + Layer Organization
```
project/
├── features/
│   ├── auth/
│   │   ├── models.py
│   │   ├── services.py
│   │   └── api.py
│   └── billing/
│       ├── models.py
│       ├── services.py
│       └── api.py
└── shared/
    ├── database.py
    └── logging.py
```

### Error Handling at Boundaries
```python
# Validate at system boundaries (user input, external APIs)
@app.post("/api/users")
async def create_user(request: UserRequest):
    # Validate here - system boundary
    validated = validate_user_input(request)

    # Internal code trusts validated data
    return await user_service.create(validated)
```

### Comments Explain WHY
```python
# WRONG - explains what
# Increment counter by 1
counter += 1

# CORRECT - explains why
# Rate limit: max 100 requests per window
counter += 1
```

### Secrets Management
```python
# CORRECT - environment or file
secret = os.environ.get("API_KEY")
# or
with open("/secrets/api-key") as f:
    secret = f.read().strip()

# WRONG - hardcoded
secret = "sk-abc123..."
```

### Tests Near Code
```
src/
├── auth/
│   ├── service.py
│   └── service_test.py    # or test_service.py
├── billing/
│   ├── calculator.py
│   └── calculator_test.py
```

---

## Anti-Patterns (Lahey Code)

Things Julian watches for:

1. **Drunk imports** - importing everything, unused imports everywhere
2. **Randy code** - exposed internals, no encapsulation
3. **Cyrus hacks** - aggressive workarounds that break other things
4. **J-Roc style** - overly clever code that prioritizes flash over clarity
5. **Shit-winds brewing** - technical debt that's about to collapse
6. **Trailer park fire hazards** - security vulnerabilities, hardcoded secrets
