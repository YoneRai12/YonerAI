# YonerAI Health Version Contract

Status: public staging contract for CLI/API compatibility checks.
Scope: public CLI reads only version metadata from the staging Control Spine.

## Endpoint

`GET /v1/health`

The public CLI may call this endpoint when the staging origin is explicitly
configured. It is not a production health probe and it must not expose private
runtime inventory, internal routes, tokens, ARNs, local paths, hostnames, or
provider credentials.

## Response Shape

```json
{
  "status": "ok",
  "api_version": "yonerai.control-spine.v0.1",
  "min_cli_version": "0.20.0-alpha.1"
}
```

Fields:

- `status`: public status string such as `ok`, `degraded`, or
  `not_production`.
- `api_version`: semver-like public API contract string. Recommended format:
  `yonerai.control-spine.v<major>.<minor>`.
- `min_cli_version`: minimum public CLI version that should use this staging
  API, using normal YonerAI semver strings such as `0.20.0-alpha.1`.

## Missing Field Rule

If `api_version` or `min_cli_version` is missing, the CLI must not crash and
must not nag the user. Missing fields are treated as debug-only compatibility
information. User-facing output may show `unknown`, but it must not show a
warning unless a valid `min_cli_version` proves the CLI is below the minimum.

## Comparison Rule

The CLI compares its own version with `min_cli_version` by numeric semver core:

- strip a leading `v`;
- compare `major.minor.patch` numerically;
- prerelease suffixes are ignored for the minimum-version warning;
- malformed versions are treated as `0.0.0` and must not crash the CLI.

If the CLI version is lower than `min_cli_version`, the CLI warns politely and
suggests:

```text
yonerai update check
```

## Compatibility Window

The staging API should keep the current minor and previous minor compatible.
For example, when the current public CLI alpha is `0.21.x`, the staging API
should remain compatible with `0.21.x` and `0.20.x` unless a release note
announces a deprecation first.

## Deprecation Rule

Breaking a CLI/API contract requires:

1. a release note notice before enforcement;
2. a new `min_cli_version` value;
3. no private runtime detail in the health payload;
4. a public CLI fallback message that does not expose stack traces, internal
   endpoints, private hostnames, local paths, or tokens.

## Non-Claims

This contract does not mean production Google login, production Oracle, full
Official Managed Cloud, live Discord, provider execution, or automatic
local-to-cloud upload is available in the public repository.
