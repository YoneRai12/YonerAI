# Say Skill

Sends a message to a specific channel or the current channel.

## Usage

```json
{
  "name": "say",
  "args": {
    "message": "Hello world",
    "channel_name": "general"
  }
}
```

## Parameters

*   `message` (string, required): The content to send.
*   `channel_name` (string, optional): The name of the target channel. If omitted, sends to current channel.
