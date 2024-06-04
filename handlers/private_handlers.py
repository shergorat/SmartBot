import logging

from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ChatType
from aiogram.utils.exceptions import ChatNotFound

from bot import bot, dp, db
from config import *
from json_manager import api_model, save_api_model, load_api_model

ALLOWED_GROUPS = None


class BotState(StatesGroup):
    waiting_for_chat_id = State()  # Состояние для ожидания id чата


# @dp.message_handler(commands = ["start"], chat_type=ChatType.PRIVATE)
async def on_start_private(message: types.Message, state: FSMContext):
    logging.info(f"User {message.from_user.id} started bot")
    await state.finish()
    user_id = message.from_user.id
    if user_id in ADMIN_ID:
        admin_button = types.InlineKeyboardButton("Админ-панель", callback_data="admin_panel")
        keyboard = types.InlineKeyboardMarkup().add(admin_button)
    else:
        keyboard = types.InlineKeyboardMarkup().add()

    message_text = (
        "Привет! Это бот-модератор\n"
        "Вопросы по работе бота можно направлять *@maxim_kuhar*"
    )
    await message.answer(message_text, reply_markup=keyboard, parse_mode='Markdown')


# @dp.callback_query_handler(lambda query: query.data == "admin_panel")
async def admin_panel(callback_query: types.CallbackQuery):
    logging.info(f"User {callback_query.from_user.id} opened admin panel")

    message_text = "Выберите чат:"
    global ALLOWED_GROUPS
    ALLOWED_GROUPS = await db.get_allowed_groups()
    # Создаем inline-кнопки для каждого чата
    keyboard = types.InlineKeyboardMarkup()
    for group_id in ALLOWED_GROUPS:
        try:
            group_info = await bot.get_chat(str(group_id[0]))
            button_text = group_info['title']
            button_callback = f"group_details_{group_id[0]}"
            chat_button = types.InlineKeyboardButton(button_text, callback_data=button_callback)
            keyboard.add(chat_button)
        except ChatNotFound as e:
            logging.error(f"Chat {group_id[0]} not found: {e}")
            pass
    openai_api_model = load_api_model()
    add_chat_button = types.InlineKeyboardButton("Добавить чат", callback_data="add_new_chat")
    model_button = types.InlineKeyboardButton(f"Модель: {openai_api_model['openaimodel']}",
                                              callback_data="model_change")

    keyboard.add(add_chat_button, model_button)

    await bot.edit_message_text(chat_id=callback_query.message.chat.id,
                                message_id=callback_query.message.message_id,
                                text=message_text, reply_markup=keyboard)


# @dp.callback_query_handler(lambda query: query.data == "add_new_chat")
async def add_new_chat(callback_query: types.CallbackQuery):
    logging.info(f"Received callback 'add_new_chat' by user {callback_query.from_user.id}")
    admin_button = types.InlineKeyboardButton("Вернуться", callback_data="return_to_admin")
    keyboard = types.InlineKeyboardMarkup().add(admin_button)
    await bot.edit_message_text(chat_id=callback_query.message.chat.id,
                                message_id=callback_query.message.message_id, text="Введите идентификатор(id) чата:",
                                reply_markup=keyboard)
    user_id = callback_query.from_user.id
    await BotState.waiting_for_chat_id.set()


# @dp.message_handler(lambda message: message.text and message.from_user.id in ADMIN_ID,
#                     state=BotState.waiting_for_chat_id)
async def handle_chat_id_input(message: types.Message, state: FSMContext):
    chat_id = message.text
    await state.update_data(chat_id=chat_id)  # Сохраняем идентификатор чата в состоянии FSM
    admin_button = types.InlineKeyboardButton("Вернуться", callback_data="admin_panel")
    keyboard = types.InlineKeyboardMarkup().add(admin_button)
    await state.finish()
    global ALLOWED_GROUPS
    try:
        await db.add_allowed_chat(int(chat_id))
        ALLOWED_GROUPS = await db.get_allowed_groups()
        await message.answer(f"Чат {chat_id} успешно добавлен", reply_markup=keyboard)
        logging.info(f"User {message.from_user.id} successfully added chat {chat_id}")
    except Exception as e:
        logging.error(f"Failed to add chat {chat_id}: {e}")
        await message.answer(
            f"Чат {chat_id} не удалось добавить. Ошибка - '{e}'\nУбедитесь, что передали корректный ID",
            reply_markup=keyboard)


# @dp.callback_query_handler(lambda query: query.data.startswith("group_details_"))
async def chat_details(callback_query: types.CallbackQuery):
    logging.info(f"Received callback 'group_details' by user {callback_query.from_user.id}")
    chat_id = str(callback_query.data.split("_")[2])  # Получаем идентификатор чата из callback
    group_info = await bot.get_chat(str(chat_id))
    chat_description = group_info['title']

    if chat_description:
        logging.info(f"Chat {chat_id} found: {chat_description}")
        await db.add_chat_title(chat_id, chat_description)
        # Создаем клавиатуру с кнопками "Удалить чат", "Изменить контекст" и "Вернуться"
        keyboard = types.InlineKeyboardMarkup()
        delete_button = types.InlineKeyboardButton("Удалить чат", callback_data=f"delete_chat_{chat_id}")
        get_punishments_button = types.InlineKeyboardButton("Получить историю блокировок",
                                                            callback_data=f"get_punishments_{chat_id}")
        back_button = types.InlineKeyboardButton("Вернуться", callback_data="admin_panel")
        notification_settings_button = types.InlineKeyboardButton("Настройки уведомлений",
                                                                  callback_data=f"notification_settings_{chat_id}")
        keyboard.add(delete_button, get_punishments_button, notification_settings_button, back_button)

        await bot.edit_message_text(chat_id=callback_query.message.chat.id,
                                    message_id=callback_query.message.message_id,
                                    text=f"Чат {chat_id}: {chat_description}", reply_markup=keyboard)
    else:
        logging.info(f"Chat {chat_id} not found.")
        await bot.answer_callback_query(callback_query.id, text=f"Чат {chat_id} не найден.")


# @dp.callback_query_handler(lambda query: query.data.startswith("delete_chat_"))
async def delete_chat(callback_query: types.CallbackQuery):
    logging.info(f"Received callback 'delete_chat' by user {callback_query.from_user.id}")
    chat_id = str(callback_query.data.split("_")[2])  # Получаем идентификатор чата из callback
    global ALLOWED_GROUPS

    try:
        await db.delete_allowed_group(int(chat_id))
        ALLOWED_GROUPS = await db.get_allowed_groups()
        await bot.answer_callback_query(callback_query.id, text=f"Чат {chat_id} удален.")
        logging.info(f"Chat {chat_id} deleted.")
    except Exception as e:
        logging.error(f"Failed to delete chat {chat_id}: {e}")
        await bot.answer_callback_query(callback_query.id, text=f"Чат {chat_id} не найден.")
        print(e, f'- не удалось удалить чат{chat_id}!')


# @dp.callback_query_handler(lambda query: query.data.startswith("get_punishments_"))
async def get_punishments(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"Received callback 'get_punishments' by user {callback_query.from_user.id}")
    chat_id = str(callback_query.data.split("_")[2])  # Получаем идентификатор чата из callback
    admin_button = types.InlineKeyboardButton("Вернуться", callback_data="admin_panel")
    keyboard = types.InlineKeyboardMarkup().add(admin_button)

    punishments = await db.get_punishments_by_chat(chat_id)

    if punishments:
        message = f"*История блокировок в чате {chat_id}:*\n"
        for punishment in punishments:
            message += f"*Punishment ID: {punishment[0]}*\n"
            message += f"User ID: {punishment[1]}\n"
            message += f"Username: {punishment[2]}\n"
            message += f"Дата: {punishment[3]}\n"
            chat_title = await bot.get_chat(str(chat_id))
            message += f"Заблокирован в чате: {punishment[4]} ({chat_title['title']})\n"
            message += f"Сообщение пользователя: {punishment[5]}\n"
            message += f"Причина: {punishment[6]}\n\n"

        await bot.send_message(callback_query.from_user.id, message, reply_markup=keyboard, parse_mode='Markdown')
    else:
        # Если данных о наказаниях нет
        await bot.send_message(callback_query.from_user.id, f"История блокировок в чате {chat_id} пуста.",
                               reply_markup=keyboard)


# @dp.callback_query_handler(lambda query: query.data == "model_change")
async def model_change(callback_query: types.CallbackQuery):
    logging.info(f"Received callback 'model_change' by user {callback_query.from_user.id}")
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("GPT-3.5 Turbo", callback_data="choose_gpt_3.5_turbo"),
        types.InlineKeyboardButton("GPT-4", callback_data="choose_gpt_4"),
        types.InlineKeyboardButton("Вернуться", callback_data="admin_panel"),
    )

    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text="Выберите модель OpenAI:",
        reply_markup=keyboard
    )


# @dp.callback_query_handler(lambda query: query.data.startswith("notification_settings_"))
async def notification_settings(callback_query: types.CallbackQuery):
    logging.info(f"Received callback 'notification_settings' by user {callback_query.from_user.id}")
    chat_id = int(callback_query.data.split("_")[2])
    chat_info = await db.get_chat_info(chat_id=chat_id)
    manual_punishment_notifications = chat_info['manual_punishment_notifications']
    auto_punishment_notifications = chat_info['auto_punishment_notifications']
    removal_punishment_notifications = chat_info['removal_punishment_notifications']
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("🟢" + " Aвтоматические наказания" if auto_punishment_notifications
                                   else '🔴' + " Aвтоматические наказания",
                                   callback_data=f"switch_auto_{chat_id}"),
        types.InlineKeyboardButton("🟢" + " Ручные наказания" if manual_punishment_notifications
                                   else '🔴' + " Ручные наказания",
                                   callback_data=f"switch_manual_{chat_id}"),
        types.InlineKeyboardButton("🟢" + " Снятие наказания" if removal_punishment_notifications
                                   else '🔴' + " Удаление наказания",
                                   callback_data=f"switch_removal_{chat_id}"),
    )
    keyboard.add(
        types.InlineKeyboardButton("Вернуться", callback_data="admin_panel")
    )
    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=f"Настройки уведомлений для чата {chat_info['chat_title']}:",
        reply_markup=keyboard
    )


async def update_notification_button_text(chat_id):
    chat_info = await db.get_chat_info(chat_id=chat_id)
    manual_punishment_notifications = chat_info['manual_punishment_notifications']
    auto_punishment_notifications = chat_info['auto_punishment_notifications']
    removal_punishment_notifications = chat_info['removal_punishment_notifications']
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("🟢" + " Aвтоматические наказания" if auto_punishment_notifications
                                   else '🔴' + " Aвтоматические наказания",
                                   callback_data=f"switch_auto_{chat_id}"),
        types.InlineKeyboardButton("🟢" + " Ручные наказания" if manual_punishment_notifications
                                   else '🔴' + " Ручные наказания",
                                   callback_data=f"switch_manual_{chat_id}"),
        types.InlineKeyboardButton("🟢" + " Снятие наказания" if removal_punishment_notifications
                                   else '🔴' + " Удаление наказания",
                                   callback_data=f"switch_removal_{chat_id}"),
    )
    keyboard.add(
        types.InlineKeyboardButton("Вернуться", callback_data="admin_panel")
    )

    return keyboard


# @dp.callback_query_handler(lambda query: query.data.startswith("switch_"))
async def switch_notification_settings(callback_query: types.CallbackQuery):
    logging.info(f"Received callback 'switch_notification_settings' by user {callback_query.from_user.id}")

    data_parts = callback_query.data.split("_")
    key = data_parts[1]
    chat_id = data_parts[2]

    await db.toggle_notification_setting(chat_id=chat_id, key=key)

    keyboard = await update_notification_button_text(chat_id)

    await bot.edit_message_reply_markup(callback_query.message.chat.id,
                                        callback_query.message.message_id,
                                        reply_markup=keyboard)


# @dp.callback_query_handler(lambda query: query.data == "choose_gpt_3.5_turbo")
async def choose_gpt_3_5_turbo(callback_query: types.CallbackQuery):
    logging.info(f"Received callback 'choose_gpt_3.5_turbo' by user {callback_query.from_user.id}")
    # Обновляем значение модели в словаре
    api_model["openaimodel"] = "gpt-3.5-turbo"
    save_api_model(api_model)
    logging.info(f"API model updated: {api_model}")
    await bot.answer_callback_query(callback_query.id, text="Модель изменена на GPT-3.5 Turbo")


# @dp.callback_query_handler(lambda query: query.data == "choose_gpt_4")
async def choose_gpt_4(callback_query: types.CallbackQuery):
    logging.info(f"Received callback 'choose_gpt_4' by user {callback_query.from_user.id}")
    # Обновляем значение модели в словаре
    api_model["openaimodel"] = "gpt-4"
    save_api_model(api_model)
    logging.info(f"API model updated: {api_model}")
    await bot.answer_callback_query(callback_query.id, text="Модель изменена на GPT-4")


# @dp.callback_query_handler(lambda query: query.data == "return_to_admin", state="*")
async def return_to_admin_panel(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"Received callback 'return_to_admin' by user {callback_query.from_user.id}")
    await callback_query.answer()
    await state.finish()
    await admin_panel(callback_query)


def register_handlers_private(dp: Dispatcher):
    dp.register_message_handler(on_start_private, commands=["start"], chat_type=ChatType.PRIVATE)
    dp.register_callback_query_handler(admin_panel, lambda query: query.data == "admin_panel")
    dp.register_callback_query_handler(add_new_chat, lambda query: query.data == "add_new_chat")
    dp.register_message_handler(handle_chat_id_input, lambda message: message.text and message.from_user.id in ADMIN_ID,
                                state=BotState.waiting_for_chat_id)
    dp.register_callback_query_handler(chat_details, lambda query: query.data.startswith("group_details_"))
    dp.register_callback_query_handler(delete_chat, lambda query: query.data.startswith("delete_chat_"))
    dp.register_callback_query_handler(get_punishments, lambda query: query.data.startswith("get_punishments_"))
    dp.register_callback_query_handler(model_change, lambda query: query.data == "model_change")
    dp.register_callback_query_handler(choose_gpt_3_5_turbo, lambda query: query.data == "choose_gpt_3.5_turbo")
    dp.register_callback_query_handler(choose_gpt_4, lambda query: query.data == "choose_gpt_4")
    dp.register_callback_query_handler(return_to_admin_panel, lambda query: query.data == "return_to_admin", state="*")
    dp.register_callback_query_handler(notification_settings,
                                       lambda query: query.data.startswith("notification_settings_"))
    dp.register_callback_query_handler(switch_notification_settings, lambda query: query.data.startswith("switch_"))
    logging.info("Private handlers registered")
