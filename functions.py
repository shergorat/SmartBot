from typing import Match, Optional, Any, List
import os
import re
from datetime import datetime, timedelta
from typing import Match, Optional, Any, List

import openai
from aiogram.types import ChatPermissions

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
        print(e, ' - error\n !!!!!!!!!!!!!!!!!!!!')
        raise e


async def escape_special_characters(text):
    escaped_text = text.replace('_', '\_').replace('?', '\?').replace('!', '\!')
    return escaped_text


async def has_link(text: str) -> Optional[Match[str]]:
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    return re.search(url_pattern, text)


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
        await bot.restrict_chat_member(chat_id, user_id, permissions)
        try:
            await db.remove_spamer(user_id)
        except Exception as e:
            print(f'{user_id} не был в базе спамеров, {e}')
        return "User unmuted successfully."
    except Exception as e:
        print(f'{user_id} не удалось размутить, {e}')
        return "Failed to unmute user."


async def get_gpt_check_words(file_name: str = 'gpt_check_words.txt') -> List[str]:
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    sw_file = os.path.join(data_dir, file_name)
    try:
        with open(sw_file, 'r', encoding='utf-8') as file:
            check_words = [word.strip().lower() for word in file if word.strip()]
        return check_words
    except Exception as e:
        raise ValueError(f'ERROR READING FILE "{file_name}": {e}\n{e.with_traceback}')


async def get_ban_words(file_name: str = 'ban_words.txt') -> List[str]:
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    sw_file = os.path.join(data_dir, file_name)
    try:
        with open(sw_file, 'r', encoding='utf-8') as file:
            ban_words = [word.strip().lower() for word in file if word.strip()]
        return ban_words
    except Exception as e:
        raise ValueError(f'ERROR READING FILE "{file_name}": {e.text}\n{e.with_traceback}')


async def has_check_words(message: str) -> bool:
    check_words = await get_gpt_check_words()
    message_lower = message.lower()
    pattern = '|'.join(check_words)

    return bool(re.search(pattern, message_lower))


async def has_ban_words(message: str) -> bool:
    ban_words = await get_ban_words()
    message_lower = message.lower()
    pattern = '|'.join(ban_words)

    return bool(re.search(pattern, message_lower))
