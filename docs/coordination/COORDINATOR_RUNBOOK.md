# Coordinator runbook (v0.2.1 transient artifacts)

## Ownership

```text
allowed_paths   = intended work product (may be committed)
transient_paths = explicitly anticipated disposable tool side-effects
```

```text
v0.2:   unexpected untracked → POSTCONDITION_FAILED
v0.2.1: declared transient may be cleaned only under strict contract
```

Never: `if path in transient_paths: ignore`. Always: baseline → classify → evidence → exact unlink → re-status → normal postconditions.

## Metadata

```yaml
transient_paths: uv.lock
```

Comma-separated for multiple. Rules: relative exact paths only; no globs; no `..`; no absolute; no directories; no overlap with allowed/required.

## Cleanup contract

Before Executor: each transient must be **absent** and **untracked**.

After Executor, a changed path in `transient_paths` is cleanable only if:

```text
absent before
untracked before
untracked after (??)
regular file (not symlink/dir)
exact path match
```

Then: SHA256 evidence → `Path.unlink()` → `git status` again must show no leftover transient and no new unexpected paths.

Then: normal v0.2 postconditions + exact-path commit/push. Transients never staged.

## Audit fields

```text
declared_transient_paths
transient_paths_observed
transient_paths_cleaned
transient_cleanup_verified
transient_sha256
```

## Opt-in only

Without `transient_paths`, pilot #2 style `uv.lock` remains `POSTCONDITION_FAILED`.

Do **not** add `uv.lock` to `.gitignore` or `allowed_paths` for this.
