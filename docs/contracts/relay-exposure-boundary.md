# Relay Exposure Boundary Contract

Status:

- planning gate durable doc
- current anchor: `v7.6`
- lane: `Distribution Node MVP`

## Purpose

この文書は、public relay / public contract と Oracle-host expose logic の boundary を固定する。
主目的は relay server entry と expose adapter を分離して読むことであり、topology surgery を始めることではない。

## Scope

この文書が固定するもの:

- relay server entry vs expose adapter boundary
- Oracle host dependency must not mix into public relay / public contract
- public relay contract must not require Oracle-host-only internals

この文書が固定しないもの:

- Cloudflare quick tunnel exactness
- expose mode selection exactness
- topology redesign
- deploy / rollback / supervision choreography

## Non-Goals

- control-plane branch family redesign
- Oracle host orchestration plan
- public/private/control-plane rewiring
- `git mv` / split steps

## Relay Server Entry vs Expose Adapter Boundary

relay contract 側に残してよいもの:

- relay server entry
- relay protocol
- public-facing relay semantics

expose adapter 側に押し出すべきもの:

- Cloudflare / Oracle host specific expose logic
- tunnel orchestration
- host-bound supervision hooks

固定 truth:

- public relay contract は Oracle-host-only internals を要求しない
- Oracle host dependency を public relay / public contract に直接混ぜない

Status:

- boundary rule = fixed
- exact adapter interface = `UNRESOLVED`

## Oracle Host Dependency Boundary

禁止:

- public relay start path が Oracle host specific runtime を前提にすること
- public contract が host-local secrets / host process controls を前提にすること

許可:

- public-safe relay protocol docs
- separate adapter boundary docs

## Quick Tunnel / Expose Mode Exactness

tracked docs 上で読み取れるのは「Oracle host expose logic は public contract に混ぜない」まで。

この phase で未固定:

- quick tunnel default policy
- expose mode switching rules
- public URL file semantics の exact lifecycle

Status:

- quick tunnel exactness = `GAP`
- expose mode exactness = `UNRESOLVED`

## Public Relay Contract Requirements

public relay contract は少なくとも次を守る。

- Oracle-host-only internals を required dependency にしない
- public artifacts は private internals を直接 import しない
- cross-repo interaction は contract 経由だけ

## Topology Note

この文書は branch family redesign でも repo split surgery でもない。
扱うのは boundary reading だけである。

## Open Gaps

- `GAP`: relay server entry の dedicated durable protocol doc exactness
- `GAP`: public URL file semantics exactness
- `UNRESOLVED`: expose adapter interface shape
- `UNRESOLVED`: quick tunnel / expose mode runtime selection

## Anchor Set

- `docs/V76_TRUTH_SYNC_PACKET_JP.md`
- `CONTRACT_GAPS.md`
- `REPO_TARGET_TREES.md`
- `docs/PROTOCOL.md`
