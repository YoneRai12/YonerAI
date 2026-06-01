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
