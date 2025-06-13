
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from config import LOGGER_ID as LOG_ID
from AnonXMusic import app
from AnonXMusic.misc import SUDOERS
from AnonXMusic.utils.inline import close_markup
from AnonXMusic.utils.decorators.language import language
from AnonXMusic.utils.database import get_active_chats, get_active_video_chats

@app.on_message(filters.new_chat_members)
async def on_new_chat_members(_, message: Message):
    if app.id in [user.id for user in message.new_chat_members]:
        added_by = message.from_user.mention if message.from_user else "ᴜɴᴋɴᴏᴡɴ ᴜsᴇʀ"
        username = f"@{message.chat.username}" if message.chat.username else None
        riruru = f"✫ <b><u>#New ɢʀᴏᴜᴘ</u></b> :\n\nᴄʜᴀᴛ ɪᴅ : {message.chat.id}\nᴄʜᴀᴛ ᴜsᴇʀɴᴀᴍᴇ : {username}\nᴄʜᴀᴛ ᴛɪᴛʟᴇ : {message.chat.title}\n\nᴀᴅᴅᴇᴅ ʙʏ : {added_by}"
        butt = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=message.from_user.first_name,
                        user_id=message.from_user.id,
                    )
                ]
            ]
        )
        try:
            await app.send_message(chat_id=LOG_ID, text=riruru, reply_markup=butt)
        except:
            pass

@app.on_message(filters.left_chat_member)
async def on_left_chat_member(client: Client, message: Message):
    if app.id == message.left_chat_member.id:
        remove_by = message.from_user.mention if message.from_user else "ᴜɴᴋɴᴏᴡɴ ᴜsᴇʀ"
        username = f"@{message.chat.username}" if message.chat.username else None
        riruru = f"✫ <b><u>#Left ɢʀᴏᴜᴘ</u></b> :\n\nᴄʜᴀᴛ ɪᴅ : {message.chat.id}\nᴄʜᴀᴛ ᴜsᴇʀɴᴀᴍᴇ : {username}\nᴄʜᴀᴛ ᴛɪᴛʟᴇ : {message.chat.title}\n\nʀᴇᴍᴏᴠᴇᴅ ʙʏ : {remove_by}"
        butt = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=message.from_user.first_name,
                        user_id=message.from_user.id,
                    )
                ]
            ]
        )
        try:
            await app.send_message(chat_id=LOG_ID, text=riruru, reply_markup=butt)
        except:
            pass

@app.on_message(filters.command("ac") & SUDOERS)
@language
async def check_vc(client, message: Message, _):
    ac = len(await get_active_chats())
    vc = len(await get_active_video_chats())
    butt = close_markup(_)
    await message.reply_text(
        text=f"<u><b>✫ ᴀᴄᴛɪᴠᴇ ᴄʜᴀᴛs ɪɴғᴏ :</b></u>\n\nTotal : <code>{ac}</code>\nVideo  : <code>{vc}</code>",
        reply_markup=butt,
)
