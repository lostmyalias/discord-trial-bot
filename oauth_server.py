# oauth_server.py
import os, requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse
from replit import db

app = FastAPI()

CLIENT_ID    = os.environ["CLIENT_ID"]
CLIENT_SECRET= os.environ["CLIENT_SECRET"]
REDIRECT_URI = os.environ["REDIRECT_URI"]

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

    # Persist link
    db[f"user:{discord_id}"] = {"discord_id": discord_id, "email": email}
    del db[state_key]  # one-time use

    # send them home
    return RedirectResponse("https://skyspoofer.com")
