# TypeScript Style Guide

Derived from the glyx and cozygraph patterns. Julian enforces these patterns on all TypeScript/JavaScript PRs.

---

## Type Safety

### Enums Over String Unions

Use TypeScript enums for discrete value sets.

```typescript
// Correct
enum Status {
  Pending = "pending",
  Active = "active",
  Completed = "completed",
}

// Wrong — string literal union
type Status = "pending" | "active" | "completed";
```

### Strict Mode

Enable `strict: true` in `tsconfig.json`. No `any` without justification.

### Runtime Validation at Boundaries

Use Zod (or equivalent) for runtime validation of external data. TypeScript types vanish at runtime — raw API responses, form data, and webhook payloads need schema validation.

```typescript
import { z } from "zod";

// Define schema — single source of truth for shape + validation
const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  role: z.enum(["admin", "user", "viewer"]),
  createdAt: z.string().datetime(),
});

// Derive type from schema — no manual interface duplication
type User = z.infer<typeof UserSchema>;

// Validate at boundary
function parseUser(raw: unknown): User {
  return UserSchema.parse(raw);  // throws ZodError on invalid data
}

// Safe parse for graceful handling
function tryParseUser(raw: unknown): User | null {
  const result = UserSchema.safeParse(raw);
  if (!result.success) {
    logger.warn("Invalid user data: %s", result.error.message);
    return null;
  }
  return result.data;
}
```

- Zod schemas at every system boundary (API responses, webhooks, form input)
- Derive TypeScript types from schemas with `z.infer<>` — don't duplicate
- `parse()` for mandatory validation, `safeParse()` for graceful handling
- No manual `as` casts on external data — validate first

## Naming Conventions

### Case Conventions

Two layers, two conventions:

```typescript
// Database/Supabase types: snake_case (matches DB columns)
interface DbUser {
  user_id: string;
  created_at: string;
  is_active: boolean;
}

// Application types: camelCase (TypeScript convention)
interface User {
  userId: string;
  createdAt: Date;
  isActive: boolean;
}
```

- `snake_case` for database types — matches column names exactly
- `camelCase` for application-layer types — TypeScript convention
- Transform at the boundary between layers

### File Naming

- `camelCase.ts` for modules
- `PascalCase.tsx` for React components
- `index.ts` for barrel exports

## Code Organization

### Minimal Entry Files

Entry points handle lifecycle only — no business logic.

```typescript
// main.ts — lifecycle only
import { App } from "./app";

const app = new App();
app.onload();

export default app;
```

### File Size Limits

Split files over 200-300 lines.

```
src/
├── components/
│   ├── Button.tsx        // < 200 lines each
│   ├── Modal.tsx
│   └── Form/
│       ├── index.tsx
│       ├── FormField.tsx
│       └── validation.ts
```

### Feature Organization

Group by feature, not by file type.

```
src/
├── features/
│   ├── auth/
│   │   ├── AuthService.ts
│   │   ├── AuthContext.tsx
│   │   └── useAuth.ts
│   └── billing/
│       ├── BillingService.ts
│       └── InvoiceList.tsx
└── shared/
    ├── api.ts
    └── types.ts
```

## Error Handling

```typescript
// Typed errors
class ApiError extends Error {
  constructor(
    public statusCode: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// Explicit error handling
try {
  const user = await fetchUser(id);
} catch (error) {
  if (error instanceof ApiError && error.statusCode === 404) {
    // handle not found
  }
  throw error;
}
```

## Async Patterns

```typescript
// Parallel independent operations
const [user, settings] = await Promise.all([
  fetchUser(id),
  fetchSettings(id),
]);

// Sequential dependent operations
const user = await fetchUser(id);
const posts = await fetchPosts(user.blogId);
```

## React Patterns (if applicable)

- Functional components with hooks
- Custom hooks for reusable logic (`useAuth`, `useFetch`)
- Context for cross-cutting concerns, not prop drilling
- Memoize expensive computations with `useMemo`/`useCallback`

## Code Review Checklist

1. **Zod schemas at boundaries** — no raw `as` casts on external data
2. **Early returns, flat code** — no nested `if/else` pyramids
3. Enums over string literal unions
4. `strict: true` — no implicit `any`
5. snake_case for DB types, camelCase for app types
6. Entry files minimal — lifecycle only
7. Files under 300 lines
8. Feature-based organization
9. Typed error classes — no bare `Error`
10. `Promise.all` for parallel operations
11. No `console.log` in production code
12. Exports are intentional — no barrel re-exports of everything
