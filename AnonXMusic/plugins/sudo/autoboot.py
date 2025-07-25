import asyncio
import os
import shutil

from pyrogram import filters
from AnonXMusic import app
from AnonXMusic.misc import SUDOERS
from AnonXMusic.utils.database import get_active_chats, remove_active_chat, remove_active_video_chat

auto_restart_task: asyncio.Task | None = None  # Global task reference

async def restart_bot():
    ac_chats = await get_active_chats()
    for x in ac_chats:
        try:
            await app.send_message(
                chat_id=int(x),
                text=f"<blockquote><b>{app.mention} ɪꜱ ʀᴇʙᴏᴏᴛɪɴɢ ᴛᴏ ᴇɴꜱᴜʀᴇ ꜱᴍᴏᴏᴛʜ ᴘʟᴀʏʙᴀᴄᴋ 🎵\n\nʜᴏʟᴅ ᴏɴ ꜰᴏʀ ᴀ ᴍᴏᴍᴇɴᴛ, ᴀɴᴅ ʏᴏᴜ’ʟʟ ʙᴇ ʙᴀᴄᴋ ᴛᴏ ᴇɴᴊᴏʏɪɴɢ ʏᴏᴜʀ ᴍᴜꜱɪᴄ ɪɴ ɴᴏ ᴛɪᴍᴇ!</b></blockquote>",
            )
            await remove_active_chat(x)
            await remove_active_video_chat(x)
        except:
            pass

    # Clean up
    for folder in ["downloads", "raw_files", "cache"]:
        try:
            shutil.rmtree(folder)
        except:
            pass

    os.system(f"kill -9 {os.getpid()} && bash start")


async def auto_restart(minutes: int):
    await asyncio.sleep(minutes * 60)
    await restart_bot()


@app.on_message(filters.command("autoboot") & SUDOERS)
async def start_auto_restart(_, message):
    global auto_restart_task

    if auto_restart_task and not auto_restart_task.done():
        await message.reply_text("<b>✅ Auto-restart is already running.</b>")
        return

    if len(message.command) < 2 or not message.command[1].isdigit():
        return await message.reply_text("<b>❌ Usage: /autoboot &lt;minutes&gt;</b>")

    minutes = int(message.command[1])
    if minutes < 1:
        return await message.reply_text("<b>❌ Minimum value is 1 minute.</b>")

    auto_restart_task = asyncio.create_task(auto_restart(minutes))
    await message.reply_text(
        f"<b>✅ Auto-restart started.\n\n⏳ Bot will restart after {minutes} minute(s).</b>"
    )


@app.on_message(filters.command("sautoboot") & SUDOERS)
async def stop_auto_restart(_, message):
    global auto_restart_task

    if auto_restart_task and not auto_restart_task.done():
        auto_restart_task.cancel()
        auto_restart_task = None
        return await message.reply_text("<b>🛑 Auto-restart task has been stopped.</b>")
    await message.reply_text("<b>⚠️ No auto-restart task is currently running.</b>")


@app.on_message(filters.command("rboot") & SUDOERS)
async def reset_boot(_, message):
    global auto_restart_task

    if auto_restart_task and not auto_restart_task.done():
        auto_restart_task.cancel()

    auto_restart_task = asyncio.create_task(auto_restart(120))
    await message.reply_text(
        "<b>🔄 Restart timer has been reset.\n\n⏳ Bot will now restart after 2 hours (default).</b>"
    )
