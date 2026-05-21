# ORA / YonerAI Naming Compatibility - 2026-05-21

## Purpose

YonerAI is the public product name. ORA remains a legacy/internal runtime namespace until compatibility migration is proven by tests and staged aliases. Naming cleanup must not break imports, environment variables, saved configuration, user scripts, or public/runtime contracts.

## Current Policy

- New public-facing documentation should use `YonerAI` for the product.
- Existing internal modules, packages, commands, and tests that still use `ora` or `ORA` stay compatible until a staged migration lands.
- Existing `ORA_*` environment variables stay valid until explicit compatibility aliases are implemented and tested.
- `ora_core` and `src/cogs/ora.py` are not renamed while boundary extraction is still in progress.
- New code may use YonerAI naming where it does not change public contracts, import paths, environment variable names, or runtime behavior.
- Public docs may mention ORA only as legacy/internal naming, compatibility context, or historical traceability.

## Migration Gates

Any future ORA-to-YonerAI runtime migration must include:

1. Import compatibility tests for old and new module paths.
2. Environment variable alias tests for existing `ORA_*` keys and new names, if added.
3. Public capability and API contract tests proving user-visible names remain stable.
4. Release notes that explain compatibility, deprecation timing, and rollback expectations.
5. A small PR scope that changes one namespace surface at a time.

## Not Current Priority

A broad ORA rename is not current priority. Cosmetic rename work is lower value than security/runtime hardening, behavior-preserving `src/cogs/ora.py` extraction, Discord contract acceptance tests, and three-mode capability harness coverage.

## What Can Be Claimed

- YonerAI is the public product name.
- ORA naming is retained as a compatibility namespace where it still exists.
- Future naming migration has explicit gates.

## What Must Not Be Claimed

- Broad ORA rename complete.
- `src/cogs/ora.py` solved.
- Runtime namespace migration complete.
- Compatibility aliases implemented, unless a later code/test PR proves them.
