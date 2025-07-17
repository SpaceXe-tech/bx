import asyncio
from datetime import datetime
from pyrogram.enums import ChatType
from pyrogram.errors import FloodWait, RPCError, PeerIdInvalid

import config
from AnonXMusic import app
from AnonXMusic.core.call import Anony, autoend
from AnonXMusic.utils.database import get_client, is_active_chat, is_autoend

# Cache for support/chat/channel IDs
SUPPORT_IDS = set()


def extract_username(link: str) -> str:
    """Extracts username from full t.me links or @usernames."""
    if not link:
        return None
    if link.startswith("https://t.me/"):
        return link.rsplit("/", 1)[-1]
    return link.lstrip("@")


async def resolve_support_ids():
    """Resolve SUPPORT_CHAT and SUPPORT_CHANNEL into IDs only once."""
    global SUPPORT_IDS
    links = [config.SUPPORT_CHAT, config.SUPPORT_CHANNEL]
    for link in links:
        username = extract_username(link)
        if not username:
            continue
        try:
            chat = await app.get_chat(username)
            SUPPORT_IDS.add(chat.id)
        except PeerIdInvalid:
            print(f"[WARN] Invalid support username: {username}")
        except Exception as e:
            print(f"[ERROR] Could not resolve {link}: {e}")


async def auto_leave():
    """Assistant clients leave unused inactive groups every 15 minutes."""
    await resolve_support_ids()
    if not config.AUTO_LEAVING_ASSISTANT:
        return

    while True:
        await asyncio.sleep(900)  # every 15 minutes
        from AnonXMusic.core.userbot import assistants

        for num in assistants:
            try:
                client = await get_client(num)
                left_count = 0
                async for dialog in client.get_dialogs():
                    chat = dialog.chat

                    if chat.type not in [ChatType.SUPERGROUP, ChatType.GROUP, ChatType.CHANNEL]:
                        continue

                    if chat.id in SUPPORT_IDS or chat.id == config.LOGGER_ID:
                        continue  # don't leave support/log chats

                    if await is_active_chat(chat.id):
                        continue  # chat is actively using music

                    if left_count >= 20:
                        break

                    try:
                        await client.leave_chat(chat.id)
                        left_count += 1
                        print(f"[LEAVE] Assistant {num} left: {chat.title or chat.id}")
                    except FloodWait as e:
                        print(f"[FLOODWAIT] Sleeping for {e.value}s")
                        await asyncio.sleep(e.value)
                    except RPCError as e:
                        print(f"[RPC ERROR] Could not leave {chat.id}: {e}")
                    except Exception as e:
                        print(f"[ERROR] Unexpected error while leaving: {e}")
            except Exception as e:
                print(f"[ERROR] Assistant fetch failed: {e}")


asyncio.create_task(auto_leave())


async def auto_end():
    """Automatically end stream if no one is listening."""
    while True:
        await asyncio.sleep(5)
        if not await is_autoend():
            continue

        for chat_id in list(autoend):
            timer = autoend.get(chat_id)
            if not timer:
                continue

            if datetime.now() > timer:
                if not await is_active_chat(chat_id):
                    autoend[chat_id] = {}
                    continue

                autoend[chat_id] = {}
                try:
                    await Anony.stop_stream(chat_id)
                    print(f"[AUTO-END] Stream stopped in chat {chat_id}")
                except Exception as e:
                    print(f"[ERROR] Failed to stop stream: {e}")

                try:
                    await app.send_message(
                        chat_id,
                        "» ʙᴏᴛ ᴀᴜᴛᴏ-ʟᴇꜰᴛ ᴛʜᴇ ᴄᴀʟʟ ᴀꜱ ɴᴏ ᴏɴᴇ ᴡᴀꜱ ʟɪꜱᴛᴇɴɪɴɢ.",
                    )
                except Exception as e:
                    print(f"[ERROR] Couldn't send auto-end message: {e}")


asyncio.create_task(auto_end())
