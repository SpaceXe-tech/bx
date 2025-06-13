import asyncio
from pyrogram import filters
from pyrogram.enums import ChatMembersFilter
from pyrogram.errors import FloodWait
from AnonXMusic import app
from AnonXMusic.misc import SUDOERS
from AnonXMusic.utils.database import (
    get_active_chats,
    get_authuser_names,
    get_client,
    get_served_chats,
    get_served_users,
)
from AnonXMusic.utils.decorators.language import language
from AnonXMusic.utils.formatters import alpha_to_int
from config import adminlist

IS_BROADCASTING = False

@app.on_message(filters.command("broadcast") & SUDOERS)
@language
async def braodcast_message(client, message, _):
    global IS_BROADCASTING

    if "-group" in message.text or "-user" in message.text:
        if not message.reply_to_message or not (
            message.reply_to_message.photo
            or message.reply_to_message.text
            or message.reply_to_message.sticker
            or message.reply_to_message.entities
        ):
            return await message.reply_text("Please reply to a text, image, or sticker message for broadcasting.")

        # Extract data from the replied message
        content_type = None
        content = None
        if message.reply_to_message.photo:
            content_type = 'photo'
            content = message.reply_to_message.photo.file_id
        elif message.reply_to_message.sticker:
            content_type = 'sticker'
            content = message.reply_to_message.sticker.file_id
        elif message.reply_to_message.text:
            content_type = 'text'
            content = message.reply_to_message.text
            # Handle premium emojis in text
            if message.reply_to_message.entities:
                content = message.reply_to_message.text.markdown

        caption = message.reply_to_message.caption
        reply_markup = message.reply_to_message.reply_markup if hasattr(message.reply_to_message, 'reply_markup') else None

        IS_BROADCASTING = True
        await message.reply_text(_["broad_1"])

        async def send_broadcast(targets, target_type):
            sent_count = 0
            batch_size = 50  # Process in batches to optimize speed
            for i in range(0, len(targets), batch_size):
                batch = targets[i:i + batch_size]
                tasks = []
                for target_id in batch:
                    try:
                        if content_type == 'photo':
                            tasks.append(
                                app.send_photo(
                                    chat_id=target_id,
                                    photo=content,
                                    caption=caption,
                                    reply_markup=reply_markup
                                )
                            )
                        elif content_type == 'sticker':
                            tasks.append(
                                app.send_sticker(
                                    chat_id=target_id,
                                    sticker=content,
                                    reply_markup=reply_markup
                                )
                            )
                        elif content_type == 'text':
                            tasks.append(
                                app.send_message(
                                    chat_id=target_id,
                                    text=content,
                                    reply_markup=reply_markup,
                                    parse_mode="markdown" if message.reply_to_message.entities else None
                                )
                            )
                    except:
                        continue
                # Execute batch concurrently
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if not isinstance(result, Exception):
                        sent_count += 1
                # Adaptive sleep to avoid flood waits
                await asyncio.sleep(0.1)  # Reduced sleep for faster processing
            return sent_count

        if "-group" in message.text:
            # Broadcasting to chats
            chats = [int(chat["chat_id"]) for chat in await get_served_chats()]
            sent_chats = await send_broadcast(chats, "chats")
            await message.reply_text(f"Broadcast to chats completed! Sent to {sent_chats} chats.")

        if "-user" in message.text:
            # Broadcasting to users
            users = [int(user["user_id"]) for user in await get_served_users()]
            sent_users = await send_broadcast(users, "users")
            await message.reply_text(f"Broadcast to users completed! Sent to {sent_users} users.")

        IS_BROADCASTING = False
        return

    if message.reply_to_message:
        x = message.reply_to_message.id
        y = message.chat.id
        reply_markup = message.reply_to_message.reply_markup if message.reply_to_message.reply_markup else None
        content_type = None
        content = None
        if message.reply_to_message.photo:
            content_type = 'photo'
            content = message.reply_to_message.photo.file_id
            caption = message.reply_to_message.caption
        elif message.reply_to_message.sticker:
            content_type = 'sticker'
            content = message.reply_to_message.sticker.file_id
        elif message.reply_to_message.text:
            content_type = 'text'
            content = message.reply_to_message.text
            if message.reply_to_message.entities:
                content = message.reply_to_message.text.markdown
    else:
        if len(message.command) < 2:
            return await message.reply_text(_["broad_2"])
        query = message.text.split(None, 1)[1]
        if "-pin" in query:
            query = query.replace("-pin", "")
        if "-nobot" in query:
            query = query.replace("-nobot", "")
        if "-pinloud" in query:
            query = query.replace("-pinloud", "")
        if "-assistant" in query:
            query = query.replace("-assistant", "")
        if "-user" in query:
            query = query.replace("-user", "")
        if query == "":
            return await message.reply_text(_["broad_8"])
        content_type = 'text'
        content = query

    IS_BROADCASTING = True
    await message.reply_text(_["broad_1"])

    if "-nobot" not in message.text:
        sent = 0
        pin = 0
        chats = [int(chat["chat_id"]) for chat in await get_served_chats()]
        batch_size = 50
        for i in range(0, len(chats), batch_size):
            batch = chats[i:i + batch_size]
            tasks = []
            for chat_id in batch:
                try:
                    if message.reply_to_message:
                        tasks.append(
                            app.copy_message(
                                chat_id=chat_id,
                                from_chat_id=y,
                                message_id=x,
                                reply_markup=reply_markup
                            )
                        )
                    else:
                        tasks.append(
                            app.send_message(
                                chat_id=chat_id,
                                text=content,
                                parse_mode="markdown" if message.reply_to_message and message.reply_to_message.entities else None
                            )
                        )
                except:
                    continue
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for idx, result in enumerate(results):
                if not isinstance(result, Exception):
                    sent += 1
                    if "-pin" in message.text:
                        try:
                            await results[idx].pin(disable_notification=True)
                            pin += 1
                        except:
                            continue
                    elif "-pinloud" in message.text:
                        try:
                            await results[idx].pin(disable_notification=False)
                            pin += 1
                        except:
                            continue
            await asyncio.sleep(0.1)  # Reduced sleep for faster processing
        try:
            await message.reply_text(_["broad_3"].format(sent, pin))
        except:
            pass

    if "-user" in message.text:
        susr = 0
        served_users = [int(user["user_id"]) for user in await get_served_users()]
        batch_size = 50
        for i in range(0, len(served_users), batch_size):
            batch = served_users[i:i + batch_size]
            tasks = []
            for user_id in batch:
                try:
                    if message.reply_to_message:
                        tasks.append(
                            app.copy_message(
                                chat_id=user_id,
                                from_chat_id=y,
                                message_id=x,
                                reply_markup=reply_markup
                            )
                        )
                    else:
                        tasks.append(
                            app.send_message(
                                chat_id=user_id,
                                text=content,
                                parse_mode="markdown" if message.reply_to_message and message.reply_to_message.entities else None
                            )
                        )
                except:
                    continue
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if not isinstance(result, Exception):
                    susr += 1
            await asyncio.sleep(0.1)
        try:
            await message.reply_text(_["broad_4"].format(susr))
        except:
            pass

    if "-assistant" in message.text:
        aw = await message.reply_text(_["broad_5"])
        text = _["broad_6"]
        from AviaxMusic.core.userbot import assistants

        for num in assistants:
            sent = 0
            client = await get_client(num)
            async for dialog in client.get_dialogs():
                try:
                    if message.reply_to_message:
                        await client.forward_messages(dialog.chat.id, y, x)
                    else:
                        await client.send_message(
                            dialog.chat.id,
                            text=content,
                            parse_mode="markdown" if message.reply_to_message and message.reply_to_message.entities else None
                        )
                    sent += 1
                    await asyncio.sleep(1)  # Slightly longer sleep for assistants to avoid rate limits
                except FloodWait as fw:
                    await asyncio.sleep(fw.value)
                except:
                    continue
            text += _["broad_7"].format(num, sent)
        try:
            await aw.edit_text(text)
        except:
            pass
    IS_BROADCASTING = False

async def auto_clean():
    while not await asyncio.sleep(10):
        try:
            served_chats = await get_active_chats()
            for chat_id in served_chats:
                if chat_id not in adminlist:
                    adminlist[chat_id] = []
                    async for user in app.get_chat_members(
                        chat_id, filter=ChatMembersFilter.ADMINISTRATORS
                    ):
                        if user.privileges.can_manage_video_chats:
                            adminlist[chat_id].append(user.user.id)
                    authusers = await get_authuser_names(chat_id)
                    for user in authusers:
                        user_id = await alpha_to_int(user)
                        adminlist[chat_id].append(user_id)
        except:
            continue

asyncio.create_task(auto_clean())
