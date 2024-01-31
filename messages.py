from auth_data import MAX_FREE_USAGE_LIMIT
import markups as m
from auth_data import admins


def start_message(user_data):
    msg = f"👋 Добро пожаловать, {user_data['first_name']}!\n\n" \
          f"⬆ * Загрузите таблицу с вместимостью товаров в коробку (2 столбца: 'Баркод' и 'Кратность').\n\n" \
          f"⬆ ** Загрузите таблицу с количеством товаров (2 столбца: 'Баркод' и 'Количество').\n\n" \
          f"⬆ *** Выполните расчет количества коробок.\n\n" \
          f"⬆ **** Сгенерируйте на WB названия коробок.\n\n" \
          f"⬆ ***** Нажмите кнопку «{m.GENERATE_REPORT_TEXT}».\n\n" \
          f"Всего без подписки Вы можете сделать {MAX_FREE_USAGE_LIMIT} бесплатных попыток генерации отчета.\n" \
          f"Осталось попыток: {user_data['usage_limit']}."
    return msg


def success_message_for_wildberries(new_limit):
    return f"🎉 Поздравляем! Этот файл можно загрузить на Wildberries.\nОсталось попыток: {new_limit}"

def instruction_for_warehouse_message(new_limit):
    return f"📦 А вот и инструкция для склада поспела!\nОсталось попыток: {new_limit}"


def exceeded_limit_message(user_data):
    admins_contact = "\n".join([f"👤 @{admin}" for admin in admins])
    return (f"⛔ {user_data['first_name']}, Ваш лимит попыток генерации отчета исчерпан.\n\n"
            "Если Вы хотите и дальше использовать функционал бота, можете связаться с админами:\n"
            f"{admins_contact}")


def reset_success_message(first_name: str) -> str:
    return f"🗑️✅ {first_name}, все ранее загруженные файлы сброшены."
