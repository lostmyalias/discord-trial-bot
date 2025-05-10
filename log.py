# log.py
import os
import discord
import aiohttp
from discord import Webhook
from datetime import datetime, timezone

WEBHOOK_URLS = os.environ["LOG_WEBHOOK_URL"].split(",")

async def notify_staff(title: str, description: str, color):
    color_value = color.value if isinstance(color, discord.Color) else int(color)
    embed = discord.Embed(
        title=title,
        description=description,
        color=color_value,
        timestamp=datetime.now(timezone.utc)
    )
    async with aiohttp.ClientSession() as session:
        for url in WEBHOOK_URLS:
            webhook = Webhook.from_url(url.strip(), session=session)
            await webhook.send(embed=embed, username="SkySpoofer Bot")

def notify_staff_sync(title: str, description: str, color):
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
    import requests
    for url in WEBHOOK_URLS:
        requests.post(url.strip(), json=payload)
