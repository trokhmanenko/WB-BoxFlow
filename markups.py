from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

GENERATE_REPORT_TEXT = "📈\u00A0Разложить\u00A0товары\u00A0по\u00A0коробкам"
COUNT_BOXES_TEXT = "📦\u00A0Посчитать коробки"
RESET_TEXT = "♻\u00A0Сброс"

btn1 = KeyboardButton(GENERATE_REPORT_TEXT)
btn2 = KeyboardButton(COUNT_BOXES_TEXT)
btn3 = KeyboardButton(RESET_TEXT)  # создаем кнопку "Сброс"
main_keyboard = ReplyKeyboardMarkup(resize_keyboard=True).row(btn1).row(btn2).row(btn3)
