import asyncio
from pyrogram import filters
from pyrogram.enums import ChatMembersFilter
from pyrogram.errors import FloodWait
from pyrogram.types import Message

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
async def broadcast_message(client, message: Message, _):
    global IS_BROADCASTING

    # Check if the message is a reply and contains supported content
    if message.reply_to_message:
        reply_msg = message.reply_to_message
        if not (
            reply_msg.text
            or reply_msg.photo
            or reply_msg.video
            or reply_msg.document
            or reply_msg.audio
            or reply_msg.animation
            or reply_msg.sticker
            or reply_msg.voice
        ):
            return await message.reply_text("Please reply to a message with text, photo, video, document, audio, sticker, or voice for broadcasting.")

        # Extract content type and details
        content_type = None
        file_id = None
        text_content = reply_msg.text or reply_msg.caption
        reply_markup = reply_msg.reply_markup if hasattr(reply_msg, 'reply_markup') else None

        if reply_msg.photo:
            content_type = 'photo'
            file_id = reply_msg.photo.file_id
        elif reply_msg.video:
            content_type = 'video'
            file_id = reply_msg.video.file_id
        elif reply_msg.document:
            content_type = 'document'
            file_id = reply_msg.document.file_id
        elif reply_msg.audio:
            content_type = 'audio'
            file_id = reply_msg.audio.file_id
        elif reply_msg.animation:
            content_type = 'animation'
            file_id = reply_msg.animation.file_id
        elif reply_msg.sticker:
            content_type = 'sticker'
            file_id = reply_msg.sticker.file_id
        elif reply_msg.voice:
            content_type = 'voice'
            file_id = reply_msg.voice.file_id
        else:
            content_type = 'text'

        IS_BROADCASTING = True
        await message.reply_text(_["broad_1"])

        # Determine if we should forward or send as new message
        should_forward = "-nobot" not in message.text

        # Broadcast to chats if -group is specified or no specific target
        if "-group" in message.text or ("-user" not in message.text and "-assistant" not in message.text):
            sent_chats = 0
            pin = 0
            chats = [int(chat["chat_id"]) for chat in await get_served_chats()]
            for chat_id in chats:
                try:
                    if should_forward:
                        # Forward the original message
                        m = await app.forward_messages(
                            chat_id=chat_id,
                            from_chat_id=message.chat.id,
                            message_ids=reply_msg.id
                        )
                    else:
                        # Send as a new message
                        if content_type == 'text':
                            m = await app.send_message(
                                chat_id=chat_id,
                                text=text_content,
                                reply_markup=reply_markup
                            )
                        elif content_type == 'photo':
                            m = await app.send_photo(
                                chat_id=chat_id,
                                photo=file_id,
                                caption=text_content,
                                reply_markup=reply_markup
                            )
                        elif content_type == 'video':
                            m = await app.send_video(
                                chat_id=chat_id,
                                video=file_id,
                                caption=text_content,
                                reply_markup=reply_markup
                            )
                        elif content_type == 'document':
                            m = await app.send_document(
                                chat_id=chat_id,
                                document=file_id,
                                caption=text_content,
                                reply_markup=reply_markup
                            )
                        elif content_type == 'audio':
                            m = await app.send_audio(
                                chat_id=chat_id,
                                audio=file_id,
                                caption=text_content,
                                reply_markup=reply_markup
                            )
                        elif content_type == 'animation':
                            m = await app.send_animation(
                                chat_id=chat_id,
                                animation=file_id,
                                caption=text_content,
                                reply_markup=reply_markup
                            )
                        elif content_type == 'sticker':
                            m = await app.send_sticker(
                                chat_id=chat_id,
                                sticker=file_id,
                                reply_markup=reply_markup
                            )
                        elif content_type == 'voice':
                            m = await app.send_voice(
                                chat_id=chat_id,
                                voice=file_id,
                                caption=text_content,
                                reply_markup=reply_markup
                            )

                    # Handle pinning
                    if "-pin" in message.text:
                        try:
                            await m.pin(disable_notification=True)
                            pin += 1
                        except:
                            pass
                    elif "-pinloud" in message.text:
                        try:
                            await m.pin(disable_notification=False)
                            pin += 1
                        except:
                            pass

                    sent_chats += 1
                    await asyncio.sleep(0.1)
                except FloodWait as fw:
                    await asyncio.sleep(fw.value)
                except:
                    continue
            await message.reply_text(_["broad_3"].format(sent_chats, pin))

        # Broadcast to users if -user is specified
        if "-user" in message.text:
            sent_users = 0
            users = [int(user["user_id"]) for user in await get_served_users()]
            for user_id in users:
                try:
                    # Skip bot users if -nobot is specified
                    if "-nobot" in message.text:
                        user = await app.get_users(user_id)
                        if user.is_bot:
                            continue

                    if should_forward:
                        # Forward the original message
                        await app.forward_messages(
                            chat_id=user_id,
                            from_chat_id=message.chat.id,
                            message_ids=reply_msg.id
                        )
                    else:
                        # Send as a new message
                        if content_type == 'text':
                            await app.send_message(
                                chat_id=user_id,
                                text=text_content,
                                reply_markup=reply_markup
                            )
                        elif content_type == 'photo':
                            await app.send_photo(
                                chat_id=user_id,
                                photo=file_id,
                                caption=text_content,
                                reply_markup=reply_markup
                            )
                        elif content_type == 'video':
                            await app.send_video(
                                chat_id=user_id,
                                video=file_id,
                                caption=text_content,
                                reply_markup=reply_markup
                            )
                        elif content_type == 'document':
                            await app.send_document(
                                chat_id=user_id,
                                document=file_id,
                                caption=text_content,
                                reply_markup=reply_markup
                            )
                        elif content_type == 'audio':
                            await app.send_audio(
                                chat_id=user_id,
                                audio=file_id,
                                caption=text_content,
                                reply_markup=reply_markup
                            )
                        elif content_type == 'animation':
                            await app.send_animation(
                                chat_id=user_id,
                                animation=file_id,
                                caption=text_content,
                                reply_markup=reply_markup
                            )
                        elif content_type == 'sticker':
                            await app.send_sticker(
                                chat_id=user_id,
                                sticker=file_id,
                                reply_markup=reply_markup
                            )
                        elif content_type == 'voice':
                            await app.send_voice(
                                chat_id=user_id,
                                voice=file_id,
                                caption=text_content,
                                reply_markup=reply_markup
                            )
                    sent_users += 1
                    await asyncio.sleep(0.1)
                except FloodWait as fw:
                    await asyncio.sleep(fw.value)
                except:
                    continue
            await message.reply_text(_["broad_4"].format(sent_users))

        IS_BROADCASTING = False
        return

    # Handle text-based broadcast (non-reply case)
    if len(message.command) < 2:
        return await message.reply_text(_["broad_2"])
    
    query = message.text.split(None, 1)[1].strip()
    flags = ["-pin", "-pinloud", "-nobot", "-assistant", "-user", "-group"]
    for flag in flags:
        query = query.replace(flag, "").strip()
    
    if not query:
        return await message.reply_text(_["broad_8"])

    IS_BROADCASTING = True
    await message.reply_text(_["broad_1"])

    sent = 0
    pin = 0

    # Broadcast to chats if -group or no specific target is specified
    if "-group" in message.text or ("-user" not in message.text and "-assistant" not in message.text):
        chats = [int(chat["chat_id"]) for chat in await get_served_chats()]
        for chat_id in chats:
            try:
                m = await app.send_message(
                    chat_id=chat_id,
                    text=query,
                    reply_markup=None
                )
                if "-pin" in message.text:
                    try:
                        await m.pin(disable_notification=True)
                        pin += 1
                    except:
                        continue
                elif "-pinloud" in message.text:
                    try:
                        await m.pin(disable_notification=False)
                        pin += 1
                    except:
                        continue
                sent += 1
                await asyncio.sleep(0.1)
            except FloodWait as fw:
                await asyncio.sleep(fw.value)
            except:
                continue
        await message.reply_text(_["broad_3"].format(sent, pin))

    # Broadcast to users if -user is specified
    if "-user" in message.text:
        sent_users = 0
        users = [int(user["user_id"]) for user in await get_served_users()]
        for user_id in users:
            try:
                # Skip bot users if -nobot is specified
                if "-nobot" in message.text:
                    user = await app.get_users(user_id)
                    if user.is_bot:
                        continue
                await app.send_message(
                    chat_id=user_id,
                    text=query,
                    reply_markup=None
                )
                sent_users += 1
                await asyncio.sleep(0.1)
            except FloodWait as fw:
                await asyncio.sleep(fw.value)
            except:
                continue
        await message.reply_text(_["broad_4"].format(sent_users))

    # Broadcast via assistants if -assistant is specified
    if "-assistant" in message.text:
        aw = await message.reply_text(_["broad_5"])
        text = _["broad_6"]
        from AnonXMusic.core.userbot import assistants

        for num in assistants:
            sent = 0
            client = await get_client(num)
            async for dialog in client.get_dialogs():
                try:
                    await client.send_message(
                        dialog.chat.id,
                        text=query
                    )
                    sent += 1
                    await asyncio.sleep(0.1)
                except FloodWait as fw:
                    await asyncio.sleep(fw.value)
                except:
                    continue
            text += _["broad_7"].format(num, sent)
        await aw.edit_text(text)

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
