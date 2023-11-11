import logging

from aiogram import Bot
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import Dispatcher

from config import TOKEN
from database import Database

lock_file = 'bot.lock'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
db = Database()
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


async def on_startup(dp):
    await db.initialize()


async def on_shutdown(dp):
    storage.close()
    bot.close()


if __name__ == '__main__':
    from aiogram import executor
    from handlers.group_handlers import register_handlers_group
    from handlers.private_handlers import register_handlers_private

    register_handlers_group(dp)
    register_handlers_private(dp)
    dp.middleware.setup(LoggingMiddleware())

    executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown)
