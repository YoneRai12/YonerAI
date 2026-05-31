# YonerAIOracle Self-Evolution Private Handoff

Status: private/official implementation handoff stub. This public repository does not implement the production system described here.

## Purpose

YonerAIOracle must own the production self-evolution system. The public repo
only provides a proposal-only simulator and boundary tests. Production signal
ingestion, product intelligence, owner approval, patch candidate generation,
production Oracle coordination, production auth/account linking boundaries, and
official release/social drafting must stay in the private/official lane.

## Required Private Capabilities

1. Signal ingestion
   - Accept only owner-approved signal classes.
   - Separate product metrics, support feedback, and runtime diagnostics.
   - Never send private/local content into public fixtures.

2. Product intelligence
   - Deduplicate recurring issues.
   - Classify user impact, frequency, privacy risk, implementation cost,
     provider independence impact, and same-experience impact.
   - Keep raw sensitive evidence out of public summaries.

3. Support feedback
- Ingest support feedback only through approved private connectors.
- Redact user identifiers, secrets, local paths, and private runtime details.
- Do not export raw prompts or raw completions into public proposal fixtures.
- Keep public repo outputs low-resolution.

4. Owner approval
   - Require owner approval before patch generation, branch creation, PR
     creation, release notes, social drafts, or deployment preparation.
   - Preserve an auditable approval record.

5. Patch candidate
   - Generate candidate changes only in private staging.
   - Include tests, rollback plan, impact summary, and non-claim checks.
   - Never auto-merge.

6. Rollback plan
   - Include rollback commands, data migration reversal if applicable, and
     release-note correction path.

7. Release note / X post draft
   - Produce drafts for owner review only.
   - Do not publish automatically.

## Public Repo Boundary

The public repo may consume only safe proposal summaries and synthetic fixtures.
It must not contain:

- production tokens
- private signal payloads
- support inbox contents
- private runtime inventory
- production routes
- break-glass details
- production signing or trust material

## Next Private Implementation Questions

- Which official signals are owner-approved for ingestion?
- Which retention limits apply to product intelligence summaries?
- What approval state transitions are allowed before patch generation?
- Where should private audit logs live?
- Which releases may include self-evolution-generated drafts?
