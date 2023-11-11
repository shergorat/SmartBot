import re

from aiogram import types
from aiogram.dispatcher import Dispatcher
from aiogram.dispatcher.filters import BoundFilter
from aiogram.types import ChatMemberStatus
from aiogram.types import ChatType

from bot import bot, db
from functions import openai_request, has_ban_words, has_check_words, has_link, mute_user, unmute_user


class AdminOrCreatorFilter(BoundFilter):
    async def check(self, message):
        chat_member = await message.chat.get_member(message.from_user.id)
        return chat_member.status in (types.ChatMemberStatus.CREATOR, types.ChatMemberStatus.ADMINISTRATOR)


ALLOWED_GROUPS = None


# @dp.message_handler(content_types=[types.ContentType.NEW_CHAT_MEMBERS])
async def on_new_chat_member(message: types.Message):
    new_members = message.new_chat_members
    bot_id = bot.id
    global ALLOWED_GROUPS
    ALLOWED_GROUPS = await db.get_allowed_groups()
    ALLOWED_GROUPS = [item[0] for item in ALLOWED_GROUPS]
    print(ALLOWED_GROUPS)
    chat_id = message.chat.id
    print(chat_id)
    for member in new_members:
        if member.id == bot_id:
            chat_title = message.chat.title
            # Бот был добавлен в чат
            # Проверяем, есть ли чат в списке одобренных
            if chat_id in ALLOWED_GROUPS:
                await message.answer(f"Привет, чат *{chat_title}*!\n"
                                     "Для того, чтобы я мог выполнять свою работу, я должен быть администратором",
                                     parse_mode='Markdown')
            else:
                await message.answer(f"Чат *{chat_id}* не является одобренным \n"
                                     "Свяжитесь с *@maxim_kuhar* для добавления вашего чата", parse_mode='Markdown')
                await bot.leave_chat(chat_id)
        else:
            await db.add_user(user_id=member.id)


# @dp.message_handler(commands = ["m"], chat_type=(ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL))
async def mute_command(message: types.Message):
    print('mute com')
    chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if chat_member.status in (ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
        chat_id = message.chat.id
        user_id = None
        message_text = None
        mute_duration_days = 3
        try:
            # Проверяем, является ли сообщение ответом на другое сообщение
            if message.reply_to_message and message.reply_to_message.from_user:
                user_id = message.reply_to_message.from_user.id
                username = message.reply_to_message.from_user.username
                message_text = message.reply_to_message.text

                if re.search(r'/m\s+\d+', message.text):
                    mute_duration_days = int(re.search(r'\d+', message.text).group())
            # Если нет, то пытаемся найти указание username
            elif re.search(r'@[\w_]+', message.text):
                username = re.search(r'@[\w_]+', message.text).group()[1:]
                user_id = await db.get_user_id_by_username(username=username)
                print(user_id)
                message_text = 'Unknown'
                if re.search(r'/m\s+@[\w_]+\s+\d+', message.text):
                    mute_duration_days = int(re.search(r'/m\s+@[\w_]+\s+(\d+)', message.text).group(1))
                    print(mute_duration_days)
            else:
                await message.reply("Команда была применена неверно\n"
                                    "Используйте команду на сообщение пользователя, либо упомяните его после `/m`",
                                    parse_mode='Markdown')
                raise ValueError('Не удалось найти пользователя для мута')

            if user_id:
                await mute_user(chat_id, user_id, mute_duration_days)
                await message.reply(f"Пользователь @{username} замучен на {mute_duration_days} дней")
                reason = f'muted by admin {message.from_user.username}'
                await db.insert_punishment(user_id=user_id, username=username, chat_id=chat_id,
                                           message_text=message_text, reason=reason)
        except Exception as e:
            raise ValueError('Не удалось найти пользователя для мута')
    else:
        pass


# @dp.message_handler(commands = ["b"], chat_type=(ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL))
async def ban_command(message: types.Message):
    print('ban com')
    chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if chat_member.status in (ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
        chat_id = message.chat.id
        user_id = None
        message_text = None
        mute_duration_days = 367
        try:
            # Проверяем, является ли сообщение ответом на другое сообщение
            if message.reply_to_message and message.reply_to_message.from_user:
                user_id = message.reply_to_message.from_user.id
                username = message.reply_to_message.from_user.username
                message_text = message.reply_to_message.text

            # Если нет, то пытаемся найти указание username
            elif re.search(r'@[\w_]+', message.text):
                username = re.search(r'@[\w_]+', message.text).group()[1:]
                user_id = await db.get_user_id_by_username(username=username)
                print(user_id)
                message_text = 'Unknown'
            else:
                await message.reply("Команда была применена неверно\n"
                                    "Используйте команду на сообщение пользователя, либо упомяните его после `/b`",
                                    parse_mode='Markdown')
                raise ValueError('Не удалось найти пользователя для мута')

            if user_id:
                await mute_user(chat_id, user_id, mute_duration_days)
                await message.reply(f"_Пользователю @{username} была перманентно отключена "
                                    f"возможность отправлять сообщения_"
                                    , parse_mode='Markdown')
                reason = f'baned by admin {message.from_user.username}'
                await db.insert_punishment(user_id=user_id, username=username, chat_id=chat_id,
                                           message_text=message_text, reason=reason)
                await db.insert_spamer(user_id=user_id, chat_id=chat_id, message_text=message_text, reason=reason)
        except Exception as e:
            print(e.with_traceback, e, '-не удалось замутить пользователя!!!')
    else:
        pass


# @dp.message_handler(commands = ["um"], chat_type=(ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL))
async def unmute_command(message: types.Message):
    chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if chat_member.status not in (ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR):
        pass
    elif chat_member.status in (ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR):
        chat_id = message.chat.id
        user_id = None

        try:
            if re.search(r'@[\w_]+', message.text):
                username = re.search(r'@[\w_]+', message.text).group()[1:]
                user_id = await db.get_user_id_by_username(username=username)
            else:
                await message.reply("Команда была применена неверно\n"
                                    "Упомяните пользователя после `/um`",
                                    parse_mode='Markdown')
                raise ValueError('Не удалось найти пользователя для снятия мута')
            if user_id:
                await unmute_user(chat_id, user_id)
                await message.reply(f"Пользователь @{username} размучен ")
        except Exception as e:
            print(e.with_traceback, e, '-не удалось размутить пользователя!!!')


# @dp.message_handler(commands = ["report"], chat_type=(ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL))
async def report_command(message: types.Message):
    if message.reply_to_message:
        try:
            user_id = message.reply_to_message.from_user.id
            message_text = message.reply_to_message.text
            chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
            if chat_member.status in (ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR):
                # тут можно вывести сообщение, мол на админов жаловаться не надо, но я посчитал это лишним
                return
            gpt_answer = await openai_request(message_text)
            if gpt_answer == 'spam':
                await message.answer(
                    f"@{message.reply_to_message.from_user.username}, ваше сообщение расценено как спам\n"
                    "_Вам была отключена возможность отправлять сообщения\n"
                    "Если считаете блокировку несправедливой, обратитесь к администратору группы_",
                    parse_mode='Markdown')
                await mute_user(chat_id=message.chat.id, user_id=user_id, mute_duration_days=367)
                reason = 'by_report'
                await bot.delete_message(chat_id=message.chat.id, message_id=message.reply_to_message.message_id)
                await db.insert_spamer(user_id=user_id, chat_id=message.chat.id, message_text=message_text,
                                       reason=reason)
                await db.insert_punishment(user_id=user_id, username=message.reply_to_message.from_user.username,
                                           chat_id=message.chat.id, message_text=message_text, reason=reason)
                return
            elif gpt_answer == 'ok':
                print('gpt check result: ok')
            else:
                print(gpt_answer, ' - нейросеть ответила не шаблоном!!!')
        except Exception as e:
            print(e.with_traceback, e, ' - не удалось провести проверку пользователя!!!')
    else:
        await message.reply("Команда должна быть ответом на сообщение, на которое вы хотите пожаловаться")


# @dp.message_handler(content_types=types.ContentTypes.TEXT,
#                     chat_type=(ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL))
async def moderate_message(message: types.Message):
    await db.insert_chat_message(message_id=message.message_id, chat_id=message.chat.id, message_text=message.text,
                                 user_id=message.from_user.id, user_name=message.from_user.username)
    chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if chat_member.status not in (ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR):
        user_message_id = message.message_id
        user_messages_count = await db.get_message_count_by_user(user_id=message.from_user.id, chat_id=message.chat.id)

        if await db.is_spamer(user_id=message.from_user.id):
            await mute_user(chat_id=message.chat.id, user_id=message.from_user.id, mute_duration_days=367)
            reason = 'spamer_from_base'
            await bot.delete_message(chat_id=message.chat.id, message_id=user_message_id)
            await db.insert_punishment(user_id=message.from_user.id, username=message.from_user.username,
                                       chat_id=message.chat.id, message_text=message.text, reason=reason)
            return

        if await has_ban_words(message.text):
            await message.answer(f"@{message.from_user.username}, в вашем сообщении обнаружены запрещенные слова\n"
                                 "_Вам была отключена возможность отправлять сообщения\n"
                                 "Если считаете блокировку несправедливой, обратитесь к администратору группы_",
                                 parse_mode='Markdown')
            await mute_user(chat_id=message.chat.id, user_id=message.from_user.id, mute_duration_days=367)
            reason = 'ban_word'
            await bot.delete_message(chat_id=message.chat.id, message_id=user_message_id)
            await db.insert_spamer(user_id=message.from_user.id, chat_id=message.chat.id, message_text=message.text,
                                   reason=reason)
            await db.insert_punishment(user_id=message.from_user.id, username=message.from_user.username,
                                       chat_id=message.chat.id, message_text=message.text, reason=reason)
            return

        if user_messages_count < 5:
            print('## first messages check ##')
            gpt_answer = await openai_request(message.text)
            if gpt_answer == 'spam':
                await message.answer(f"@{message.from_user.username}, ваше сообщение расценено как спам\n"
                                     "_Вам была отключена возможность отправлять сообщения\n"
                                     "Если считаете блокировку несправедливой, обратитесь к администратору группы_",
                                     parse_mode='Markdown')
                await mute_user(chat_id=message.chat.id, user_id=message.from_user.id, mute_duration_days=367)
                reason = 'by_gpt_newmember_control'
                await db.insert_spamer(user_id=message.from_user.id, chat_id=message.chat.id, message_text=message.text,
                                       reason=reason)
                await db.insert_punishment(user_id=message.from_user.id, username=message.from_user.username,
                                           chat_id=message.chat.id, message_text=message.text, reason=reason)
                await bot.delete_message(chat_id=message.chat.id, message_id=user_message_id)
                return
            elif gpt_answer == 'ok':
                print('gpt check result: ok')
            else:
                print(gpt_answer, ' - нейросеть ответила не шаблоном!!!')

        if await has_check_words(message.text):
            gpt_answer = await openai_request(message.text)
            if gpt_answer == 'spam':
                await message.answer(f"@{message.from_user.username}, ваше сообщение расценено как спам\n"
                                     "_Вам была отключена возможность отправлять сообщения_", parse_mode='Markdown')
                await mute_user(chat_id=message.chat.id, user_id=message.from_user.id, mute_duration_days=367)
                reason = 'spam-message'
                await bot.delete_message(chat_id=message.chat.id, message_id=user_message_id)
                await db.insert_spamer(user_id=message.from_user.id, chat_id=message.chat.id, message_text=message.text,
                                       reason=reason)
                await db.insert_punishment(user_id=message.from_user.id, username=message.from_user.username,
                                           chat_id=message.chat.id, message_text=message.text, reason=reason)
                return
            elif gpt_answer == 'ok':
                await message.answer(f"@{message.from_user.username}, ваше сообщение в порядке", parse_mode='Markdown')
            else:
                print(gpt_answer, ' - нейросеть ответила не шаблоном!!!')

        if await has_link(message.text):
            await message.answer(f"@{message.from_user.username}, для новых пользователей *запрещена отправка ссылок*\n"
                                 "_Вам была временно отключена возможность отправлять сообщения_",
                                 parse_mode='Markdown')
            await mute_user(chat_id=message.chat.id, user_id=message.from_user.id, mute_duration_days=3)
            reason = 'link in message'
            await bot.delete_message(chat_id=message.chat.id, message_id=user_message_id)
            await db.insert_punishment(user_id=message.from_user.id, username=message.from_user.username,
                                       chat_id=message.chat.id, message_text=message.text, reason=reason)

        else:
            print('message check result: ok')


def register_handlers_group(dp: Dispatcher):
    dp.register_message_handler(on_new_chat_member, content_types=[types.ContentType.NEW_CHAT_MEMBERS])
    dp.register_message_handler(mute_command, commands=["m"],
                                chat_type=(ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL))
    dp.register_message_handler(unmute_command, commands=["um"],
                                chat_type=(ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL))
    dp.register_message_handler(ban_command, commands=["b"],
                                chat_type=(ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL))
    dp.register_message_handler(report_command, commands=["report"],
                                chat_type=(ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL))
    dp.register_message_handler(moderate_message, content_types=types.ContentTypes.TEXT,
                                chat_type=(ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL))
