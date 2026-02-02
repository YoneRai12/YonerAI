# Cleanup Messages Skill

Deletes a specified number of recent messages from the current channel.

## Usage

```json
{
  "name": "cleanup_messages",
  "args": {
    "count": 10
  }
}
```

## Parameters

*   `count` (integer, optional): Number of messages to delete. Default is 10. Max 100.
