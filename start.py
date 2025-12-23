import discord
from discord.ext import tasks
from discord import app_commands
import datetime
import asyncio
import os
from flask import Flask
import threading

OWNER_ID = 853310319002517524

ALLOWED_USERS = [
    536238884359503894,
    853310319002517524
]

NUKE_HOUR = 7
AUTO_NUKE_ENABLED = True

SAFE_CHANNEL_IDS = [
    1447326481964339210,
    1447326481964339213,
    1447331680879906981,
    1447367888930607245
]

LOG_CHANNEL_ID = 1447326481964339213
MAX_DM_LENGTH = 1900

intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.guild_messages = True
intents.members = True
intents.message_content = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

async def send_dm_log(text: str):
    user = bot.get_user(OWNER_ID)
    if not user:
        return
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full = f"[{timestamp}]\n{text}"
    for i in range(0, len(full), MAX_DM_LENGTH):
        await user.send(f"```{full[i:i+MAX_DM_LENGTH]}```")

def get_time_until_next_nuke():
    now = datetime.datetime.now()
    next_nuke = now.replace(hour=NUKE_HOUR, minute=0, second=0, microsecond=0)
    if now >= next_nuke:
        next_nuke += datetime.timedelta(days=1)
    delta = next_nuke - now
    h, r = divmod(delta.seconds, 3600)
    m, _ = divmod(r, 60)
    return delta.days, h, m

async def duplicate_channel(ch):
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

async def dump_audit_logs(guild):
    logs = []
    async for entry in guild.audit_logs(limit=50):
        logs.append(
            f"""
ACTION: {entry.action}
USER: {entry.user} ({entry.user.id if entry.user else "Unknown"})
TARGET: {entry.target}
REASON: {entry.reason}
TIME: {entry.created_at}
"""
        )
    if logs:
        await send_dm_log("AUDIT LOG DUMP\n" + "\n".join(logs))

async def nuke_guild(guild, auto=False):
    await send_dm_log(
        f"""
NUKE STARTED
Guild: {guild.name}
ID: {guild.id}
Owner: {guild.owner} ({guild.owner_id})
Members: {guild.member_count}
Auto: {auto}
"""
    )

    old_to_new = {}
    to_delete = []

    for ch in guild.channels:
        if ch.id in SAFE_CHANNEL_IDS:
            continue
        clone = await duplicate_channel(ch)
        if clone:
            old_to_new[ch.id] = clone.id
            to_delete.append(ch)
            await send_dm_log(
                f"""
CHANNEL CLONED
Name: {ch.name}
Old ID: {ch.id}
New ID: {clone.id}
Type: {type(ch).__name__}
Category: {ch.category}
"""
            )
        await asyncio.sleep(0.8)

    for ch in to_delete:
        try:
            await ch.delete()
            await send_dm_log(
                f"""
CHANNEL DELETED
Name: {ch.name}
ID: {ch.id}
Type: {type(ch).__name__}
"""
            )
        except Exception as e:
            await send_dm_log(f"DELETE FAILED {ch.name} | {e}")
        await asyncio.sleep(0.8)

    gif_url = "https://cdn.discordapp.com/attachments/1253256583132217348/1390853665535033434/togif.gif"

    for new_id in old_to_new.values():
        ch = guild.get_channel(new_id)
        if isinstance(ch, discord.TextChannel):
            try:
                await ch.send(f"_ _\n{gif_url}")
            except:
                pass

    await dump_audit_logs(guild)

    await send_dm_log(
        f"""
NUKE FINISHED
Guild: {guild.name}
Channels Nuked: {len(old_to_new)}
Auto: {auto}
"""
    )

@bot.event
async def on_ready():
    await tree.sync()
    daily_nuke.start()
    await send_dm_log(f"BOT ONLINE {bot.user}")

@tasks.loop(minutes=1)
async def daily_nuke():
    if not AUTO_NUKE_ENABLED:
        return
    now = datetime.datetime.now()
    if now.hour == NUKE_HOUR and now.minute == 0:
        for guild in bot.guilds:
            await nuke_guild(guild, auto=True)

@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    await send_dm_log(
        f"""
MESSAGE DELETED
Author: {message.author} ({message.author.id})
Channel: {message.channel} ({message.channel.id})
Content:
{message.content}
"""
    )

@bot.event
async def on_message_edit(before, after):
    if before.author.bot:
        return
    await send_dm_log(
        f"""
MESSAGE EDITED
Author: {before.author} ({before.author.id})
Channel: {before.channel}
BEFORE:
{before.content}

AFTER:
{after.content}
"""
    )

@bot.event
async def on_member_join(member):
    await send_dm_log(f"MEMBER JOINED {member} ({member.id}) {member.created_at}")

@bot.event
async def on_member_remove(member):
    await send_dm_log(f"MEMBER LEFT {member} ({member.id})")

async def no_perm(interaction):
    await interaction.response.send_message("SNAKE.", ephemeral=False)
    try:
        await interaction.user.send("U TRYNA NUKE MY SERVER SON?")
    except:
        pass

@tree.command(name="nuke_now")
async def nuke_now(interaction: discord.Interaction):
    if interaction.user.id not in ALLOWED_USERS:
        await no_perm(interaction)
        return
    await interaction.response.send_message("Nuking server...")
    await nuke_guild(interaction.guild, auto=False)

@tree.command(name="nuke_pause")
async def nuke_pause(interaction: discord.Interaction):
    global AUTO_NUKE_ENABLED
    if interaction.user.id not in ALLOWED_USERS:
        await no_perm(interaction)
        return
    AUTO_NUKE_ENABLED = not AUTO_NUKE_ENABLED
    await interaction.response.send_message(
        f"Auto Nuke {'ENABLED' if AUTO_NUKE_ENABLED else 'PAUSED'}"
    )

@tree.command(name="nuke_timer")
async def nuke_timer(interaction: discord.Interaction):
    d, h, m = get_time_until_next_nuke()
    await interaction.response.send_message(
        f"Next nuke in {d}d {h}h {m}m | Auto {'ENABLED' if AUTO_NUKE_ENABLED else 'PAUSED'}"
    )

@tree.command(name="ping")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong {round(bot.latency*1000)}ms")

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
