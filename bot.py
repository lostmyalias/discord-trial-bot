# bot.py
import os
import secrets
import discord
from discord import app_commands
from discord.ui import View, Button
from replit import db

# ── Config from Replit Secrets ──
CLIENT_ID    = os.environ["CLIENT_ID"]
GUILD_ID     = int(os.environ["GUILD_ID"])
BOT_TOKEN    = os.environ["BOT_TOKEN"]
REDIRECT_URI = os.environ["REDIRECT_URI"]

OAUTH_BASE = "https://discord.com/oauth2/authorize"

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

@bot.event
async def on_ready():
    # Sync only to your test guild for instant updates
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"[✅] Bot ready as {bot.user}")

@tree.command(
    name="trial",
    description="🔑 Claim your free SkySpoofer trial key!",
    guild=discord.Object(id=GUILD_ID)
)
async def trial(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    user_key = f"user:{interaction.user.id}"

    if user_key not in db:
        # 1) CSRF-safe state
        state = secrets.token_urlsafe(16)
        db[f"state:{state}"] = str(interaction.user.id)

        # 2) Build OAuth URL
        oauth_url = (
            f"{OAUTH_BASE}"
            f"?client_id={CLIENT_ID}"
            f"&redirect_uri={REDIRECT_URI}"
            f"&response_type=code"
            f"&scope=identify%20email"
            f"&state={state}"
        )

        # 3) Ephemeral embed + link button
        embed = discord.Embed(
            title="🔗 Link Discord & run again!",
            description="Click the button below to link.",
            color=discord.Color.blurple()
        )
        view = View()
        view.add_item(Button(label="Link Discord", url=oauth_url))
        await interaction.followup.send(embed=embed, view=view)

    else:
        # Already linked
        await interaction.followup.send(
            "✅ You're already linked! Trial-key dispensing coming in Phase 2…"
        )

def run_bot():
    bot.run(BOT_TOKEN)
