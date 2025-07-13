from pyrogram import filters
from pyrogram.types import Message
from typing import Union, List
import asyncio

from AnonXMusic import app
from AnonXMusic.core.call import Anony

from ntgcalls.types import GroupCallParticipant
from ntgcalls.types.events import GroupCallParticipantJoined, GroupCallParticipantLeft

# Toggle state for VC notifications
infovc_enabled = True

# Helper command decorator
def command(commands: Union[str, List[str]]):
    return filters.command(commands, prefixes=["/"])

# Toggle command
@app.on_message(command(["infovc"]))
async def toggle_infovc(_, message: Message):
    global infovc_enabled
    if len(message.command) > 1:
        state = message.command[1].lower()
        if state == "on":
            infovc_enabled = True
            await message.reply("✅ VC join/leave notifications enabled.")
        elif state == "off":
            infovc_enabled = False
            await message.reply("🔕 VC join/leave notifications disabled.")
        else:
            await message.reply("⚠️ Usage: /infovc on or /infovc off")
    else:
        await message.reply("⚙️ Usage: /infovc on or /infovc off")

# Message format
def format_user(user_id: int, username: str, full_name: str, action: str):
    return (
        "**Voice Chat Is Active Where Are You?**\n"
        "`#Join Vc`\n"
        f"**User**: [{full_name}](tg://user?id={user_id})\n"
        f"**Username**: @{username if username else 'N/A'}\n"
        f"**Action**: {action}"
    )

# Handler for VC Join
@Anony.on_participant_joined()
async def on_participant_joined(_, chat_id: int, user: GroupCallParticipantJoined):
    if not infovc_enabled:
        return
    try:
        u = user.user
        full_name = u.first_name + (f" {u.last_name}" if u.last_name else "")
        msg = await app.send_message(
            chat_id,
            format_user(u.id, u.username, full_name, "Joined")
        )
        await asyncio.sleep(5)
        await msg.delete()
    except Exception as e:
        print(f"[VC JOIN ERROR] {chat_id}: {e}")

# Handler for VC Leave
@Anony.on_participant_left()
async def on_participant_left(_, chat_id: int, user: GroupCallParticipantLeft):
    if not infovc_enabled:
        return
    try:
        u = user.user
        full_name = u.first_name + (f" {u.last_name}" if u.last_name else "")
        msg = await app.send_message(
            chat_id,
            format_user(u.id, u.username, full_name, "Left")
        )
        await asyncio.sleep(5)
        await msg.delete()
    except Exception as e:
        print(f"[VC LEAVE ERROR] {chat_id}: {e}")
