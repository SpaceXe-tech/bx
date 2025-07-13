from pyrogram import filters
from pyrogram.types import Message
from typing import Union, List
import asyncio

from AnonXMusic import app
from AnonXMusic.core.call import Anony

# Toggle VC notifications
infovc_enabled = True

# Command decorator
def command(commands: Union[str, List[str]]):
    return filters.command(commands, prefixes=["/"])

# Toggle VC join/leave notifications
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

# Format join/leave message
def format_user(user, action: str):
    full_name = user.first_name + (f" {user.last_name}" if user.last_name else "")
    return (
        "**🎙️ Voice Chat Is Active — Where Are You?**\n"
        "`#Join_Vc`\n"
        f"**👤 User**: [{full_name}](tg://user?id={user.id})\n"
        f"**🔗 Username**: @{user.username if user.username else 'N/A'}\n"
        f"**🎯 Action**: {action}"
    )

# Handle VC join
@Anony.on_participant_joined()
async def on_participant_joined(_, chat_id: int, user):
    if not infovc_enabled:
        return
    try:
        msg = await app.send_message(chat_id, format_user(user.user, "Joined"))
        await asyncio.sleep(5)
        await msg.delete()
    except Exception as e:
        print(f"[VC JOIN ERROR] in {chat_id} — {e}")

# Handle VC leave
@Anony.on_participant_left()
async def on_participant_left(_, chat_id: int, user):
    if not infovc_enabled:
        return
    try:
        msg = await app.send_message(chat_id, format_user(user.user, "Left"))
        await asyncio.sleep(5)
        await msg.delete()
    except Exception as e:
        print(f"[VC LEAVE ERROR] in {chat_id} — {e}")
