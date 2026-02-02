# Manage User Role Skill

Adds or removes roles from a user.

## Usage

```json
{
  "name": "manage_user_role",
  "args": {
    "user_query": "username_or_id",
    "role_query": "role_name_or_id",
    "action": "add"
  }
}
```

## Parameters

*   `user_query` (string, required): Username, ID, or mention.
*   `role_query` (string, required): Role name, ID, or mention.
*   `action` (string, required): "add" or "remove".
