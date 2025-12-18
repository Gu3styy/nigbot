import discord
from discord.ext import tasks
from discord import app_commands
import datetime
import asyncio
import os

ALLOWED_USERS = [
    536238884359503894,  # matito
    853310319002517524
]
NUKE_HOUR = 7  # 08:00 every day

SAFE_CHANNEL_IDS = [
    1447326481964339210, 1447326481964339213, 1447331680879906981,
    1447367888930607245
]

LOG_CHANNEL_ID = 1447326481964339213

intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True
intents.messages = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)


async def safe_edit(channel, **kwargs):
    """Retry edits if hitting rate limits."""
    while True:
        try:
            return await channel.edit(**kwargs)
        except discord.HTTPException as e:
            if e.status == 429:
                await asyncio.sleep(getattr(e, "retry_after", 2))
            else:
                raise


async def duplicate_channel(ch: discord.abc.GuildChannel):
    """Duplicate a text or voice channel like Discord client 'Duplicate'."""
    overwrites = ch.overwrites

    if isinstance(ch, discord.TextChannel):
        clone = await ch.guild.create_text_channel(
            name=ch.name,
            category=ch.category,
            topic=getattr(ch, "topic", None),
            slowmode_delay=getattr(ch, "slowmode_delay", 0),
            nsfw=getattr(ch, "nsfw", False),
            overwrites=overwrites,
            reason="Duplicated like Discord client")
    elif isinstance(ch, discord.VoiceChannel):
        clone = await ch.guild.create_voice_channel(
            name=ch.name,
            category=ch.category,
            bitrate=getattr(ch, "bitrate", 64000),
            user_limit=getattr(ch, "user_limit", 0),
            overwrites=overwrites,
            reason="Duplicated like Discord client")
    else:
        return None

    # Keep the same position in category
    await clone.edit(position=ch.position)
    return clone


async def nuke_guild(guild: discord.Guild, auto=False):
    print(f"[DEBUG] 🚀 Nuke started for guild: {guild.name}")
    log_channel = guild.get_channel(LOG_CHANNEL_ID)
    to_delete = []
    old_to_new = {}

    # Step 1 — Duplicate all non-safe channels
    for ch in guild.channels:
        if ch.id in SAFE_CHANNEL_IDS:
            print(f"[DEBUG] Skipping safe: {ch.name}")
            continue

        print(f"[DEBUG] Duplicating {ch.name}")
        clone = await duplicate_channel(ch)
        if clone:
            old_to_new[ch.id] = clone.id
            to_delete.append(ch)
        await asyncio.sleep(0.8)

    # Step 2 — Delete old channels
    for ch in to_delete:
        print(f"[DEBUG] Deleting old: {ch.name}")
        try:
            await ch.delete(reason="Daily nuke")
        except:
            pass
        await asyncio.sleep(0.8)

    # Step 3 — Send a fun message + GIF to nuked channels
    GIF_URL = "https://cdn.discordapp.com/attachments/1253256583132217348/1390853665535033434/togif.gif?ex=6942a3aa&is=6941522a&hm=a0bfac54b6a4816a6a1023dca30054ce478a003c7087319f896dc4678362331d&"  # example explosion GIF
    MESSAGE = "_ _"

    for new_channel_id in old_to_new.values():
        new_ch = guild.get_channel(new_channel_id)
        if isinstance(new_ch, discord.TextChannel):
            try:
                await new_ch.send(f"{MESSAGE}\n{GIF_URL}")
            except:
                pass
        await asyncio.sleep(0.5)

    # Step 4 — Log
    if log_channel:
        await log_channel.send(
            f"💥 **Server Nuked** ({'AUTO' if auto else 'MANUAL'})\n"
            f"Old → New ID mapping:\n" +
            "\n".join(f"{old} → {new}" for old, new in old_to_new.items()))

    print(f"[DEBUG] ✅ Nuke finished for guild: {guild.name}")


@bot.event
async def on_ready():
    print(f"[DEBUG] Logged in as {bot.user}")
    await tree.sync()
    daily_nuke.start()


@tasks.loop(minutes=1)
async def daily_nuke():
    now = datetime.datetime.now()
    if now.hour == NUKE_HOUR and now.minute == 0:
        for guild in bot.guilds:
            await nuke_guild(guild, auto=True)


# -------------------- SLASH COMMANDS -------------------- #

FUNNY_MESSAGES = [
    "U TRYNA NUKE MY SERVER SON?", "NAH BRO WHO GAVE YOU PERMISSION 💀"
]


async def send_no_permission_response(interaction: discord.Interaction):
    await interaction.response.send_message("SNAKE.", ephemeral=False)
    try:
        for msg in FUNNY_MESSAGES:
            await interaction.user.send(msg)
            await asyncio.sleep(0.5)
    except:
        pass


@tree.command(name="nuke_now", description="Nuke the server immediately")
async def nuke_now(interaction: discord.Interaction):
    if interaction.user.id not in ALLOWED_USERS:
        await send_no_permission_response(interaction)
        return
    await interaction.response.send_message("🔥 Nuking server now...",
                                            ephemeral=False)
    await nuke_guild(interaction.guild, auto=False)


@tree.command(name="nuke_preview",
              description="Preview which channels will be nuked")
async def nuke_preview(interaction: discord.Interaction):
    if interaction.user.id not in ALLOWED_USERS:
        await send_no_permission_response(interaction)
        return
    nuked = [
        c.mention for c in interaction.guild.channels
        if c.id not in SAFE_CHANNEL_IDS
    ]
    safe = [
        c.mention for c in interaction.guild.channels
        if c.id in SAFE_CHANNEL_IDS
    ]

    embed = discord.Embed(title="💣 Nuke Preview", color=discord.Color.red())
    embed.add_field(name="Will be deleted:",
                    value="\n".join(nuked) or "None",
                    inline=False)
    embed.add_field(name="Safe channels:", value="\n".join(safe), inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=False)


@tree.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"Pong! {latency}ms")

from flask import Flask
import threading

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot alive"

def run_web():
    app.run(host="0.0.0.0", port=8080)

threading.Thread(target=run_web).start()


token = os.environ.get('DISCORD_BOT_TOKEN')
if not token:
    print("Error: DISCORD_BOT_TOKEN not found. Please add it to Secrets.")
else:
    bot.run(token)
