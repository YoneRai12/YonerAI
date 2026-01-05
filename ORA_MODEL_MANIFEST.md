# ORA Model Manifest (v1.0)

This document defines the **Supported Models and Traffic Limits** for the ORA System.
Any updates to `src/config.py` or routing logic MUST validate against this list.

## 1. High Intel Lane (250k Tokens/Day)
**Models**:
*   `gpt-5.1`
*   `gpt-5.1-codex` (Primary for Coding)
*   `gpt-5`
*   `gpt-5-codex`
*   `gpt-5-chat-latest`
*   `gpt-4.1`
*   `gpt-4o`
*   `o1`
*   `o3`

## 2. Stable Lane (2.5M Tokens/Day)
**Models**:
*   `gpt-5.1-codex-mini`
*   `gpt-5-mini` (Standard Default)
*   `gpt-5-nano`
*   `gpt-4.1-mini`
*   `gpt-4.1-nano`
*   `gpt-4o-mini`
*   `o1-mini`
*   `o3-mini`
*   `o4-mini`
*   `codex-mini-latest`

## 3. Critical Constraints
1. **Temperature**: MUST NOT be sent for `gpt-5` series, `o1`, or `o3`. These models imply reasoning/coding constraints that reject temperature modulation.
2. **Endpoint**: Ensure `v1/chat/completions` is used unless model is strictly legacy completion (but 5.1 implies advanced). Use `System` roles appropriately.

## 4. Default Routing
*   **Coding**: `gpt-5.1-codex`
*   **High Intel**: `gpt-5.1`
*   **Standard**: `gpt-5-mini`
