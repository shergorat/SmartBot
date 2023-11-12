import aiosqlite
import os
import datetime

basedir = os.path.dirname(os.path.abspath(__file__))
database_path = basedir + os.sep + "telegram.db"


class Database:
    def __init__(self):
        self.database_path = database_path

    async def initialize(self):
        async with aiosqlite.connect(self.database_path) as conn:
            cursor = await conn.cursor()
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS telegram_channel_history (
                    message_id INTEGER PRIMARY KEY,
                    date DATATIME,
                    chat_id INTEGER,
                    message_text TEXT,
                    user_id INTEGER,
                    user_name TEXT
                )
            ''')
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS users_base (
                    user_id INTEGER PRIMARY KEY,
                    join_date DATATIME,
                    username TEXT
                )
            ''')
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS spamers_base (
                    user_id INTEGER PRIMARY KEY,
                    date DATATIME,
                    banned_in_channel STRING,
                    user_message STRING,
                    reason STRING
                )
            ''')
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS punishments_base (
                    punishment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username STRING,
                    date DATATIME,
                    banned_in_channel STRING,
                    user_message STRING,
                    reason STRING
                )
            ''')
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS chat_base (
                    chat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATATIME
                )
            ''')
            await conn.commit()
            logging.info("Database was successfully initialized")

    async def add_new_user(self, user_id):
        current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self.database_path) as conn:
            await conn.execute('''
                INSERT INTO users_base (user_id, join_date)
                VALUES (?, ?)
            ''', (user_id, current_date))
            await conn.commit()

    async def add_user(self, user_id, join_date):
        async with aiosqlite.connect(self.database_path) as conn:
            await conn.execute('''
                INSERT INTO users_base (user_id, join_date)
                VALUES (?, ?)
            ''', (user_id, join_date))
            await conn.commit()

    async def get_user(self, user_id):
        async with aiosqlite.connect(self.database_path) as conn:
            await conn.execute('''
                SELECT * FROM users_base WHERE user_id = ?
            ''', (user_id,))
            await conn.commit()

    async def add_allowed_chat(self, chat_id):
        current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self.database_path) as conn:
            await conn.execute('''
                INSERT INTO chat_base (chat_id, date)
                VALUES (?, ?)
            ''', (chat_id, current_date))
            await conn.commit()

    async def get_allowed_groups(self):
        async with aiosqlite.connect(self.database_path) as conn:
            cursor = await conn.cursor()
            await cursor.execute('SELECT ALL chat_id FROM chat_base')
            allowed_chats = await cursor.fetchall()
            return allowed_chats

    async def delete_allowed_group(self, chat_id):
        async with aiosqlite.connect(self.database_path) as conn:
            cursor = await conn.cursor()
            await cursor.execute('DELETE FROM chat_base WHERE chat_id = ?', (chat_id,))
            await conn.commit()

    async def insert_chat_message(self, chat_id, message_id, message_text, user_id, user_name):
        current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self.database_path) as conn:
            await conn.execute('''
                INSERT INTO telegram_channel_history (message_id, date, chat_id, message_text, user_id, user_name)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (message_id, current_date, chat_id, message_text, user_id, user_name))
            await conn.commit()

    async def get_message_count_by_user(self, user_id, chat_id):
        async with aiosqlite.connect(self.database_path) as conn:
            cursor = await conn.cursor()
            await cursor.execute('SELECT COUNT(*) FROM telegram_channel_history WHERE user_id = ? AND chat_id = ?',
                                 (user_id, chat_id))
            message_count = await cursor.fetchone()
        return message_count[0] if message_count else 0

    async def insert_punishment(self, user_id, username, chat_id, message_text, reason):
        current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self.database_path) as conn:
            await conn.execute('''
                INSERT INTO punishments_base (user_id, username, date, banned_in_channel, user_message, reason)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, current_date, chat_id, message_text, reason))
            await conn.commit()

    async def get_punishments_by_chat(self, chat_id):
        async with aiosqlite.connect(self.database_path) as conn:
            cursor = await conn.cursor()
            await cursor.execute('SELECT * FROM punishments_base WHERE banned_in_channel = ?', (chat_id,))
            punishments = await cursor.fetchall()
        return punishments

    async def insert_spamer(self, user_id, chat_id, message_text, reason):
        current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self.database_path) as conn:
            await conn.execute('''
                INSERT INTO spamers_base (user_id, date, banned_in_channel, user_message, reason)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, current_date, chat_id, message_text, reason))
            await conn.commit()

    async def remove_spamer(self, user_id):
        async with aiosqlite.connect(self.database_path) as conn:
            cursor = await conn.cursor()
            await cursor.execute('''
                DELETE FROM spamers_base
                WHERE user_id = ? 
            ''', (user_id,))
            await conn.commit()

    async def is_spamer(self, user_id):
        async with aiosqlite.connect(self.database_path) as conn:
            cursor = await conn.cursor()
            await cursor.execute('SELECT * FROM spamers_base WHERE user_id = ?', (user_id,))
            spamer_data = await cursor.fetchone()
        return True if spamer_data is not None else False

    async def get_error_messages(self):
        async with aiosqlite.connect(self.database_path) as conn:
            cursor = await conn.cursor()
            await cursor.execute(
                'SELECT user_name, message_id, message_text, chat_id FROM telegram_channel_history WHERE status = "error"')
            error_messages = await cursor.fetchall()
        return error_messages

    async def get_user_id_by_username(self, username):
        async with aiosqlite.connect(self.database_path) as conn:
            cursor = await conn.cursor()
            # Выбираем user_id по username из последней записи в таблице
            await cursor.execute(
                'SELECT user_id FROM telegram_channel_history WHERE user_name = ? ORDER BY message_id DESC LIMIT 1',
                (username,))
            row = await cursor.fetchone()
            if row:
                user_id = row[0]
                return int(user_id)
            else:
                return None
