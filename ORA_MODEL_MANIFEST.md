# ORA Model Manifest (v1.0)

This document defines the **Supported Models and Traffic Limits** for the ORA System.
Any updates to `src/config.py` or routing logic MUST validate against this list.

## 1. High Intel Lane (Max 1M Tokens/Day)
*Shared OpenAI Traffic (Free Tier)*
**Models**:
*   `gpt-5.1`
*   `gpt-5.1-codex`
*   `gpt-5`
*   `gpt-5-codex`
*   `gpt-5-chat-latest`
*   `gpt-4.1`
*   `gpt-4o`
*   `o1`
*   `o3`

## 2. Stable Lane (Max 10M Tokens/Day)
*Shared OpenAI Traffic (Free Tier)*
**Models**:
*   `gpt-5.1-codex-mini` (Current Default)
*   `gpt-5-mini`
*   `gpt-5-nano`
*   `gpt-4.1-mini`
*   `gpt-4.1-nano`
*   `gpt-4o-mini`
*   `o1-mini`
*   `o3-mini`
*   `o4-mini`
*   `codex-mini-latest`

## 3. Critical Constraints
1. **Temperature**: MUST NOT be sent. (Strictly Enforced)
2. **Endpoint**: Requires Custom Gateway (Env: `OPENAI_BASE_URL`).

## 4. Default Routing
*   **Coding**: `gpt-5.1-codex-mini`
*   **High Intel**: `gpt-5.1-codex-mini`
*   **Standard**: `gpt-5.1-codex-mini`
