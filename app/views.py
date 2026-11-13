"""Экраны, которые показываются из разных хендлеров: главное меню и своя анкета."""
from aiogram.types import Message

from app import db
from app import keyboards as kb


async def send_main_menu(message: Message):
    user_id = message.chat.id
    profile = await db.get_profile(user_id)
    if not profile:
        return await message.answer("Сначала создай анкету 📝", reply_markup=kb.get_start_menu())
    if not profile.active:
        return await message.answer(
            "Твоя анкета выключена 💤\nПока она выключена, тебя никто не видит в поиске.",
            reply_markup=kb.get_inactive_menu()
        )
    incoming = await db.get_incoming_likes(user_id)
    text = "<b>Главное меню:</b>\n\n1. Смотреть анкеты 🔍\n2. Моя анкета 👤\n3. Выключить анкету 💤\n4. Премиум ⭐"
    await message.answer(text, reply_markup=kb.get_main_menu(len(incoming)))

async def send_edit_menu(message: Message):
    text = "<b>Настройка профиля</b> ⚙️\n\nЧто изменить?\n1. Имя\n2. Возраст\n3. Город\n4. Текст\n5. Фото\n6. Пол\n7. Кого ищу"
    await message.answer(text, reply_markup=kb.get_edit_menu())

async def show_my_profile(message: Message, is_after_edit: bool = False):
    profile = await db.get_profile(message.chat.id)
    if profile:
        await message.answer_photo(photo=profile.media[0], caption=f"<b>Ваша анкета:</b>\n\n{profile.preview_text()}")
        if is_after_edit:
            await send_main_menu(message)
        else:
            await send_edit_menu(message)
    else:
        await message.answer("Профиль не найден. Напиши /start")
