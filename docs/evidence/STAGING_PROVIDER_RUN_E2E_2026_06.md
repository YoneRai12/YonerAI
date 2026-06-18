# Staging Provider Run E2E Evidence

Date: 2026-06-19
Status: public-safe staging E2E evidence
Backend: `https://api-staging.yonerai.com`

This evidence confirms the public YonerAI CLI can submit an explicit-consent
staging provider run through Native Run, then display status, events, and result
without receiving provider keys, Google tokens, refresh tokens, local paths, or
private file bytes.

## Commands Verified

```powershell
$env:YONERAI_STAGING_AUTH_ORIGIN = "https://api-staging.yonerai.com"
yonerai auth status --json
yonerai provider status --json
yonerai provider quota --json
yonerai provider models --json
yonerai sync conversation show cloud_conv_84c212c254ae65ca_001 --json
yonerai privacy provider-sharing enable cloud_conv_84c212c254ae65ca_001 --sync-policy cloud_to_local --confirm --json
yonerai run submit "use cloud conversation body" --capability run.openai_shared_text --conversation-id cloud_conv_84c212c254ae65ca_001 --conversation-origin cloud --sync-policy cloud_to_local --provider-data-policy openai_shared_explicit --json
yonerai run status run_native_0f207e79bde3 --json
yonerai run events run_native_0f207e79bde3 --json
yonerai run result run_native_0f207e79bde3 --json
yonerai run status run_native_2b860428ee65 --json
yonerai run events run_native_2b860428ee65 --json
yonerai run result run_native_2b860428ee65 --json
yonerai capability list --json
yonerai module list --json
yonerai worker status --json
```

## Verified Result

- Staging auth state was linked.
- Provider gateway status was reachable.
- Provider quota/model policy was visible.
- The selected cloud conversation was metadata-only in public CLI output.
- Explicit per-conversation provider-sharing consent was recorded locally.
- Public CLI prepared AWS-backed provider context:
  - message body stayed on AWS
  - context manifest reported `raw_content_included=false`
  - provider consent preview was allowed
  - provider traffic approval was accepted
- Native Run submit returned `202` with run id `run_native_0f207e79bde3`.
- Run status reached `completed`.
- Events showed run creation, queueing, provider dispatch, and provider result.
- Result endpoint returned a completed provider result summary.
- A metadata-only `run.echo` official worker run was also verified through the
  public CLI as completed with run id `run_native_2b860428ee65`.
- The `run.echo` event sequence included run creation, queueing, worker claim,
  worker event, and result.
- Capability manifest included `run.openai_shared_text`.
- Module manifest included `run.core`.
- Worker status showed provider execution in AWS and the owner-worker path as separate.

## Negative Checks

- No provider-sharing consent: rejected before backend call.
- `local_only` plus `openai_shared_explicit`: rejected before backend call.
- Secret-like prompt: rejected before backend call.
- Consent revocation: future provider-sharing run was rejected before backend call.

## Safety Observed

- Google access token printed or stored: no
- Google refresh token printed or stored: no
- Google auth code printed or stored: no
- Provider key printed or stored: no
- Local private file bytes sent: no
- Local absolute path printed: no
- Raw chain-of-thought included: no
- OpenAI shared traffic default: off
- Provider sharing: explicit per conversation
- Local-only conversation sent to OpenAI: no
- Production Google login enabled: no
- Production Oracle/cloud runtime enabled: no

## Limitations

- This is staging only.
- The public repo does not include production AWS, Oracle, or Official Managed
  Cloud runtime.
- OpenAI shared traffic is not default and requires explicit per-conversation
  consent.
- Selected AWS-backed conversation input and provider output may be sent to
  OpenAI under the staging provider-sharing path.
- OpenAI project budget is a soft alert; YonerAI applies its own hard token
  reservation and application budget checks.
- Production signing/trust-store validation is not included.
- `reference_clawdbot` was not touched.
- `src/cogs/ora.py` remains a legacy boundary and is not solved here.
