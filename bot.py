# bot.py
import os
import secrets
import discord
from discord import app_commands
from discord.ui import View, Button
from replit import db
from datetime import datetime, timezone, timedelta
from log import notify_staff
from typing import Optional


# ── Config & Defaults ──
CLIENT_ID         = os.environ["CLIENT_ID"]
BOT_TOKEN         = os.environ["BOT_TOKEN"]
REDIRECT_URI      = os.environ["REDIRECT_URI"]
OAUTH_BASE        = "https://discord.com/oauth2/authorize"
STATE_TTL_HOURS   = 1

# Multi-guild support: read GUILD_IDS or fall back to single GUILD_ID
if os.environ.get("GUILD_IDS"):
    GUILD_IDS = [int(x.strip()) for x in os.environ["GUILD_IDS"].split(",") if x.strip()]
else:
    GUILD_IDS = [int(os.environ["GUILD_ID"])]

DEFAULT_COOLDOWN  = 30  # days
SPAM_COOLDOWN_SEC = 5   # seconds
STAFF_ROLE_IDS    = [int(r) for r in os.environ.get("STAFF_ROLE_IDS","").split(",") if r.strip()]
LOW_POOL_THRESHOLD= 20
LOW_POOL_PING     = os.environ.get("LOW_POOL_PING", "@Staff")

intents = discord.Intents.default()
bot     = discord.Client(intents=intents)
tree    = app_commands.CommandTree(bot)

# ── GLOBAL ERROR HANDLER ──
@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    # Permissions check failed
    if isinstance(error, app_commands.CheckFailure):
        # Make sure we haven't already responded
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ You don’t have permission to use this command.",
                ephemeral=True
            )
    else:
        # Other errors—log & notify staff
        await notify_staff(
            "⚠️ Command Error",
            f"{interaction.user.mention} triggered an error in `{interaction.command}`:\n```{error}```",
            discord.Color.red()
        )
        # If we still can respond
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "🚫 An unexpected error occurred. Staff have been notified.",
                ephemeral=True
            )

def parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts)

def is_staff():
    def pred(interaction: discord.Interaction) -> bool:
        return any(r.id in STAFF_ROLE_IDS for r in interaction.user.roles)
    return app_commands.check(pred)

@bot.event
async def on_ready():
    # copy all global commands into each guild, then sync
    for gid in GUILD_IDS:
        guild_obj = discord.Object(id=gid)
        tree.copy_global_to(guild=guild_obj)
        await tree.sync(guild=guild_obj)
    print(f"[✅] Bot ready as {bot.user} – commands synced to {GUILD_IDS}")


# ── /trial ──
@tree.command(name="trial", description="🔑 Claim your free SkySpoofer trial key!")
@app_commands.guild_only()
async def trial(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    now      = datetime.now(timezone.utc)
    user_id  = str(interaction.user.id)
    user_key = f"user:{user_id}"

    # 1) Anti-spam per user
    last_spam = db.get(f"spam:{user_id}")
    if last_spam:
        diff = (now - parse_iso(last_spam)).total_seconds()
        if diff < SPAM_COOLDOWN_SEC:
            return await interaction.followup.send(
                f"⚠️ Please wait **{int(SPAM_COOLDOWN_SEC - diff)}s** before retrying.",
                ephemeral=True
            )
    db[f"spam:{user_id}"] = now.isoformat()

    # 2) Configurable cooldown
    cd_days  = db.get("config:cooldown_days", DEFAULT_COOLDOWN)
    cooldown = timedelta(days=cd_days)

    # 3) Frozen check
    if db.get("frozen", False):
        await interaction.followup.send("⏸️ Disbursement paused.", ephemeral=True)
        return await notify_staff(
            "⏸️ Claim Blocked – Frozen",
            f"{interaction.user.mention} tried to claim while frozen.",
            discord.Color.orange()
        )

    # 4) Not linked → send OAuth embed
    if user_key not in db:
        state = secrets.token_urlsafe(16)
        db[f"state:{state}"] = {"user_id": user_id, "created_at": now.isoformat()}
        oauth_url = (
            f"{OAUTH_BASE}?client_id={CLIENT_ID}"
            f"&redirect_uri={REDIRECT_URI}"
            f"&response_type=code"
            f"&scope=identify%20email"
            f"&state={state}"
        )
        embed = discord.Embed(
            title="🔗 Link Discord, key will be DMed!",
            description="Click below to authorize.",
            color=discord.Color.blurple()
        )
        view = View().add_item(Button(label="Link Discord", url=oauth_url))
        return await interaction.followup.send(embed=embed, view=view)

    user_data = db[user_key]

    # 5) Already has key? cooldown-aware ephemeral embed
    if "dispensed_key" in user_data:
        last = parse_iso(user_data["last_dispensed_at"])
        elapsed = now - last
        if elapsed < cooldown:
            rem = cooldown - elapsed
            d, s = rem.days, rem.seconds
            h, m = s // 3600, (s % 3600) // 60

            embed = discord.Embed(
                title="🔁 Trial Key Already Claimed",
                description=(
                    f"**Key:** `{user_data['dispensed_key']}`\n\n"
                    f"**Next free key in:** {d}d {h}h {m}m"
                ),
                color=discord.Color.orange()
            )
            # only visible to the user
            await interaction.followup.send(embed=embed, ephemeral=True)

            # log for staff
            await notify_staff(
                "⏳ Cooldown Active",
                f"{interaction.user.mention} reminded of existing key; {d}d {h}h {m}m left.",
                discord.Color.orange()
            )
            return

        # cooldown passed: clear so we can dispense a fresh key
        user_data.pop("dispensed_key", None)
        user_data.pop("last_dispensed_at", None)
        db[user_key] = user_data


    # 6) Low-pool alert
    left = sum(1 for k in db if k.startswith("key:"))
    if left <= LOW_POOL_THRESHOLD and not db.get("warned_low_pool"):
        db["warned_low_pool"] = True
        await notify_staff(
            "🚨 Low Key Pool",
            f"{LOW_POOL_PING}, only **{left}** keys remain!",
            discord.Color.red()
        )
    elif left > LOW_POOL_THRESHOLD and db.get("warned_low_pool"):
        del db["warned_low_pool"]

    # 7) Dispense loop with brief lock
    db["frozen"] = True
    try:
        for k in list(db.keys()):
            if k.startswith("key:"):
                key_str = k.split("key:")[1]
                # Assign to user & remove from pool
                user_data["dispensed_key"]     = key_str
                user_data["last_dispensed_at"] = now.isoformat()
                db[user_key] = user_data
                del db[k]

                try:
                    await interaction.user.send(
                        f"🎉 Here’s your trial key:\n**{key_str}**\n"
                        f"Next in {cd_days} days."
                    )
                    await interaction.followup.send(
                        "✅ Trial key sent via DM!", ephemeral=True
                    )
                    await notify_staff(
                        "🔑 Key Dispensed",
                        f"{interaction.user.mention} was issued **{key_str}**.",
                        discord.Color.green()
                    )
                except discord.Forbidden:
                    await interaction.followup.send(
                        "⚠️ Please open your DMs so I can send your key.",
                        ephemeral=True
                    )
                    await notify_staff(
                        "📭 DM Delivery Failed",
                        f"Could not DM {interaction.user.mention} **{key_str}**.",
                        discord.Color.orange()
                    )
                return

        # Pool exhausted
        await interaction.followup.send(
            "❌ All trial keys claimed—check back later or message staff.",
            ephemeral=True
        )
        await notify_staff(
            "❌ Pool Exhausted",
            f"{interaction.user.mention} attempted to claim but no keys left.",
            discord.Color.red()
        )
    finally:
        db["frozen"] = False


# ── Admin: List available keys only ──
@tree.command(
    name="list_keys",
    description="📜 List all available keys",
)
@is_staff()
@app_commands.guild_only()
async def list_keys(interaction: discord.Interaction):
    # Fetch all remaining keys
    available = [k.split("key:")[1] for k in db if k.startswith("key:")]
    count     = len(available)

    # Build an embed with one key per line, prefixed by '-'
    embed = discord.Embed(
        title=f"🔑 Available Keys ({count})",
        description="\n".join(f"- {key}" for key in available) or "None",
        color=discord.Color.blurple()
    )

    # Send it ephemerally to the admin
    await interaction.response.send_message(embed=embed, ephemeral=True)

    # Log to staff channel
    await notify_staff(
        "📜 Keys Queried",
        f"{interaction.user.mention} ran /list_keys; {count} keys remaining.",
        discord.Color.blue()
    )


# ── Admin: Set cooldown ──
@tree.command(name="set_cooldown_days", description="⏲️ Set trial cooldown")
@is_staff()
@app_commands.guild_only()
async def set_cooldown_days(interaction: discord.Interaction, days: int):
    if not 0 <= days <= 365:
        return await interaction.response.send_message("❌ Days must be 0–365.", ephemeral=True)
    db["config:cooldown_days"] = days
    await interaction.response.send_message(f"✅ Cooldown set to {days} days.", ephemeral=True)
    await notify_staff(
        "⏲️ Cooldown Updated",
        f"{interaction.user.mention} set cooldown to {days} days.",
        discord.Color.green()
    )


# ── Admin: Freeze / Unfreeze ──
@tree.command(name="freeze", description="⏸️ Pause key disbursement")
@is_staff()
@app_commands.guild_only()
async def freeze(interaction: discord.Interaction):
    db["frozen"] = True
    await interaction.response.send_message("🔒 Disbursement frozen.", ephemeral=True)
    await notify_staff(
        "🔒 Disbursement Frozen",
        f"{interaction.user.mention} paused key distribution.",
        discord.Color.red()
    )

@tree.command(name="unfreeze", description="▶️ Resume key disbursement")
@is_staff()
@app_commands.guild_only()
async def unfreeze(interaction: discord.Interaction):
    db["frozen"] = False
    await interaction.response.send_message("🔓 Disbursement resumed.", ephemeral=True)
    await notify_staff(
        "🔓 Disbursement Resumed",
        f"{interaction.user.mention} resumed key distribution.",
        discord.Color.green()
    )


# ── Admin: Add trial keys ──
@tree.command(name="add_keys", description="➕ Add trial keys (comma-separated)")
@is_staff()
@app_commands.guild_only()
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
            db[db_key] = {}
            added += 1

    msg = f"✅ Added {added} keys."
    if skipped: msg += f" Skipped {skipped} duplicates."
    if invalid: msg += f" Ignored {invalid} invalid."
    await interaction.response.send_message(msg, ephemeral=True)
    await notify_staff(
        "➕ Keys Added",
        f"{interaction.user.mention} added {added} keys; skipped {skipped}; invalid {invalid}.",
        discord.Color.green()
    )


# ── Admin: Delete All Keys ──
@tree.command(name="delete_all_keys", description="🗑️ Wipe all keys")
@is_staff()
@app_commands.guild_only()
async def delete_all_keys(interaction: discord.Interaction):
    # Remove every “key:” entry from the DB
    count = 0
    for k in list(db.keys()):
        if k.startswith("key:"):
            db.pop(k, None)
            count += 1

    await interaction.response.send_message(f"🧨 Deleted {count} keys.", ephemeral=True)
    await notify_staff(
        "🧨 All Keys Wiped",
        f"{interaction.user.mention} deleted {count} keys from DB.",
        discord.Color.red()
    )


# ── Admin: Status ──
@tree.command(name="status", description="📊 Show key-distribution status")
@is_staff()
@app_commands.guild_only()
async def status(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    now = datetime.now(timezone.utc)

    # 1) Purge stale OAuth states
    for key in list(db.keys()):
        if key.startswith("state:"):
            entry = db[key]
            if isinstance(entry, dict) and "created_at" in entry:
                created = parse_iso(entry["created_at"])
                if now - created > timedelta(hours=STATE_TTL_HOURS):
                    del db[key]
            else:
                del db[key]

    # 2) Metrics
    remaining = sum(1 for k in db if k.startswith("key:"))
    disp24 = disp7 = 0
    for k, v in db.items():
        if k.startswith("user:") and "last_dispensed_at" in v:
            delta = now - parse_iso(v["last_dispensed_at"])
            if delta <= timedelta(days=1):
                disp24 += 1
            if delta <= timedelta(days=7):
                disp7 += 1

    frozen = db.get("frozen", False)

    # 3) Single-embed response
    embed = discord.Embed(
        title="SkySpoofer Key Distribution Status",
        description=(
            f"**Remaining Keys:** {remaining}\n"
            f"**Frozen:** {'Yes' if frozen else 'No'}"
        ),
        color=discord.Color.blurple()
    )
    await interaction.followup.send(embed=embed, ephemeral=True)
    await notify_staff(
        "📊 Admin Queried Status",
        f"{interaction.user.mention} ran /status (stale states purged).",
        discord.Color.blue()
    )


# ── Admin: Unlink User ──
@tree.command(name="unlink", description="🔄 Unlink a user")
@is_staff()
@app_commands.guild_only()
async def unlink(
    interaction: discord.Interaction,
    user: Optional[discord.Member] = None
):
    target = user or interaction.user
    ukey   = f"user:{target.id}"

    if ukey in db:
        # Only remove the user record; keys were already deleted on dispense
        del db[ukey]

        await interaction.response.send_message(
            f"🔄 Unlinked {target.mention}.",
            ephemeral=True
        )
        await notify_staff(
            "🔄 User Unlinked",
            f"{interaction.user.mention} unlinked {target.mention}.",
            discord.Color.orange()
        )
    else:
        await interaction.response.send_message(
            f"ℹ️ {target.mention} not linked.",
            ephemeral=True
        )


# ── Entrypoint ──
def run_bot():
    bot.run(BOT_TOKEN)
