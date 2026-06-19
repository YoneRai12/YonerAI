# YonerAI Update Policy

Status: public policy for the YonerAI CLI Local Runtime.

## Current behavior

YonerAI does not perform forced updates.

`yonerai update check`, `yonerai update plan`, and TUI `/更新` are dry-run
status surfaces. They can show the current version, latest manifest version,
channel, artifact, SHA256 presence, trust/signature state, and next safe
command. They do not download, install, mutate PATH, execute remote code,
request admin rights, edit the registry, install services, or auto-apply an
update.

## Deferred update classes

YonerAI surfaces update state as policy metadata so the TUI can explain what
will happen without installing anything.

| class | behavior during an active session | behavior after the current task | next startup behavior |
| --- | --- | --- | --- |
| normal update | Show a notice only. | Show the next safe command if update notice is enabled. | Continue normally. |
| recommended update | Show a stronger notice only. | Show the update prompt if update notice is enabled. | Continue normally. |
| security update | Warn, but do not interrupt an active task. | Show the update prompt after the task completes. | Show the update screen early, then allow local-safe use. |
| critical update | Warn, but do not silently update. | Show the update prompt after the task completes. | Show the update screen first. Basic local mock chat remains available. |

Critical policy may restrict only risky live/cloud/provider-sensitive features
when an explicit minimum-safe-version policy exists. It must not block basic
local mock chat, and it must always explain the reason.

The public repo currently emits `security_update=false` and
`critical_update=false` from local manifest checks. Production advisory policy,
minimum-safe-version enforcement, and signed advisory feeds are future
official/private-lane work.

## Security advisories

A future security advisory can recommend that users update. The CLI may display
a warning or next safe command, but it must not force an update or silently
change the installed runtime.

## Requirements before forced or automatic update can exist

Forced update or automatic update apply requires a separate owner-approved
release lane with at least:

- production signing or an approved trust framework
- rollback plan
- clear user notice
- dry-run preview
- explicit approval path
- audit record
- no provider key leakage
- no local private content upload
- no PATH, registry, service, or admin mutation without explicit approval

Until those requirements are implemented and reviewed, YonerAI update behavior
is warning-only and dry-run only.

## Non-claims

- No production installer.
- No npm, winget, Microsoft Store, or production package-manager channel.
- No production signing key or production trust store in the public repo.
- No automatic updater service.
- No forced update.
