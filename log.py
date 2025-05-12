# log.py
import os
import discord
import aiohttp
from discord import Webhook
from datetime import datetime, timezone
import requests

WEBHOOK_URLS = os.environ["LOG_WEBHOOK_URL"].split(",")

async def notify_staff(title: str, description: str, color):
    """Async notification via Discord webhooks."""
    color_value = color.value if isinstance(color, discord.Color) else int(color)
    embed = discord.Embed(
        title=title,
        description=description,
        color=color_value,
        timestamp=datetime.now(timezone.utc)
    )

    async with aiohttp.ClientSession() as session:
        for url in WEBHOOK_URLS:
            url = url.strip()
            try:
                webhook = Webhook.from_url(url, session=session)
                await webhook.send(embed=embed, username="SkySpoofer Bot")
            except Exception as e:
                # Log but don’t propagate
                print(f"[LOG ERROR] notify_staff failed for {url}: {e}")

def notify_staff_sync(title: str, description: str, color):
    """Sync notification via HTTP POST for sync contexts."""
    color_value = color.value if isinstance(color, discord.Color) else int(color)
    embed = {
        "title": title,
        "description": description,
        "color": color_value,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    payload = {
        "username": "SkySpoofer Bot",
        "embeds": [embed]
    }

    for url in WEBHOOK_URLS:
        url = url.strip()
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print(f"[LOG ERROR] notify_staff_sync failed for {url}: {e}")
