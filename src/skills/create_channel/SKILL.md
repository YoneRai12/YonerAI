# Create Channel Skill

Creates a new text or voice channel.

## Usage

```json
{
  "name": "create_channel",
  "args": {
    "name": "new-channel",
    "channel_type": "text",
    "private": false,
    "users_to_add": "user_id_1 user_id_2"
  }
}
```

## Parameters

*   `name` (string, required): The name of the channel.
*   `channel_type` (string, optional): "text" or "voice". Default is "voice" (based on legacy default, but usually text is safer default). Legacy says "voice".
*   `private` (boolean, optional): Whether the channel is private.
*   `users_to_add` (string, optional): IDs of users to add if private.
