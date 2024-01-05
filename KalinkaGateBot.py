import telebot
import requests
from telebot import types

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

# Инициализация бота
bot = telebot.TeleBot(TOKEN)

# Словарь для хранения состояний пользователя (в данном примере - флаг разрешения открытия ворот)
user_states = {}
# Словарь для хранения текущего сообщения администратора
admin_messages = {}
# Словарь для хранения запросов на доступ
access_requests = {}
# Словарь для отслеживания отправленных запросов на доступ пользователями
user_requests = {}


@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    user_states.setdefault(user_id, {'granted': False})

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_open_gate = types.KeyboardButton("Открыть ворота")
    button_request_access = types.KeyboardButton("Запросить доступ")

    # Проверяем, не является ли пользователь админом
    if user_id != int(ADMIN_USER_ID):
        markup.add(button_request_access)

    markup.add(button_open_gate)

    bot.send_message(user_id, "Привет! Выберите действие:", reply_markup=markup)

    if user_id == int(ADMIN_USER_ID):
        user_states[user_id]['granted'] = True
        admin_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        admin_markup.add(types.KeyboardButton("Открыть ворота"))
        admin_markup.add(types.KeyboardButton("Пользователи с доступом"))
        admin_markup.add(types.KeyboardButton("Удалить доступ"))
        bot.send_message(user_id, "Добро пожаловать, администратор!", reply_markup=admin_markup)


@bot.message_handler(func=lambda message: message.text == 'Открыть ворота')
def open_gate(message):
    user_id = message.chat.id

    if user_states.get(user_id, {}).get('granted', False):
        callback = create_call(17722404, +79218738724)
        if 'status' in callback:
            bot.send_message(user_id, "Возникла ошибка, свяжитесь с нами.")
        else:
            bot.send_message(user_id, "Ворота открыты!")
    else:
        bot.send_message(user_id, "У вас нет доступа!")


@bot.message_handler(func=lambda message: message.text == 'Запросить доступ' and message.chat.id != int(ADMIN_USER_ID))
def request_access(message):
    user_id = message.chat.id
    user_name = message.from_user.username

    # Проверяем, есть ли у пользователя уже доступ
    if user_states.get(user_id, {}).get('granted', False):
        bot.send_message(user_id, "У вас уже есть доступ.")
    else:
        # Проверяем, отправлял ли пользователь уже запрос на доступ
        if user_requests.get(user_id, False):
            bot.send_message(user_id, "Вы уже отправили запрос на доступ. Ожидайте ответа.")
        else:
            user_requests[user_id] = True
            access_requests[user_id] = user_name
            markup = types.InlineKeyboardMarkup()
            button_grant_access = types.InlineKeyboardButton("Дать доступ", callback_data=f'grant_{user_id}')
            button_decline_access = types.InlineKeyboardButton("Отклонить", callback_data=f'decline_{user_id}')
            markup.row(button_grant_access, button_decline_access)

            # Отправим новое сообщение
            msg = bot.send_message(int(ADMIN_USER_ID),
                                   f"Получен запрос на доступ от пользователя @{user_name} ({user_id}).",
                                   reply_markup=markup)
            # Сохраняем ID нового сообщения для дальнейшего удаления
            admin_messages[user_id] = msg.message_id


@bot.callback_query_handler(func=lambda call: call.data.startswith(('grant_', 'decline_')))
def process_access_decision(call):
    user_id = call.message.text
    user_id = user_id[user_id.find('(') + 1:user_id.find(')')]
    admin_user_id = call.from_user.id
    decision = call.data.split('_')[0]

    user_id = int(user_id)
    if decision == 'grant':
        user_states.setdefault(user_id, {'granted': False})
        user_states[user_id]['granted'] = True
        bot.edit_message_text("Доступ успешно выдан!", ADMIN_USER_ID, admin_messages[user_id])
        bot.send_message(user_id, "Доступ успешно выдан!")
    elif decision == 'decline':
        bot.edit_message_text("Запрос в доступе отклонен.", ADMIN_USER_ID, admin_messages[user_id])
        bot.send_message(user_id, "Запрос в доступе отклонен.")

    if user_id in access_requests:
        del access_requests[user_id]
    if user_id in user_requests:
        del user_requests[user_id]


@bot.message_handler(func=lambda message: message.text == 'Пользователи с доступом' and message.chat.id == int(ADMIN_USER_ID))
def users_with_access(message):
    user_id = message.chat.id

    # Проверяем, является ли пользователь админом
    if user_id == int(ADMIN_USER_ID):
        users_with_access = [user_id for user_id, state in user_states.items() if state.get('granted', False)]

        if users_with_access:
            users_info = "\n".join([f"ID: {user_id}, Ник: @{bot.get_chat(user_id).username}" for user_id in users_with_access])
            bot.send_message(ADMIN_USER_ID, f"Пользователи с доступом:\n{users_info}")
        else:
            bot.send_message(ADMIN_USER_ID, "Нет пользователей с доступом.")
    else:
        bot.send_message(ADMIN_USER_ID, "У вас нет прав на просмотр пользователей с доступом.")


@bot.message_handler(func=lambda message: message.text == 'Удалить доступ' and message.chat.id == int(ADMIN_USER_ID))
def remove_access(message):
    user_id = message.chat.id

    # Проверяем, является ли пользователь админом
    if user_id == int(ADMIN_USER_ID):
        users_with_access = [user_id for user_id, state in user_states.items() if state.get('granted', False)]

        if users_with_access:
            markup = types.InlineKeyboardMarkup()

            for user_id in users_with_access:
                # Проверяем, что пользователь не админ
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

    # Проверяем, есть ли у пользователя доступ и он не админ
    if user_states.get(user_id_to_remove, {}).get('granted', False) and user_id_to_remove != int(ADMIN_USER_ID):
        # Удаляем доступ
        user_states[user_id_to_remove]['granted'] = False
        bot.edit_message_text(f"Доступ пользователя @{bot.get_chat(user_id_to_remove).username} (ID: {user_id_to_remove}) удален!",
                              ADMIN_USER_ID, call.message.message_id)
    elif user_id_to_remove == int(ADMIN_USER_ID):
        bot.edit_message_text("Нельзя удалить доступ у админа.", ADMIN_USER_ID, call.message.message_id)
    else:
        bot.edit_message_text("У пользователя уже нет доступа.", ADMIN_USER_ID, call.message.message_id)

if __name__ == '__main__':
    bot.polling(none_stop=True)