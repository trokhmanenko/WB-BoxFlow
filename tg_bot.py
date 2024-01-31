from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from auth_data import bot_token, admins
from db import Database
import logging
import messages as msg
import markups
import main
from aiogram.types import InputFile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=bot_token)
dp = Dispatcher(bot)
db = Database("database.db")
db.initialize_database()


# Обработчик команды /start
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_data = db.create_user(message)
    await message.answer(msg.start_message(user_data), reply_markup=markups.main_keyboard)


@dp.message_handler(content_types=types.ContentType.DOCUMENT)
async def handle_docs(message: types.Message):
    file_name = message.document.file_name
    user_id = message.from_user.id
    user_data = db.get_row_as_dict({'user_id': user_id})
    bytes_file = (await bot.download_file_by_id(message.document.file_id)).read()
    dfs = main.open_excel(bytes_file)

    if dfs is None or not dfs:
        await message.reply(f"Не удалось обработать файл '{file_name}'. Проверьте формат файла.")
        return

        # Выбор функций проверки в зависимости от количества коробок
    if user_data['amount_of_boxes'] > 0:
        file_type_functions = [
            (main.is_box_capacity, 'box_capacity_id', "таблица с вместимостью товаров в коробку"),
            (main.is_items_to_ship, 'items_to_ship_id', "таблица с количеством товаров"),
            (main.is_boxes_id, 'boxes_id', "сгенерированные WB названия коробок"),
        ]
    else:
        file_type_functions = [
            (main.is_box_capacity, 'box_capacity_id', "таблица с вместимостью товаров в коробку"),
            (main.is_items_to_ship, 'items_to_ship_id', "таблица с количеством товаров"),
        ]

    for data in dfs:
        sheet_name = data['name']
        df = data['df']
        for check_function, table_name, description in file_type_functions:
            result = check_function(df, user_data)
            if result:
                db.save_dataframe(user_id, table_name, df)
                if table_name != 'boxes_id':
                    db.reset_amount_of_boxes(user_id)
                    db.reset_file_ids(user_id, ['boxes_id'])
                await message.reply(
                    f"Лист '{sheet_name}' в файле '{file_name}' успешно загружен как {description}.")
                break
            elif isinstance(result, str):  # Если функция возвращает строку, значит обнаружена ошибка
                await message.reply(f"Ошибка в листе '{sheet_name}' файла '{file_name}': {result}")
                break
        else:
            await message.reply(f"Лист '{sheet_name}' в файле '{file_name}' не удалось идентифицировать.")


@dp.message_handler(lambda message: message.text == markups.COUNT_BOXES_TEXT)
async def handle_count_boxes(message: types.Message):
    user_id = message.from_user.id
    await message.delete()
    user_data = db.get_row_as_dict({'user_id': user_id})

    missing_steps = []
    if not user_data.get('box_capacity_id'):
        missing_steps.append(
            " * Загрузите таблицу с вместимостью товаров в коробку (2 столбца: 'Баркод' и 'Кратность').")
    if not user_data.get('items_to_ship_id'):
        missing_steps.append(" ** Загрузите таблицу с количеством товаров (2 столбца: 'Баркод' и 'Количество').")
    # if user_data.get('amount_of_boxes', 0) <= 0:
    #     missing_steps.append("3. Выполните расчет количества коробок.")
    # if not user_data.get('boxes_id'):
    #     missing_steps.append("4. Сгенерируйте WB названия коробок.")

    if missing_steps:
        response_message = "Для продолжения выполните следующие шаги:\n" + "\n".join(missing_steps)
        await message.answer(response_message)
    else:
        # Получаем данные из базы данных
        box_capacity_df, items_to_ship_df, _ = db.get_data_from_db(user_id)

        # Выполняем расчет количества коробок
        box_count_result = main.count_boxes(box_capacity_df, items_to_ship_df)

        if isinstance(box_count_result, str):
            # Если функция вернула строку, значит произошла ошибка
            await message.answer(box_count_result)
        else:
            db.update_table('users', {'amount_of_boxes': box_count_result}, {'user_id': user_id})
            await message.answer(f"Всего коробок: {box_count_result}")


@dp.message_handler(lambda message: message.text == markups.GENERATE_REPORT_TEXT)
async def handle_generate_report(message: types.Message):
    user_id = message.from_user.id
    await message.delete()
    user_data = db.get_row_as_dict({'user_id': user_id})
    new_limit = user_data['usage_limit']
    # Проверка на авторизацию и оставшиеся попытки
    if user_data['is_authorized'] or new_limit > 0:
        missing_steps = []
        if not user_data.get('box_capacity_id'):
            missing_steps.append(
                " * Загрузите таблицу с вместимостью товаров в коробку (2 столбца: 'Баркод' и 'Кратность').")
        if not user_data.get('items_to_ship_id'):
            missing_steps.append(" ** Загрузите таблицу с количеством товаров (2 столбца: 'Баркод' и 'Количество').")
        if user_data.get('amount_of_boxes', 0) <= 0:
            missing_steps.append(" *** Выполните расчет количества коробок.")
        if not user_data.get('boxes_id'):
            missing_steps.append(" **** Сгенерируйте WB названия коробок.")

        if missing_steps:
            response_message = "Для продолжения выполните следующие шаги:\n" + "\n".join(missing_steps)
            await message.answer(response_message)
        else:
            # Получаем данные из базы данных
            box_capacity_df, items_to_ship_df, boxes_id_df = db.get_data_from_db(user_id)

            # Выполняем генерацию отчета
            result = main.generate_report(box_capacity_df, items_to_ship_df, boxes_id_df)

            if isinstance(result, str):
                # Если функция вернула строку, значит произошла ошибка
                await message.answer(result)
            else:
                if not user_data['is_authorized']:
                    new_limit = db.decrease_usage_limit(user_id)
                db.create_generation(user_id)

                result_wb, result_storage = result

                # Отправка файла для Wildberries
                await bot.send_document(user_id,
                                        InputFile(result_wb[0], filename=result_wb[1]),
                                        caption=msg.success_message_for_wildberries(new_limit))

                # Отправка инструкции для склада
                await bot.send_document(user_id, InputFile(result_storage[0], filename=result_storage[1]),
                                        caption=msg.instruction_for_warehouse_message(new_limit))
    else:
        # Если пользователь не авторизован и у него нет попыток
        await message.answer(msg.exceeded_limit_message(user_data))


@dp.message_handler(lambda message: message.text == markups.RESET_TEXT)
async def reset_command(message: types.Message):
    user_id = message.from_user.id
    db.reset_file_ids(user_id)

    await message.delete()
    await message.answer(msg.reset_success_message(message.from_user.first_name), reply_markup=markups.main_keyboard)


@dp.message_handler(content_types=['text'])
async def handle_text(message: types.Message):
    user_id = message.from_user.id
    user_data = db.get_row_as_dict({'user_id': user_id})

    # Проверка на пересланное сообщение и статус администратора
    if 'forward_from' in message and user_data["username"] in admins:
        forwarded_user_id = message.forward_from.id
        forwarded_user_data = db.get_row_as_dict({"user_id": forwarded_user_id}, "users")
        if forwarded_user_data:
            info = f"UserID: {forwarded_user_data['user_id']}\nUsername: @{forwarded_user_data['username']}\n" \
                   f"Attempts: {forwarded_user_data['usage_limit']}\n" \
                   f"Registration Date: {forwarded_user_data['registration_date']}\n" \
                   f"Authorization Status: {forwarded_user_data['is_authorized']}"
            keyboard = InlineKeyboardMarkup().add(
                InlineKeyboardButton("Выдать пароль", callback_data=f"give_password:{forwarded_user_data['user_id']}"),
                InlineKeyboardButton("Сгенерировать новый пароль",
                                     callback_data=f"generate_password:{forwarded_user_data['user_id']}")
            )
            await message.answer(info, reply_markup=keyboard)
        else:
            await message.answer("Пересланный пользователь не найден.")
        return

    # Проверка пароля для обычных или пересланных сообщений от неадминов
    input_text = message.text
    if user_data and input_text == user_data['password']:
        # Пароль верный, производим авторизацию
        db.toggle_authorization(user_id, authorize=True)
        await message.answer("Вы успешно авторизованы.")
    else:
        # Пароль неверный
        await message.answer("Неверный пароль. Попробуйте снова.")


# Обработчики для callback данных кнопок
@dp.callback_query_handler(lambda call: call.data.startswith("give_password:"))
async def handle_give_password(call: types.CallbackQuery):
    user_id = call.data.split(':')[1]
    user_data = db.get_row_as_dict({"user_id": user_id})
    password = user_data["password"]
    await bot.send_message(chat_id=call.from_user.id, text=password)
    await call.answer()


@dp.callback_query_handler(lambda call: call.data.startswith("generate_password:"))
async def handle_generate_password(call: types.CallbackQuery):
    user_id = int(call.data.split(':')[1])  # Получаем user_id из callback данных
    user_data = db.update_user(user_id)
    password = user_data["password"]
    await bot.send_message(chat_id=call.from_user.id, text=password)
    await call.answer()


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
