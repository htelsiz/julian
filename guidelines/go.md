# Go Style Guide

Derived from the skitz project (Charm stack TUI). Julian enforces these patterns on all Go PRs.

---

## Formatting

Run `gofmt` before committing. Non-negotiable.

### Imports

stdlib, then external, then internal — blank lines between groups.

```go
import (
    "context"
    "fmt"

    tea "github.com/charmbracelet/bubbletea"
    "github.com/charmbracelet/lipgloss"

    "github.com/org/project/internal/config"
)
```

## Naming

### Packages

Short, lowercase, no underscores, match directory name.

```go
package config  // not package configManager
package mcp     // not package mcp_client
```

Don't repeat the package name in exports:

```go
func Load() Config { ... }  // config.Load() — not config.LoadConfig()
```

### Interfaces

`-er` suffix for single-method interfaces. No `I` prefix.

```go
type Reader interface { Read(p []byte) (n int, err error) }
type Storage interface { ... }  // multi-method: descriptive noun
```

### Locks

Named `lock`, never embedded.

```go
type Cache struct {
    lock sync.Mutex
    data map[string]string
}
```

## Error Handling

### Wrap with Context

Always wrap errors with `%w` to preserve the chain.

```go
if err := db.Connect(ctx); err != nil {
    return fmt.Errorf("failed to connect to database: %w", err)
}
```

### Sentinel Errors

Define sentinel errors for expected conditions.

```go
var ErrNotFound = errors.New("not found")

if errors.Is(err, ErrNotFound) {
    // handle gracefully
}
```

### Never Ignore Errors

```go
// Wrong
db.Close()

// Correct
if err := db.Close(); err != nil {
    log.Printf("failed to close db: %v", err)
}
```

## Functions

Keep functions focused — split by responsibility.

```go
func (m *model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
    switch msg := msg.(type) {
    case tea.KeyMsg:
        return m.handleKey(msg)
    case tickMsg:
        return m.handleTick(msg)
    }
    return m, nil
}
```

Accept interfaces, return concrete types:

```go
func NewClient(r io.Reader) *Client { ... }
```

## Structs

Composite literals with field names:

```go
cfg := Config{
    Name:    "default",
    Timeout: 30 * time.Second,
}
```

Zero values with `var`:

```go
var buf bytes.Buffer
var coords Point
```

## Testing

### Table-Driven Tests

One test function, multiple cases.

```go
func TestParse(t *testing.T) {
    tests := []struct {
        name    string
        input   string
        want    int
        wantErr bool
    }{
        {name: "valid", input: "42", want: 42},
        {name: "negative", input: "-1", want: -1},
        {name: "invalid", input: "abc", wantErr: true},
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := Parse(tt.input)
            if (err != nil) != tt.wantErr {
                t.Errorf("Parse(%q) error = %v, wantErr %v", tt.input, err, tt.wantErr)
                return
            }
            if got != tt.want {
                t.Errorf("Parse(%q) = %v, want %v", tt.input, got, tt.want)
            }
        })
    }
}
```

### Test Helpers

Always call `t.Helper()`.

```go
func mustLoadFixture(t *testing.T, path string) []byte {
    t.Helper()
    data, err := os.ReadFile(path)
    if err != nil {
        t.Fatalf("failed to load fixture %s: %v", path, err)
    }
    return data
}
```

## Concurrency

### Channel Direction

Specify direction in function signatures.

```go
func producer(out chan<- int) { ... }
func consumer(in <-chan int) { ... }
```

### Goroutines Must Be Cancellable

```go
func watch(ctx context.Context) {
    go func() {
        for {
            select {
            case <-ctx.Done():
                return
            case event := <-events:
                handle(event)
            }
        }
    }()
}
```

## Package Organization

```
myapp/
├── cmd/
│   └── myapp/
│       └── main.go
├── internal/           # Private packages
│   ├── app/
│   ├── config/
│   └── mcp/
├── pkg/                # Public packages (if any)
└── go.mod
```

- `internal/` for private packages — enforced by the compiler
- Group related types in the same file
- Split large packages by domain (`client.go`, `server.go`, `types.go`)
- Name packages by function, not `util` or `helpers`

## Patterns

### Elm Architecture

BubbleTea's Init/Update/View pattern for TUI apps — state is immutable, updates return new state + commands.

### Map-Based Dispatch

Prefer maps over switch chains for action routing and metadata lookup. Declarative, easy to extend.

```go
// Correct — map-based dispatch, declarative
var handlers = map[string]func(ctx context.Context, msg tea.Msg) tea.Cmd{
    "quit":    handleQuit,
    "refresh": handleRefresh,
    "deploy":  handleDeploy,
    "review":  handleReview,
}

func dispatch(ctx context.Context, action string, msg tea.Msg) tea.Cmd {
    handler, ok := handlers[action]
    if !ok {
        return nil
    }
    return handler(ctx, msg)
}

// Wrong — long switch chain, imperative
func dispatch(ctx context.Context, action string, msg tea.Msg) tea.Cmd {
    switch action {
    case "quit":
        return handleQuit(ctx, msg)
    case "refresh":
        return handleRefresh(ctx, msg)
    case "deploy":
        return handleDeploy(ctx, msg)
    case "review":
        return handleReview(ctx, msg)
    default:
        return nil
    }
}
```

### Other Patterns

- **Context propagation**: Pass `context.Context` as first parameter
- **Functional options**: Use `Option` pattern for configurable constructors

## Code Review Checklist

1. **Early returns on error** — no nested `if err == nil` success paths
2. **Map-based dispatch** where applicable — no long switch chains
3. `gofmt` applied
4. Errors wrapped with `%w` context
5. Table-driven tests for functions with multiple cases
6. Channel direction specified in signatures
7. No package name repetition in exports
8. `internal/` for private packages
9. Goroutines cancellable via context
10. Interfaces accepted, concrete types returned
11. No ignored errors
12. Test helpers call `t.Helper()`
