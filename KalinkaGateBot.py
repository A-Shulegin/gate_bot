import pymysql
import telebot
from telebot import types
import requests
from datetime import datetime, timedelta

class CallToolsException(Exception):
    pass

def create_call(campaign_id, phonenumber, text=None, speaker='Tatyana'):
  resp = requests.get(
      'https://zvonok.com/manager/cabapi_external/api/v1/phones/call/', {
          'public_key': '504ae08958e866bf0c9dbaff49c5f5ed',
          'phone': phonenumber,
          'campaign_id': campaign_id,
          'text': text,
          'speaker': speaker,
      },
      timeout=30)
  ret = resp.json()
  return ret

TOKEN = '6957262747:AAFrIb_Z14WBwVNVC7Ed4Azf2ZGHScz3TPs'
ADMIN_USER_ID = '961214635'
DB_HOST = 'viaduct.proxy.rlwy.net'
DB_USER = 'root'
DB_PASSWORD = '-4EBh3ad2B2EBCd2BD246hf62Hg-hf6h'
DB_NAME = 'railway'
DB_PORT = 15358

connection = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT
)
cursor = connection.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_states (
    user_id BIGINT PRIMARY KEY,
    granted INTEGER
    );
''')
connection.commit()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS access_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES user_states(user_id)
    );
''')
connection.commit()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT,
    message_id BIGINT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES user_states(user_id)
    );
''')
connection.commit()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT,
    username TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
''')
connection.commit()

bot = telebot.TeleBot(TOKEN)

# Инициализация базы данных, включая пользователя с ID ADMIN_USER_ID
cursor.execute('INSERT IGNORE INTO user_states (user_id, granted) VALUES (%s, %s)', (int(ADMIN_USER_ID), 1))
connection.commit()

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id

    cursor.execute('SELECT granted FROM user_states WHERE user_id = %s', (user_id,))
    result = cursor.fetchone()

    if result is None:
        cursor.execute('INSERT INTO user_states (user_id, granted) VALUES (%s, 0)', (user_id,))
        connection.commit()

        granted_status = 0
    else:
        granted_status = int(result[0])

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_open_gate = types.KeyboardButton("Открыть ворота")
    button_request_access = types.KeyboardButton("Запросить доступ")

    if user_id != int(ADMIN_USER_ID):
        markup.add(button_request_access)

    markup.add(button_open_gate)

    bot.send_message(user_id, "Привет! Выберите действие:", reply_markup=markup)

    if user_id == int(ADMIN_USER_ID):
        admin_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        admin_markup.add(types.KeyboardButton("Открыть ворота"))
        admin_markup.add(types.KeyboardButton("Пользователи с доступом"))
        admin_markup.add(types.KeyboardButton("Удалить доступ"))
        admin_markup.add(types.KeyboardButton("Показать лог"))
        bot.send_message(user_id, "Добро пожаловать, администратор!", reply_markup=admin_markup)
        
def insert_log_entry(user_id):
    user_info = bot.get_chat(user_id)
    cursor.execute('INSERT INTO log (user_id, username) VALUES (%s, %s)', (user_id, user_info.username))
    connection.commit()

def clean_old_logs():
    week_ago = datetime.now() - timedelta(days=7)
    cursor.execute('DELETE FROM log WHERE timestamp < %s', (week_ago.strftime('%Y-%m-%d %H:%M:%S'),))
    connection.commit()
            
@bot.message_handler(func=lambda message: message.text == 'Открыть ворота')
def open_gate(message):
    user_id = message.chat.id

    cursor.execute('SELECT granted FROM user_states WHERE user_id = %s', (user_id,))
    result = cursor.fetchone()

    if result and result[0]:
        callback = create_call(17722404, +79218738724)
        if 'status' in callback:
            bot.send_message(user_id, "Возникла ошибка, свяжитесь с нами.")
        else:
            bot.send_message(user_id, "Ворота открыты!")

            # Вставляем запись в лог
            insert_log_entry(user_id)
            
            # Очищаем старые записи в логе
            clean_old_logs()
    else:
        bot.send_message(user_id, "У вас нет доступа!")

@bot.message_handler(func=lambda message: message.text == 'Запросить доступ' and message.chat.id != int(ADMIN_USER_ID))
def request_access(message):
    user_id = message.chat.id
    user_invite_text = f"[Перейти в чат](tg://user?id={user_id})"
    user_name = message.from_user.username

    cursor.execute('SELECT granted FROM user_states WHERE user_id = %s', (user_id,))
    result = cursor.fetchone()

    if result and result[0]:
        bot.send_message(user_id, "У вас уже есть доступ.")
    else:
        cursor.execute('SELECT * FROM user_states WHERE user_id = %s', (user_id,))
        existing_user = cursor.fetchone()

        if not existing_user:
            cursor.execute('INSERT INTO user_states (user_id, granted) VALUES (%s, 0)', (user_id,))
            connection.commit()

        cursor.execute('SELECT user_id FROM access_requests WHERE user_id = %s', (user_id,))
        request_id = cursor.fetchone()

        if request_id:
            bot.send_message(user_id, "Вы уже отправили запрос на доступ. Ожидайте ответа.")
        else:
            # Вставляем запрос на доступ в новую таблицу
            cursor.execute('INSERT INTO access_requests (user_id) VALUES (%s)', (user_id,))
            connection.commit()
            markup = types.InlineKeyboardMarkup()
            button_grant_access = types.InlineKeyboardButton("Дать доступ", callback_data=f'grant_{user_id}')
            button_decline_access = types.InlineKeyboardButton("Отклонить", callback_data=f'decline_{user_id}')
            markup.row(button_grant_access, button_decline_access)
            msg = bot.send_message(int(ADMIN_USER_ID),
                                   f"Получен запрос на доступ от пользователя @{user_name} ({user_id}) {user_invite_text}",
                                   reply_markup=markup, parse_mode="Markdown")
            # Записываем информацию о сообщении администратора в таблицу admin_messages
            cursor.execute('INSERT INTO admin_messages (user_id, message_id) VALUES (%s, %s)', (user_id, msg.message_id))
            connection.commit()

@bot.callback_query_handler(func=lambda call: call.data.startswith(('grant_', 'decline_')))
def process_access_decision(call):
    user_id = int(call.data.split('_')[1])
    admin_user_id = call.from_user.id
    decision = call.data.split('_')[0]
    if decision == 'grant':
        cursor.execute('UPDATE user_states SET granted = %s WHERE user_id = %s', (1, user_id))
        connection.commit()
        cursor.execute('SELECT message_id FROM admin_messages WHERE user_id = %s', (user_id,))
        result = cursor.fetchone()
        bot.edit_message_text("Доступ успешно выдан!", ADMIN_USER_ID, result[0])
        bot.send_message(user_id, "Доступ успешно выдан!")
    elif decision == 'decline':
        cursor.execute('SELECT message_id FROM admin_messages WHERE user_id = %s', (user_id,))
        result = cursor.fetchone()
        bot.edit_message_text("Запрос в доступе отклонен.", ADMIN_USER_ID, result[0])
        bot.send_message(user_id, "Запрос в доступе отклонен.")

    # Удаляем запрос из таблицы access_requests
    cursor.execute('DELETE FROM access_requests WHERE user_id = %s', (user_id,))
    connection.commit()

    # Удаляем сообщение из таблицы admin_messages
    cursor.execute('DELETE FROM admin_messages WHERE user_id = %s', (user_id,))
    connection.commit()

@bot.message_handler(func=lambda message: message.text == 'Пользователи с доступом' and message.chat.id == int(ADMIN_USER_ID))
def users_with_access(message):
    admin_user_id = int(ADMIN_USER_ID)

    cursor.execute('SELECT user_id FROM user_states WHERE granted = 1')
    users_with_access = [user_id[0] for user_id in cursor.fetchall()]

    if users_with_access:
        users_info = []
        for user_id in users_with_access:
            user_chat = bot.get_chat(user_id)
            user_info = f"ID: {user_id}, Ник: @{user_chat.username}"

            user_invite_text = f"[Перейти в чат](tg://user?id={user_id})"
            user_info += f", {user_invite_text}"

            users_info.append(user_info)

        bot.send_message(admin_user_id, f"Пользователи с доступом:\n" + "\n".join(users_info), parse_mode="Markdown")
    else:
        bot.send_message(admin_user_id, "Нет пользователей с доступом.")

@bot.message_handler(func=lambda message: message.text == 'Удалить доступ' and message.chat.id == int(ADMIN_USER_ID))
def remove_access(message):
    user_id = message.chat.id

    if user_id == int(ADMIN_USER_ID):
        cursor.execute('SELECT user_id FROM user_states WHERE granted = 1')
        users_with_access = [user[0] for user in cursor.fetchall()]

        if users_with_access:
            markup = types.InlineKeyboardMarkup()

            for user_id in users_with_access:
                if user_id != int(ADMIN_USER_ID):
                    user_info = f"@{bot.get_chat(user_id).username} (ID: {user_id})"
                    button_remove_access = types.InlineKeyboardButton(f"Удалить доступ {user_info}", callback_data=f'remove_{user_id}')
                    markup.row(button_remove_access)

            bot.send_message(ADMIN_USER_ID, "Выберите пользователя для удаления доступа:", reply_markup=markup)
        else:
            bot.send_message(ADMIN_USER_ID, "Нет пользователей с доступом для удаления.")
    else:
        bot.send_message(ADMIN_USER_ID, "У вас нет прав на удаление доступа.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('remove_'))
def remove_access_callback(call):
    admin_user_id = call.from_user.id
    user_id_to_remove = int(call.data.split('_')[1])
    
    cursor.execute('UPDATE user_states SET granted = 0 WHERE user_id = %s', (user_id_to_remove,))
    connection.commit()

    bot.edit_message_text(f"Доступ пользователя @{bot.get_chat(user_id_to_remove).username} (ID: {user_id_to_remove}) удален.",
                          ADMIN_USER_ID, call.message.message_id)

@bot.message_handler(func=lambda message: message.text == 'Показать лог' and message.chat.id == int(ADMIN_USER_ID))
def view_log(user_id):
    # Вычисляем время 24 часа назад от текущего момента
    day_ago = datetime.now() - timedelta(days=1)

    # Извлекаем записи из лога только за последние сутки
    cursor.execute('SELECT CONVERT_TZ(timestamp, "+00:00", "+03:00") AS moscow_time, id, username FROM log WHERE timestamp >= %s ORDER BY timestamp DESC', (day_ago.strftime('%Y-%m-%d %H:%M:%S'),))
    log_entries = cursor.fetchall()

    if log_entries:
        log_text = "Записи в логе за последние сутки:\n"
        for entry in log_entries:
            log_text += f"ID: {entry[1]}, Ник: @{entry[2]}, Время: {entry[0]}\n"

        bot.send_message(ADMIN_USER_ID, log_text)
    else:
        bot.send_message(ADMIN_USER_ID, "Лог за последние сутки пуст.")
        
if __name__ == '__main__':
    bot.polling(none_stop=True)

connection.close()