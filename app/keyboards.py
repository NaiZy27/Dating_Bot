from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

REPORT_REASONS = ["🔞 Непристойное", "💰 Спам / реклама", "🎭 Фейк", "🤬 Оскорбления", "🤷 Другое"]
PREMIUM_PRICE = 199


def get_start_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="Создать анкету 📝"))
    return builder.as_markup(resize_keyboard=True)

def get_main_menu(likes_count: int = 0) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    if likes_count:
        builder.row(KeyboardButton(text=f"Кто меня лайкнул ({likes_count}) ❤️"))
    builder.row(*[KeyboardButton(text=str(i)) for i in range(1, 5)])
    return builder.as_markup(resize_keyboard=True)

def get_inactive_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="Включить анкету ✅"))
    return builder.as_markup(resize_keyboard=True)

def get_edit_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    for i in range(1, 8):
        builder.add(KeyboardButton(text=str(i)))
    builder.add(KeyboardButton(text="Назад ⬅️"))
    builder.adjust(4, 3, 1)
    return builder.as_markup(resize_keyboard=True)

def get_cancel_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="Отмена ❌"))
    return builder.as_markup(resize_keyboard=True)

def get_gender_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="Мужчина"), KeyboardButton(text="Женщина"))
    builder.add(KeyboardButton(text="Отмена ❌"))
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)

def target_gender_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="Мужчины"), KeyboardButton(text="Женщины"))
    builder.add(KeyboardButton(text="Отмена ❌"))
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)

def get_text_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="Пропустить ⏭️"))
    builder.add(KeyboardButton(text="Отмена ❌"))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

def get_search_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="❤️"))
    builder.add(KeyboardButton(text="💌"))
    builder.add(KeyboardButton(text="👎"))
    builder.add(KeyboardButton(text="⚠️ Жалоба"))
    builder.add(KeyboardButton(text="Вернуться в меню ⬅️"))
    builder.adjust(3, 2)
    return builder.as_markup(resize_keyboard=True)

def get_report_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    for reason in REPORT_REASONS:
        builder.add(KeyboardButton(text=reason))
    builder.add(KeyboardButton(text="Отмена ❌"))
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup(resize_keyboard=True)

def get_view_likes_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Посмотреть 👀", callback_data="show_likes")]
    ])

def get_premium_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Оплатить {PREMIUM_PRICE} ₽ (тест) 💳", callback_data="buy_premium")]
    ])
