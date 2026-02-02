# System Control Skill

Performs system-level actions via the SystemCog (e.g., restart, sync, status).

## Usage

```json
{
  "name": "system_control",
  "args": {
    "action": "restart",
    "value": null
  }
}
```

## Parameters

*   `action` (string, required): The action to perform.
*   `value` (string, optional): Additional argument for the action.
