# Discord Trial Bot

> One-stop, plug-and-play Discord Bot for managing time-limited SkySpoofer trial keys.

## 🚀 Deployment

Designed exclusively for Replit:

1. Fork or clone into Replit.
2. Replit auto-installs dependencies via `requirements.txt`.
3. Set the environment secrets (see below).
4. Run—`main.py` launches the bot and OAuth2 server automatically.

## 📁 Repository Layout

**Core files (required):**
```
.
├─ bot.py            # Slash commands & key management
├─ main.py           # Entrypoint: starts bot + OAuth server
├─ oauth_server.py   # Web-based OAuth2 redemption endpoint
├─ log.py            # Webhook logging helper
├─ requirements.txt  # Python deps
└─ .replit           # Replit launch config
```

**Helper scripts (standalone):**
```
├─ init_keys.py      # Bulk-seed trial keys
├─ view_db.py        # Print database contents
├─ clear_db.py       # Wipe all keys (danger!)
├─ push.sh           # Replit git add/commit/push wrapper
└─ .gitignore        # Ignore rules
```

## 🔐 Environment Variables

| Name              | Description                                                  | Multiple values? |
|-------------------|--------------------------------------------------------------|------------------|
| `CLIENT_ID`       | Discord App Client ID                                        | No               |
| `CLIENT_SECRET`   | Discord App Client Secret                                    | No               |
| `BOT_TOKEN`       | Discord Bot Token                                            | No               |
| `REDIRECT_URI`    | OAuth2 Redirect URI                                          | No               |
| `LOG_WEBHOOK_URL` | Discord Webhook URL for audit logs                           | Yes              |
| `GITHUB_TOKEN`    | GitHub token (e.g. for auto-updates)                         | No               |
| `GUILD_IDS`       | Guild IDs where bot operates                                 | Yes              |
| `STAFF_ROLE_IDS`  | Role IDs allowed to manage keys (add/delete/freeze)          | Yes              |

> **Note:** Comma-separated values must not contain spaces.

## ⚙️ Slash Commands

```
/add_keys            Add trial keys (comma-separated)
/delete_all_keys     Wipe all keys
/freeze              Pause key disbursement
/list_keys           List all available keys
/set_cooldown_days   Set trial cooldown
/status              Show key-distribution status
/trial               Claim your free SkySpoofer trial key!
/unfreeze            Resume key disbursement
/unlink              Unlink a user
```
