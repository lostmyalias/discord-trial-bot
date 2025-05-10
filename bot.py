import os
import secrets
import discord
from discord import app_commands
from discord.ui import View, Button
from replit import db
from datetime import datetime, timezone, timedelta

# ── Config ──
CLIENT_ID       = os.environ["CLIENT_ID"]
GUILD_ID        = int(os.environ["GUILD_ID"])
BOT_TOKEN       = os.environ["BOT_TOKEN"]
REDIRECT_URI    = os.environ["REDIRECT_URI"]
STAFF_ROLE_IDS  = [int(r) for r in os.environ.get("STAFF_ROLE_IDS", "").split(",") if r.strip()]
COOLDOWN_DAYS   = 30
OAUTH_BASE      = "https://discord.com/oauth2/authorize"

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

def parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts)

# ── Bot Startup ──
@bot.event
async def on_ready():
    # sync to guild for immediate availability
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"[✅] Bot ready as {bot.user}")

# ── Trial Command ──
@tree.command(
    name="trial",
    description="🔑 Claim your free SkySpoofer trial key!",
    guild=discord.Object(id=GUILD_ID)
)
async def trial(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    # check if frozen
    if db.get("frozen", False):
        return await interaction.followup.send(
            "⏸️ Key disbursement is currently paused by staff.",
            ephemeral=True
        )

    user_id     = str(interaction.user.id)
    user_db_key = f"user:{user_id}"
    now         = datetime.now(timezone.utc)
    cooldown    = timedelta(days=COOLDOWN_DAYS)

    # not linked yet
    if user_db_key not in db:
        state = secrets.token_urlsafe(16)
        db[f"state:{state}"] = user_id
        oauth_url = (
            f"{OAUTH_BASE}"
            f"?client_id={CLIENT_ID}"
            f"&redirect_uri={REDIRECT_URI}"
            f"&response_type=code"
            f"&scope=identify%20email"
            f"&state={state}"
        )
        embed = discord.Embed(
            title="🔗 Link Discord, key will be sent via DMs!",
            description="Click below to link your account.",
            color=discord.Color.blurple()
        )
        view = View()
        view.add_item(Button(label="Link Discord", url=oauth_url))
        return await interaction.followup.send(embed=embed, view=view)

    user_data = db[user_db_key]

    # already has a key?
    if "dispensed_key" in user_data:
        last_ts = parse_iso(user_data["last_dispensed_at"])
        elapsed = now - last_ts
        if elapsed < cooldown:
            rem = cooldown - elapsed
            d, s = rem.days, rem.seconds
            h, m = s // 3600, (s % 3600) // 60
            return await interaction.followup.send(
                f"⏳ Next key in **{d}d {h}h {m}m**.",
                ephemeral=True
            )
        # cooldown passed: clear for new dispense
        del user_data["dispensed_key"]
        del user_data["last_dispensed_at"]
        db[user_db_key] = user_data

    # dispense a new key
    for db_key, info in db.items():
        if db_key.startswith("key:") and not info.get("dispensed", False):
            key_str = db_key.split("key:")[1]
            db[db_key] = {"dispensed": True, "user_id": user_id}

            record = db[user_db_key]
            record["dispensed_key"]     = key_str
            record["last_dispensed_at"] = now.isoformat()
            db[user_db_key] = record

            # DM with fallback
            try:
                await interaction.user.send(
                    f"🎉 Your SkySpoofer trial key:\n**{key_str}**\n\n"
                    "You won’t be issued another for 30 days."
                )
            except discord.Forbidden:
                return await interaction.followup.send(
                    "⚠️ I couldn’t DM you. Please open your DMs and try again.",
                    ephemeral=True
                )

            await interaction.followup.send(
                "✅ Trial key sent via DM!",
                ephemeral=True
            )
            print(f"[LOG] Dispensed {key_str} → {user_id}")
            return

    # no keys left
    await interaction.followup.send(
        "❌ All trial keys claimed—please check back later.",
        ephemeral=True
    )
    print(f"[WARN] No keys left for {user_id}")

# ── Staff Check ──
def is_staff():
    def pred(interaction: discord.Interaction) -> bool:
        return any(r.id in STAFF_ROLE_IDS for r in interaction.user.roles)
    return app_commands.check(pred)

# ── Admin Commands ──
@tree.command(name="freeze", description="⏸️ Pause key disbursement", guild=discord.Object(id=GUILD_ID))
@is_staff()
@app_commands.guild_only()
async def freeze(interaction: discord.Interaction):
    db["frozen"] = True
    await interaction.response.send_message("🔒 Disbursement frozen.", ephemeral=True)

@tree.command(name="unfreeze", description="▶️ Resume key disbursement", guild=discord.Object(id=GUILD_ID))
@is_staff()
@app_commands.guild_only()
async def unfreeze(interaction: discord.Interaction):
    db["frozen"] = False
    await interaction.response.send_message("🔓 Disbursement resumed.", ephemeral=True)

@tree.command(
    name="status",
    description="📊 Show key-distribution status",
    guild=discord.Object(id=GUILD_ID)
)
@is_staff()
@app_commands.guild_only()
async def status(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    now = datetime.now(timezone.utc)

    # gather metrics
    total = left = 0
    for k, v in db.items():
        if k.startswith("key:"):
            total += 1
            if not v.get("dispensed", False):
                left += 1

    disp24 = disp7 = 0
    for k, v in db.items():
        if k.startswith("user:") and "last_dispensed_at" in v:
            ts = parse_iso(v["last_dispensed_at"])
            delta = now - ts
            if delta <= timedelta(days=1): disp24 += 1
            if delta <= timedelta(days=7): disp7 += 1

    frozen = db.get("frozen", False)

    # build embed with line-separated stats
    embed = discord.Embed(
        title="SkySpoofer Key Distribution Status",
        description=(
            f"**Total Keys in DB:** {total}\n"
            f"**Keys Remaining:** {left}\n"
            f"**Dispensed in last 24h:** {disp24}\n"
            f"**Dispensed in last 7d:** {disp7}\n"
            f"**Frozen:** {'Yes' if frozen else 'No'}"
        ),
        color=discord.Color.blurple()
    )

    await interaction.followup.send(embed=embed, ephemeral=True)


@tree.command(name="add_keys", description="➕ Add trial keys (comma-separated)", guild=discord.Object(id=GUILD_ID))
@is_staff()
@app_commands.guild_only()
@app_commands.describe(keys="CSV list, e.g. SkyTrial-ABC,SkyTrial-DEF")
async def add_keys(interaction: discord.Interaction, keys: str):
    added = skipped = invalid = 0
    for raw in keys.split(","):
        k = raw.strip()
        if not k or " " in k:
            invalid += 1
            continue
        db_key = f"key:{k}"
        if db_key in db:
            skipped += 1
        else:
            db[db_key] = {"dispensed": False}
            added += 1

    await interaction.response.send_message(
        f"✅ Added {added} keys!",
        ephemeral=True
    )

@tree.command(name="delete_all_keys", description="🗑️ Wipe all keys", guild=discord.Object(id=GUILD_ID))
@is_staff()
@app_commands.guild_only()
async def delete_all_keys(interaction: discord.Interaction):
    count = 0
    for key in list(db.keys()):
        if key.startswith("key:"):
            del db[key]
            count += 1

    await interaction.response.send_message(f"🧨 Deleted {count} keys.", ephemeral=True)

@tree.command(name="unlink", description="🔄 Unlink a user", guild=discord.Object(id=GUILD_ID))
@is_staff()
@app_commands.guild_only()
@app_commands.describe(user="User to unlink (default: you)")
async def unlink(interaction: discord.Interaction, user: discord.Member = None):
    target = user or interaction.user
    ukey   = f"user:{target.id}"
    if ukey in db:
        del db[ukey]
        await interaction.response.send_message(f"🔄 Unlinked {target.mention}.", ephemeral=True)
    else:
        await interaction.response.send_message(f"ℹ️ {target.mention} not linked.", ephemeral=True)

def run_bot():
    bot.run(BOT_TOKEN)
