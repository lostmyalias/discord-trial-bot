import os
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse
from replit import db
from datetime import datetime, timezone

app = FastAPI()

# ── Config ──
CLIENT_ID     = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
BOT_TOKEN     = os.environ["BOT_TOKEN"]
REDIRECT_URI  = os.environ["REDIRECT_URI"]

COOLDOWN_DAYS = 30  # for bookkeeping, though immediate dispense only on first link

def dm_user(discord_id: str, message: str):
    # 1) Open a DM channel
    resp = requests.post(
        "https://discord.com/api/v10/users/@me/channels",
        headers={
            "Authorization": f"Bot {BOT_TOKEN}",
            "Content-Type": "application/json"
        },
        json={"recipient_id": discord_id}
    )
    resp.raise_for_status()
    channel_id = resp.json()["id"]

    # 2) Send the message
    msg_resp = requests.post(
        f"https://discord.com/api/v10/channels/{channel_id}/messages",
        headers={
            "Authorization": f"Bot {BOT_TOKEN}",
            "Content-Type": "application/json"
        },
        json={"content": message}
    )
    msg_resp.raise_for_status()

@app.get("/oauth/callback")
async def oauth_callback(request: Request):
    code  = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code or not state:
        raise HTTPException(400, "Missing code or state")

    state_key = f"state:{state}"
    if state_key not in db:
        raise HTTPException(400, "Invalid or expired state")
    discord_id = db[state_key]

    # Exchange code → token
    token_resp = requests.post(
        "https://discord.com/api/oauth2/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "scope": "identify email"
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    token_resp.raise_for_status()
    access_token = token_resp.json()["access_token"]

    # Fetch user info
    user_resp = requests.get(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    user_resp.raise_for_status()
    user_data = user_resp.json()
    email = user_data.get("email")
    if not email:
        raise HTTPException(400, "Email scope not granted")

    # Persist link record
    user_db_key = f"user:{discord_id}"
    db[user_db_key] = {
        "discord_id": discord_id,
        "email": email
    }
    del db[state_key]  # one-time use

    # Auto-dispense a key
    now = datetime.now(timezone.utc)
    for db_key, info in db.items():
        if db_key.startswith("key:") and not info.get("dispensed"):
            key_str = db_key.split("key:")[1]

            # mark key
            db[db_key] = {"dispensed": True, "user_id": discord_id}

            # annotate user record
            record = db[user_db_key]
            record["dispensed_key"]     = key_str
            record["last_dispensed_at"] = now.isoformat()
            db[user_db_key] = record

            # DM the user
            dm_user(
                discord_id,
                f"🎉 Congrats, your account is linked!\n"
                f"Here’s your SkySpoofer trial key:\n**{key_str}**\n\n"
                "Don’t lose it—you won’t be issued another one for 30 days."
            )
            print(f"[LOG] Auto-dispensed {key_str} → {discord_id}")
            break

    # Redirect back
    return RedirectResponse("https://skyspoofer.com")
