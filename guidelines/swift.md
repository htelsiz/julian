# Swift Style Guide

Derived from the glyx-ios patterns. Julian enforces these patterns on all Swift PRs.

---

## Guard Clauses

Use `guard` for all preconditions. Exit early, keep the happy path flat.

```swift
// Correct — guard clauses, flat body
func processOrder(data: OrderData?) throws -> Order {
    guard let data else { throw OrderError.missingData }
    guard data.items.isEmpty == false else { throw OrderError.emptyCart }
    guard let user = try? await fetchUser(data.userId) else {
        throw OrderError.userNotFound
    }

    let total = calculateTotal(data.items)
    let order = Order(user: user, items: data.items, total: total)
    try await save(order)
    return order
}

// Wrong — nested conditionals
func processOrder(data: OrderData?) throws -> Order {
    if let data {
        if !data.items.isEmpty {
            if let user = try? await fetchUser(data.userId) {
                let total = calculateTotal(data.items)
                let order = Order(user: user, items: data.items, total: total)
                try await save(order)
                return order
            } else {
                throw OrderError.userNotFound
            }
        } else {
            throw OrderError.emptyCart
        }
    } else {
        throw OrderError.missingData
    }
}
```

- `guard let` for optional unwrapping — exits the scope on failure
- `guard` conditions at the top of the function — before any business logic
- Never nest the success path inside `if let` when `guard let` works
- `else` block of a `guard` must exit (`return`, `throw`, `continue`, `break`)

## Concurrency

### @MainActor Services

Observable services run on the main actor.

```swift
@MainActor
final class AuthService: ObservableObject {
    @Published private(set) var isAuthenticated = false

    func signIn(email: String, password: String) async throws {
        // Implementation
    }
}
```

- `@MainActor` on service classes that publish to the UI
- `final class` — don't design for inheritance unless needed
- `private(set)` on published properties — control mutation

### Actor Pattern

Use actors for thread-safe shared state.

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

### async/await

Always use structured concurrency. No completion handlers.

```swift
// Correct
func fetchUser() async throws -> User {
    let data = try await api.fetch("/user")
    return try JSONDecoder().decode(User.self, from: data)
}

// Wrong — completion handler style
func fetchUser(completion: @escaping (Result<User, Error>) -> Void) {
    // Don't do this
}
```

## Logging

Use `os.Logger`, never `print()`.

```swift
import os

private let logger = Logger(subsystem: "com.app.feature", category: "FeatureName")

func doSomething() {
    logger.info("Starting operation")
    logger.error("Failed with error: \(error.localizedDescription)")
}
```

## Theming

Use theme constants. No hardcoded colors.

```swift
// Correct — use theme
Text("Hello")
    .foregroundColor(GlyxTheme.primaryText)
    .background(GlyxTheme.background)

// Wrong — hardcoded
Text("Hello")
    .foregroundColor(.blue)
    .background(Color(hex: "#FF0000"))
```

## Code Organization

### MARK Comments

Organize files with MARK sections.

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

### File Structure

- One primary type per file
- Extensions in the same file or a `+Extension.swift` file
- Keep files under 300 lines — split if larger

## Access Control

- Default to `private` — expose only what's needed
- `private(set)` for read-only published properties
- `internal` (default) for module-internal types
- `public` only for framework APIs

## Error Handling

```swift
// Typed errors
enum NetworkError: Error {
    case unauthorized
    case notFound
    case serverError(statusCode: Int)
}

// Explicit handling
do {
    let user = try await fetchUser()
} catch NetworkError.unauthorized {
    // handle auth failure
} catch {
    logger.error("Unexpected error: \(error)")
}
```

## Code Review Checklist

1. **`guard` clauses for preconditions** — no nested `if let` pyramids
2. `@MainActor` on UI-publishing service classes
3. `os.Logger` — no `print()` statements
4. Theme constants — no hardcoded colors
5. `async/await` — no completion handlers
6. MARK comments for file organization
7. `private` by default, expose intentionally
8. Actors for shared mutable state
9. `final class` unless inheritance is designed
10. Structured concurrency with task groups where appropriate
11. Error types are specific and descriptive
