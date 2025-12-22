import discord
from discord.ext import tasks
from discord import app_commands
import datetime
import asyncio
import os
from flask import Flask
import threading

ALLOWED_USERS = [
    536238884359503894,
    853310319002517524
]

NUKE_HOUR = 7
AUTO_NUKE_ENABLED = True
LOG_FILE = "nuke_logs.txt"

SAFE_CHANNEL_IDS = [
    1447326481964339210,
    1447326481964339213,
    1447331680879906981,
    1447367888930607245
]

LOG_CHANNEL_ID = 1447326481964339213

intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True
intents.messages = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

def write_log(text: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {text}\n")

def get_time_until_next_nuke():
    now = datetime.datetime.now()
    next_nuke = now.replace(hour=NUKE_HOUR, minute=0, second=0, microsecond=0)
    if now >= next_nuke:
        next_nuke += datetime.timedelta(days=1)
    delta = next_nuke - now
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return delta.days, hours, minutes

async def duplicate_channel(ch: discord.abc.GuildChannel):
    overwrites = ch.overwrites
    if isinstance(ch, discord.TextChannel):
        clone = await ch.guild.create_text_channel(
            name=ch.name,
            category=ch.category,
            topic=ch.topic,
            slowmode_delay=ch.slowmode_delay,
            nsfw=ch.nsfw,
            overwrites=overwrites
        )
    elif isinstance(ch, discord.VoiceChannel):
        clone = await ch.guild.create_voice_channel(
            name=ch.name,
            category=ch.category,
            bitrate=ch.bitrate,
            user_limit=ch.user_limit,
            overwrites=overwrites
        )
    else:
        return None
    await clone.edit(position=ch.position)
    return clone

async def nuke_guild(guild: discord.Guild, auto=False):
    write_log(f"Nuke started for {guild.name} | AUTO={auto}")
    old_to_new = {}
    to_delete = []

    for ch in guild.channels:
        if ch.id in SAFE_CHANNEL_IDS:
            continue
        clone = await duplicate_channel(ch)
        if clone:
            old_to_new[ch.id] = clone.id
            to_delete.append(ch)
        await asyncio.sleep(0.8)

    for ch in to_delete:
        try:
            await ch.delete()
        except:
            pass
        await asyncio.sleep(0.8)

    gif_url = "https://cdn.discordapp.com/attachments/1253256583132217348/1390853665535033434/togif.gif"
    for new_id in old_to_new.values():
        ch = guild.get_channel(new_id)
        if isinstance(ch, discord.TextChannel):
            try:
                await ch.send(f"_ _\n{gif_url}")
            except:
                pass

    for old, new in old_to_new.items():
        write_log(f"Channel {old} -> {new}")

    log_ch = guild.get_channel(LOG_CHANNEL_ID)
    if log_ch:
        await log_ch.send(
            f"💥 **NUKE COMPLETE** ({'AUTO' if auto else 'MANUAL'})\n"
            f"Channels nuked: {len(old_to_new)}"
        )

    write_log(f"Nuke finished for {guild.name}")

@bot.event
async def on_ready():
    await tree.sync()
    daily_nuke.start()

@tasks.loop(minutes=1)
async def daily_nuke():
    if not AUTO_NUKE_ENABLED:
        return
    now = datetime.datetime.now()
    if now.hour == NUKE_HOUR and now.minute == 0:
        for guild in bot.guilds:
            await nuke_guild(guild, auto=True)

FUNNY_MESSAGES = [
    "U TRYNA NUKE MY SERVER SON?",
    "NAH BRO WHO GAVE YOU PERMISSION 💀"
]

async def send_no_permission_response(interaction):
    await interaction.response.send_message("SNAKE.", ephemeral=False)
    try:
        for msg in FUNNY_MESSAGES:
            await interaction.user.send(msg)
            await asyncio.sleep(0.5)
    except:
        pass

@tree.command(name="nuke_now")
async def nuke_now(interaction: discord.Interaction):
    if interaction.user.id not in ALLOWED_USERS:
        await send_no_permission_response(interaction)
        return
    await interaction.response.send_message("🔥 Nuking server now...")
    await nuke_guild(interaction.guild, auto=False)

@tree.command(name="nuke_pause")
async def nuke_pause(interaction: discord.Interaction):
    global AUTO_NUKE_ENABLED
    if interaction.user.id not in ALLOWED_USERS:
        await send_no_permission_response(interaction)
        return
    AUTO_NUKE_ENABLED = not AUTO_NUKE_ENABLED
    status = "PAUSED" if not AUTO_NUKE_ENABLED else "ENABLED"
    write_log(f"Auto nuke toggled: {status} by {interaction.user}")
    await interaction.response.send_message(
        f"⚙️ Automatic nukes are now **{status}**"
    )

@tree.command(name="nuke_timer")
async def nuke_timer(interaction: discord.Interaction):
    days, hours, minutes = get_time_until_next_nuke()
    status = "ENABLED" if AUTO_NUKE_ENABLED else "PAUSED"
    await interaction.response.send_message(
        f"⏱️ **Next Nuke In:** {days}d {hours}h {minutes}m\n"
        f"⚙️ Auto Nuke Status: **{status}**"
    )

@tree.command(name="ping")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"Pong! {latency}ms")

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot alive"

def run_web():
    app.run(host="0.0.0.0", port=8080)

threading.Thread(target=run_web, daemon=True).start()

token = os.environ.get("DISCORD_BOT_TOKEN")
if token:
    bot.run(token)
else:
    print("DISCORD_BOT_TOKEN missing")
