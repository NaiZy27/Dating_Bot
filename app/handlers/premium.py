"""Премиум: больше лайков в день. Оплата ненастоящая — проект учебный."""
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery

from app import db
from app import keyboards as kb
from app.models import DAILY_LIKES_LIMIT, PREMIUM_DAILY_LIKES_LIMIT, HOURLY_LIKES_LIMIT
from app.views import send_main_menu

router = Router()

PREMIUM_PERKS = (
    f"• {PREMIUM_DAILY_LIKES_LIMIT} лайков в день вместо {DAILY_LIKES_LIMIT}\n"
    f"• без лимита {HOURLY_LIKES_LIMIT} лайков в час\n"
    "• можно написать любому из ленты — имя в анкете станет ссылкой на Telegram"
)


@router.message(F.text == "4", StateFilter(None))
async def premium_info(message: Message):
    profile = await db.get_profile(message.from_user.id)
    if not profile:
        return await send_main_menu(message)
    if profile.premium:
        return await message.answer(f"⭐ У тебя уже премиум\n\n{PREMIUM_PERKS}")
    await message.answer(f"⭐ <b>Премиум</b>\n\n{PREMIUM_PERKS}\n\nЦена: {kb.PREMIUM_PRICE} ₽", reply_markup=kb.get_premium_inline())

@router.callback_query(F.data == "buy_premium")
async def buy_premium(callback: CallbackQuery):
    # shortcut: mock-оплата, деньги не списываются; для настоящей — bot.send_invoice + обработка pre_checkout_query
    # Без проверки save_profile создал бы пустую анкету для того, у кого её нет
    profile = await db.get_profile(callback.from_user.id)
    if not profile:
        return await callback.answer("Сначала создай анкету 📝", show_alert=True)
    # Повторное нажатие: текст тот же, и edit_text упал бы с «message is not modified»
    if profile.premium:
        return await callback.answer("Премиум уже включён ⭐")
    await db.save_profile({"id": callback.from_user.id, "premium": True})
    await callback.answer("Оплата прошла ✅")
    await callback.message.edit_text(f"⭐ Премиум включён\n\n{PREMIUM_PERKS}")
