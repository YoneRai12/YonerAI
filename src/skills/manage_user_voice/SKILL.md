# Manage User Voice Skill

Mutes, unmutes, or disconnects a user in a voice channel.

## Usage

```json
{
  "name": "manage_user_voice",
  "args": {
    "target_user": "username_or_id",
    "action": "mute_mic"
  }
}
```

## Parameters

*   `target_user` (string, required): Username, ID, or mention.
*   `action` (string, required): "mute_mic", "unmute_mic", or "disconnect".
