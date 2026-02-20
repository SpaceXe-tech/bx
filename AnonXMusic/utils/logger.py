from AnonXMusic import app
from AnonXMusic.misc import SUDOERS
from AnonXMusic.utils.database import is_on_off
from config import LOGGER_ID


async def play_logs(message, streamtype):
    if not await is_on_off(2):
        return

    if not message.from_user:
        return

    if message.from_user.id in SUDOERS:
        return

    text = message.text or ""
    parts = text.split(None, 1)
    query = parts[1] if len(parts) > 1 else ""

    user = message.from_user
    chat = message.chat

    if user.username:
        user_ref = f"@{user.username}"
    else:
        user_ref = f"tg://user?id={user.id}"

    if chat.username:
        chat_ref = f"https://t.me/{chat.username}"
    else:
        chat_ref = f"{chat.id}"

    logger_text = (
        f"{app.mention} play log\n\n"
        f"Chat: {chat.title} ({chat_ref})\n"
        f"Chat ID: {chat.id}\n\n"
        f"User: {user.first_name} ({user_ref})\n"
        f"User ID: {user.id}\n\n"
        f"Query: {query}\n"
        f"Stream type: {streamtype}"
    )

    if chat.id == LOGGER_ID:
        return

    try:
        await app.send_message(
            chat_id=LOGGER_ID,
            text=logger_text,
            disable_web_page_preview=True,
        )
    except:
        return
