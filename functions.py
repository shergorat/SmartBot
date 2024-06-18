import logging
import os
import re
from datetime import datetime, timedelta
from typing import Match, Optional, Any, List
from fuzzywuzzy import fuzz

import openai
from aiogram import types
from aiogram.types import ChatPermissions
from aiogram.types import Message
from linkify_it import LinkifyIt

from bot import bot, db
from config import *
from json_manager import load_api_model

openai.api_key = OPENAI_API_KEY


async def openai_request(prompt):
    try:
        api_model = load_api_model()
        response = openai.ChatCompletion.create(
            model=api_model['openaimodel'],
            messages=[
                {"role": "system", "content": API_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=1024,
            n=1,
            stop=":700",  # stop=None
            # best_of = 3,
        )
        message = response['choices'][0]['message']['content']
        print(message, 'ANSWER!!')
        print(response['choices'][0]['finish_reason'], ' - finish reason ######')
        if not message:
            message = "Я не могу ответить на ваш вопрос. Пожалуйста, попробуйте переформулировать его."

        return message
    except Exception as e:
        logging.error(f'ERROR OPENAI REQUEST: {e}')
        raise e


async def openai_question(prompt):
    try:
        response = openai.ChatCompletion.create(
            model='gpt-3.5-turbo',
            messages=[
                {"role": "system", "content": API_ROLE},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=1024,
            n=1,
            stop=":700",  # stop=None
            # best_of = 3,
        )
        message = response['choices'][0]['message']['content']
        print(message, 'ANSWER!!')
        print(response['choices'][0]['finish_reason'], ' - finish reason ######')
        if not message:
            message = "Я не могу ответить на ваш вопрос. Пожалуйста, попробуйте переформулировать его."

        return message
    except Exception as e:
        logging.error(f'ERROR OPENAI REQUEST: {e}')
        raise e


async def get_reaction_count(message: types.Message) -> int:
    reactions = await bot.get_messages_reactions(chat_id=message.chat.id, message_ids=[message.message_id])
    count = 0
    for reaction in reactions:
        if reaction.emoji == EMOJI_VOTE:
            count += reaction.count
    return count


async def escape_special_characters(text):
    escaped_text = text.replace('_', '\_').replace('?', '\?').replace('!', '\!')
    return escaped_text


async def has_link(text: str) -> bool:
    linkify = LinkifyIt()
    return linkify.test(text)


async def get_link(text: str) -> str or None:
    linkify = LinkifyIt()
    matches = linkify.match(text)
    if matches:
        return matches[0].url
    else:
        return None


async def mute_user(chat_id: int, user_id: int, mute_duration_days: int or float) -> None:
    dt = datetime.now() + timedelta(days=mute_duration_days)
    timestamp = dt.timestamp()
    permissions = ChatPermissions(can_send_messages=False)

    await bot.restrict_chat_member(chat_id, user_id, permissions, until_date=timestamp)


async def unmute_user(chat_id: int, user_id: int) -> Any:
    permissions = ChatPermissions(
        can_send_messages=True,
        can_invite_users=True,
        can_send_media_messages=True
    )

    try:
        chats = await db.get_allowed_groups()
        for chat in chats:
            await bot.restrict_chat_member(chat, user_id, permissions)
        try:
            await db.remove_spamer(user_id)
        except Exception as e:
            print(f'{user_id} не был в базе спамеров, {e}')
        return "User unmuted successfully."
    except Exception as e:
        logging.error(f"Failed to unmute user {user_id}: {e}")
        return "Failed to unmute user."


async def order_alert(admins_id, service_id: int):
    for admin in admins_id:
        try:
            await bot.send_message(admin, f'Новый заказ услуги No{service_id} был создан')
        except Exception as e:
            print(e)


async def get_gpt_check_words(file_name: str = 'gpt_check_words.txt') -> List[str]:
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    sw_file = os.path.join(data_dir, file_name)
    try:
        with open(sw_file, 'r', encoding='utf-8') as file:
            check_words = [word.strip().lower() for word in file if word.strip()]
        return check_words
    except Exception as e:
        logging.error(f'ERROR READING FILE "{file_name}": {e}')
        raise ValueError(f'ERROR READING FILE "{file_name}": {e}\n{e.with_traceback}')


async def get_ban_words(file_name: str = 'ban_words.txt') -> List[str]:
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    sw_file = os.path.join(data_dir, file_name)
    try:
        with open(sw_file, 'r', encoding='utf-8') as file:
            ban_words = [word.strip().lower() for word in file if word.strip()]
        return ban_words
    except Exception as e:
        logging.error(f'ERROR READING FILE "{file_name}": {e}')
        raise ValueError(f'ERROR READING FILE "{file_name}": {e}\n{e.with_traceback}')


async def has_check_words(message: str) -> str or None:
    check_words = await get_gpt_check_words()
    # logging.info(f'Check words: {check_words}')
    words = message.lower().split()
    for word in words:
        for check_word in check_words:
            if fuzz.ratio(word, check_word) > C_ACCURACY:
                return check_word
    # logging.info(f'No check word found in message: {message}')
    return None


async def has_ban_words(message: str) -> str or None:
    ban_words = await get_ban_words()
    # logging.info(f'Ban words: {ban_words}')
    words = message.lower().split()
    for word in words:
        for ban_word in ban_words:
            if fuzz.ratio(word, ban_word) > B_ACCURACY:
                return ban_word
    # logging.info(f'No ban word found in message: {message}')
    return None


async def save_message_in_db(message: Message):
    message_id = message.message_id
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = message.from_user.username
    message_type = message.content_type

    message_text = message.text
    if message_type == types.ContentTypes.PHOTO:
        image_url = message.photo[-1].file_id
        message_text = f"{message_text}\n\n[Фото]({image_url})"

    elif message_type == types.ContentType.NEW_CHAT_MEMBERS:
        new_members = message.new_chat_members
        if new_members:
            new_member = new_members[0]
            username = new_member.username
            if username:
                message_text = f"{message_text}\n\n[Новый участник чата]({username})"
            else:
                message_text = f"{message_text}\n\nНовый участник чата"

    elif message_type == types.ContentType.LEFT_CHAT_MEMBER:
        left_member = message.left_chat_member
        if left_member:
            username = left_member.username
            if username:
                message_text = f"{message_text}\n\n[Покинул чат]({username})"
            else:
                message_text = f"{message_text}\n\nПокинул чат"

    await db.insert_chat_message(
        message_id=message_id,
        chat_id=chat_id,
        user_id=user_id,
        user_name=user_name,
        message_type=message_type,
        message_text=message_text,
    )
