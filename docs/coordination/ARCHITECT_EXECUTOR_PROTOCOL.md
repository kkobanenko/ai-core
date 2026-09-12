# Architect ↔ Executor protocol (Coordinator v0.2.1)

## Ownership

| Concern | Owner |
| --- | --- |
| Bounded edits / required artifacts | Executor |
| Declared transient tool side-effects cleanup | Coordinator (strict contract) |
| Postconditions + exact-path commit/push | Coordinator |

```text
allowed_paths   = intended work product
transient_paths = explicitly anticipated disposable tool side-effects
```

## Strictness

Coordinator never trusts Executor stdout about changed files.

Undeclared unexpected paths still fail closed.

Transient cleanup is opt-in via metadata and never uses `git clean` / globs / recursive deletes.
