# Self-Evolution Proposal-only MVP

Status: public-safe MVP plan and implementation boundary.

## Purpose

The proposal-only MVP converts synthetic or local public-safe fixture signals into owner-reviewable improvement proposals.

It is product intelligence. It is not autonomous code mutation.

## Included

- `SignalEvent` schema for public-safe fixture signals
- local synthetic fixture loader
- normalization into `SignalEvent`
- score breakdown for review aid
- Markdown proposal packet generator
- explicit owner approval gate
- tests that reject forbidden fields and automatic action fields

## Not Included

- real telemetry collection
- SNS scraping
- competitor scraping
- web scraping
- raw prompt, raw completion, raw chain-of-thought, or file-content ingestion
- private data ingestion
- Discord runtime ingestion
- model-provider live calls
- automatic code mutation
- automatic branch creation
- automatic PR creation or merge
- deployment
- release automation

## Input Contract

Input is local fixture JSON only. The fixture must use synthetic or public-safe aggregate data.

Required signal fields:

- `id`
- `source`
- `kind`
- `summary`
- `severity`
- `frequency`
- `evidence`
- `created_at`
- `privacy_class`
- `approval_required`

The fixture loader rejects secret-shaped values, local machine paths, live URLs, raw text fields, private identifiers, and automatic action fields.

## Output Contract

The output is a Markdown proposal packet for owner review.

The proposal packet includes:

- problem statement
- safe evidence summary
- candidate improvement
- score breakdown
- required tests
- rollback expectation
- approval gate

The proposal packet does not authorize code changes, publication, deployment, or release.

## Approval Gate

Scores are review aids only.

No score, model judgment, aggregate signal, or generated proposal is approval.

Implementation work requires a later owner-approved lane.

## Validation

The MVP is validated by tests that confirm:

- synthetic fixture proposals are generated
- forbidden fields are rejected
- secret-shaped values are rejected
- local paths are rejected
- live URLs are rejected
- high score does not set approval
- proposal Markdown includes the approval gate and non-automation guardrails
