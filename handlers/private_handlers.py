import logging
import time
from datetime import datetime

from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ChatType
from aiogram.utils.exceptions import ChatNotFound

from bot import bot, dp, db
from config import *
from functions import openai_question, order_alert
from json_manager import api_model, save_api_model, load_api_model

ALLOWED_GROUPS = None


class BotState(StatesGroup):
    waiting_for_question = State()  # Состояние для ожидания вопроса
    waiting_for_chat_id = State()  # Состояние для ожидания id чата


# @dp.message_handler(commands = ["start"], chat_type=ChatType.PRIVATE)
async def on_start_private(message: types.Message, state: FSMContext):
    logging.info(f"User {message.from_user.id} started bot")
    await state.finish()
    user_id = message.from_user.id
    services_button = types.InlineKeyboardButton("Я хочу консультацию человека", callback_data="services")
    question_button = types.InlineKeyboardButton("Я хочу задать вопрос", callback_data="question")

    if user_id in ADMIN_ID:
        admin_button = types.InlineKeyboardButton("Админ-панель", callback_data="admin_panel")

        keyboard = types.InlineKeyboardMarkup().add(admin_button, services_button, question_button)
    else:
        keyboard = types.InlineKeyboardMarkup().add(services_button, question_button)

    message_text = (
        "Привет! Это бот-помощник компании ЮрЮг\n"
        "Вопросы по работе бота можно направлять *@admin*"
    )
    await message.answer(message_text, reply_markup=keyboard, parse_mode='Markdown')


async def on_retry_to_start(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"User {callback_query.from_user.id} started bot")
    await state.finish()
    user_id = callback_query.from_user.id
    services_button = types.InlineKeyboardButton("Я хочу консультацию человека", callback_data="services")
    question_button = types.InlineKeyboardButton("Я хочу задать вопрос", callback_data="question")

    if user_id in ADMIN_ID:
        admin_button = types.InlineKeyboardButton("Админ-панель", callback_data="admin_panel")

        keyboard = types.InlineKeyboardMarkup().add(admin_button, services_button, question_button)
    else:
        keyboard = types.InlineKeyboardMarkup().add(services_button, question_button)

    message_text = (
        "Привет! Это бот-помощник компании ЮрЮг\n"
        "Вопросы по работе бота можно направлять *@admin*"
    )
    await bot.edit_message_text(message_id=callback_query.message.message_id, chat_id=callback_query.message.chat.id,
                                text=message_text, reply_markup=keyboard,
                                parse_mode='Markdown')


# @dp.callback_query_handler(lambda query: query.data == "question")
async def bot_question(callback_query: types.CallbackQuery):
    logging.info(f"User {callback_query.from_user.id} opened admin panel")

    message_text = "Задайте ваш вопрос:"

    keyboard = types.InlineKeyboardMarkup()
    return_button = types.InlineKeyboardButton("Вернуться", callback_data="return_to_start")
    keyboard.add(return_button)

    await bot.edit_message_text(chat_id=callback_query.message.chat.id,
                                message_id=callback_query.message.message_id,
                                text=message_text, reply_markup=keyboard)
    await BotState.waiting_for_question.set()


# @dp.message_handler(lambda message: message.text,
#                     state=BotState.waiting_for_question)
async def handle_question(message: types.Message, state: FSMContext):
    question = message.text
    await state.update_data(question=question)  # Сохраняем идентификатор чата в состоянии FSM
    return_button = types.InlineKeyboardButton("Вернуться", callback_data="return_to_start")
    keyboard = types.InlineKeyboardMarkup().add(return_button)
    await state.finish()

    command_parts = message.text.split()
    if len(command_parts) > 2:
        question_text = " ".join(command_parts[0:])
        print(question_text, '#')

        try:
            answer = await openai_question(question_text)
            await message.reply(f"*Ответ*: \n{answer}", parse_mode='Markdown', reply_markup=keyboard)
            status = 'complete'

        except Exception as e:
            print(e.with_traceback, e, '-error!!!')
            await message.answer(f"@{message.from_user.username} возникли технические неполадки.\n"
                                 f"Я запомнил ваш вопрос и отвечу сразу, как появится возможность.",
                                 parse_mode='HTML', reply_markup=keyboard)
            status = 'error'

    elif len(command_parts) == 2:
        await message.answer("Пожалуйста, задайте более осознанный вопрос", reply_markup=keyboard)


# @dp.callback_query_handler(lambda query: query.data == "services")
async def show_services(callback_query: types.CallbackQuery):
    message_text = "Выберите услугу:"
    services = await db.get_services()

    keyboard = types.InlineKeyboardMarkup()
    for service in services:
        service_id, service_title, service_description, service_price = service
        button_text = service_title
        button_callback = f"service_{service_id}"
        service_button = types.InlineKeyboardButton(button_text, callback_data=button_callback)
        keyboard.add(service_button)

    keyboard.add(types.InlineKeyboardButton("Вернуться", callback_data="return_to_start"))

    await bot.edit_message_text(chat_id=callback_query.message.chat.id,
                                message_id=callback_query.message.message_id,
                                text=message_text, reply_markup=keyboard)


# @dp.callback_query_handler(lambda query: query.data == "services_")
async def buy_service(callback_query: types.CallbackQuery):
    service_id = int(callback_query.data.split('_')[1])
    service = await db.get_service(service_id)

    if service:
        service_id, service_title, service_description, service_price = service
        message_text = (f"Подробнее об услуге:\n\n"
                        f"Название: {service_title}\n"
                        f"Описание: {service_description}\n"
                        f"Цена: {service_price} рублей\n"
                        f"тестовая карта для оплаты - 1111 1111 1111 1026, 12/22, CVC 000")

        keyboard = types.InlineKeyboardMarkup()
        # Кнопка для перехода к оплате
        pay_button = types.InlineKeyboardButton("Перейти к оплате", callback_data=f"pay_service_{service_id}")
        # Кнопка для возврата на начальный экран
        return_button = types.InlineKeyboardButton("Вернуться", callback_data="return_to_start")

        keyboard.add(pay_button, return_button)

        await bot.edit_message_text(chat_id=callback_query.message.chat.id,
                                    message_id=callback_query.message.message_id,
                                    text=message_text, reply_markup=keyboard)
    else:
        await bot.edit_message_text(chat_id=callback_query.message.chat.id,
                                    message_id=callback_query.message.message_id,
                                    text="Услуга не найдена.",
                                    reply_markup=types.InlineKeyboardMarkup().add(
                                        types.InlineKeyboardButton("Вернуться", callback_data="return_to_start")))


# @dp.callback_query_handler(lambda query: query.data == "pay_service_")
async def payment_service(callback_query: types.CallbackQuery):
    service_id = int(callback_query.data.split('_')[2])
    service = await db.get_service(service_id)
    service_title = service[1]
    service_description = service[2]
    service_price = service[3]
    await bot.send_invoice(
        chat_id=callback_query.from_user.id,
        title=service_title,
        description=service_description,
        payload=f'pay_service_{service_id}_{service_price}',
        provider_token=PAYMENT_TOKEN,
        currency='RUB',
        start_parameter='subscribe_bot',
        prices=[types.LabeledPrice(label=service_title, amount=service_price * 100)]
    )


# @dp.pre_checkout_query_handler()
async def procces_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


# @dp.message_handler(content_types=types.ContentType.SUCCESSFUL_PAYMENT)
async def process_successful_payment(message: types.Message):
    user_id = message.from_user.id

    payload_data = message.successful_payment.invoice_payload.split('_')
    service_id = int(payload_data[2])
    service_price = int(payload_data[3])
    # Фиксируем текущее время после успешной оплаты
    current_time = int(time.time())
    await db.add_order(service_id, user_id, message.from_user.username, service_price)
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Вернуться", callback_data="return_to_start"))
    await bot.send_message(user_id, "Оплата прошла успешно! С вами в ближайшее время свяжется наш сотрудник",
                           reply_markup=keyboard)
    await order_alert(ADMIN_ID, service_id)


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
    orders_button = types.InlineKeyboardButton("Заказы", callback_data="orders_list")
    back_button = types.InlineKeyboardButton("Вернуться", callback_data="return_to_start")
    keyboard.add(add_chat_button, model_button, orders_button, back_button)

    await bot.edit_message_text(chat_id=callback_query.message.chat.id,
                                message_id=callback_query.message.message_id,
                                text=message_text, reply_markup=keyboard)


# @dp.callback_query_handler(lambda query: query.data.startswith("orders_list"))
async def show_orders(callback_query: types.CallbackQuery, state: FSMContext):
    admin_button = types.InlineKeyboardButton("Вернуться", callback_data="admin_panel")
    keyboard = types.InlineKeyboardMarkup().add(admin_button)

    orders = await db.get_orders()

    if orders:
        message = f"Список заказов:\n\n"
        for order in orders:
            message += f"\nЗаказ ID: {order[0]}\n"
            message += f"Услуга ID: {order[1]}\n"
            message += f"Пользователь ID: {order[2]}\n"
            message += f"Username: {order[3]}\n"
            message += f"Оплатил: {order[4]}\n"
            message += f"Дата: {order[5]}\n"
        print(message)
        await bot.send_message(chat_id=callback_query.message.chat.id,
                               text=message, reply_markup=keyboard)
    else:
        await bot.send_message(callback_query.from_user.id, f"История заказов пуста.",
                               reply_markup=keyboard)


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
        message = f"История блокировок в чате {chat_id}:\n\n"
        for punishment in punishments:
            message += f"Punishment ID: {punishment[0]}\n"
            message += f"User ID: {punishment[1]}\n"
            message += f"Username: {punishment[2]}\n"
            message += f"Дата: {punishment[3]}\n"
            chat_title = await bot.get_chat(str(chat_id))
            message += f"Заблокирован в чате: {punishment[4]} ({chat_title['title']})\n"
            message += f"Сообщение пользователя: {punishment[5]}\n"
            message += f"Причина: {punishment[6]}\n\n"
        print(message)
        await bot.send_message(chat_id=callback_query.message.chat.id,
                               text=message, reply_markup=keyboard)
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


# @dp.callback_query_handler(lambda query: query.data == "return_to_start", state="*")
async def return_to_start(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info(f"Received callback 'return_to_start' by user {callback_query.from_user.id}")
    await callback_query.answer()
    await state.finish()
    await on_retry_to_start(callback_query, state)


def register_handlers_private(dp: Dispatcher):
    dp.register_message_handler(on_start_private, commands=["start"], chat_type=ChatType.PRIVATE)
    dp.register_callback_query_handler(admin_panel, lambda query: query.data == "admin_panel")
    dp.register_callback_query_handler(bot_question, lambda query: query.data == "question")
    dp.register_callback_query_handler(show_services, lambda query: query.data == "services")
    dp.register_callback_query_handler(add_new_chat, lambda query: query.data == "add_new_chat")
    dp.register_message_handler(handle_chat_id_input, lambda message: message.text and message.from_user.id in ADMIN_ID,
                                state=BotState.waiting_for_chat_id)
    dp.register_message_handler(handle_question, lambda message: message.text,
                                state=BotState.waiting_for_question)
    dp.register_callback_query_handler(chat_details, lambda query: query.data.startswith("group_details_"))
    dp.register_callback_query_handler(payment_service, lambda query: query.data.startswith("pay_service_"))
    dp.register_pre_checkout_query_handler(procces_pre_checkout_query, lambda query: True)
    dp.register_message_handler(process_successful_payment, content_types=types.ContentTypes.SUCCESSFUL_PAYMENT)
    dp.register_callback_query_handler(delete_chat, lambda query: query.data.startswith("delete_chat_"))
    dp.register_callback_query_handler(show_orders, lambda query: query.data == "orders_list")
    dp.register_callback_query_handler(get_punishments, lambda query: query.data.startswith("get_punishments_"))
    dp.register_callback_query_handler(buy_service, lambda query: query.data.startswith("service_"))
    dp.register_callback_query_handler(model_change, lambda query: query.data == "model_change")
    dp.register_callback_query_handler(choose_gpt_3_5_turbo, lambda query: query.data == "choose_gpt_3.5_turbo")
    dp.register_callback_query_handler(choose_gpt_4, lambda query: query.data == "choose_gpt_4")
    dp.register_callback_query_handler(return_to_admin_panel, lambda query: query.data == "return_to_admin", state="*")
    dp.register_callback_query_handler(return_to_start, lambda query: query.data == "return_to_start", state="*")
    dp.register_callback_query_handler(notification_settings,
                                       lambda query: query.data.startswith("notification_settings_"))
    dp.register_callback_query_handler(switch_notification_settings, lambda query: query.data.startswith("switch_"))
    logging.info("Private handlers registered")
