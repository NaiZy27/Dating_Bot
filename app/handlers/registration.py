"""Заполнение анкеты по шагам. Те же шаги используются при редактировании (флаг is_editing)."""
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from pydantic import ValidationError

from app import db
from app import keyboards as kb
from app.models import Profile
from app.states import Registration
from app.views import show_my_profile

router = Router()


async def save_edited_field(message: Message, state: FSMContext, **fields):
    await db.save_profile({"id": message.from_user.id, **fields})
    await state.clear()
    await show_my_profile(message, is_after_edit=True)

async def next_step(message: Message, state: FSMContext, field: str, value, next_state, prompt: str, keyboard):
    """При редактировании сохраняем одно поле, при регистрации запоминаем его и задаём следующий вопрос."""
    if (await state.get_data()).get("is_editing"):
        return await save_edited_field(message, state, **{field: value})
    await state.update_data(**{field: value})
    await state.set_state(next_state)
    await message.answer(prompt, reply_markup=keyboard())

@router.message(Registration.name, F.text)
async def reg_name(message: Message, state: FSMContext):
    try:
        name = Profile(name=message.text).name
    except ValidationError as e:
        return await message.answer(Profile.format_error(e))
    await next_step(message, state, "name", name, Registration.age, "Сколько тебе лет?", kb.get_cancel_kb)

@router.message(Registration.age, F.text)
async def reg_age(message: Message, state: FSMContext):
    # isdecimal, а не isdigit: "²" проходит isdigit, но роняет int()
    if not message.text.isdecimal(): return await message.answer("Введите число!")
    try:
        age = Profile(age=int(message.text)).age
    except ValidationError as e:
        return await message.answer(Profile.format_error(e))
    await next_step(message, state, "age", age, Registration.city, "Из какого ты города?", kb.get_cancel_kb)

@router.message(Registration.city, F.text)
async def reg_city(message: Message, state: FSMContext):
    try:
        city = Profile(city=message.text).city
    except ValidationError as e:
        return await message.answer(Profile.format_error(e))
    await next_step(message, state, "city", city, Registration.gender, "Твой пол:", kb.get_gender_keyboard)

@router.message(Registration.gender, F.text.in_(["Мужчина", "Женщина"]))
async def reg_gender(message: Message, state: FSMContext):
    await next_step(message, state, "gender", message.text, Registration.target_gender, "Кто тебе интересен?", kb.target_gender_keyboard)

@router.message(Registration.target_gender, F.text.in_(["Мужчины", "Женщины"]))
async def reg_target(message: Message, state: FSMContext):
    await next_step(message, state, "target_gender", message.text, Registration.text, "О себе:", kb.get_text_kb)

@router.message(Registration.text, F.text)
async def reg_text(message: Message, state: FSMContext):
    val = None if message.text == "Пропустить ⏭️" else message.text
    try:
        if val: Profile(text=val)
    except ValidationError as e:
        return await message.answer(Profile.format_error(e))
    await next_step(message, state, "text", val, Registration.media, "Пришли фото 📸", kb.get_cancel_kb)

@router.message(Registration.media, F.photo)
async def reg_media(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    if data.get("is_editing"):
        return await save_edited_field(message, state, media=[photo_id])
    data.pop("is_editing", None)
    data.update({"id": message.from_user.id, "username": message.from_user.username, "media": [photo_id], "active": True})
    try:
        user_profile = Profile(**data)
    except ValidationError as e:
        return await message.answer(Profile.format_error(e))
    # exclude_unset: не затираем поля, которых нет в анкете (например, купленный премиум)
    await db.save_profile(user_profile.model_dump(exclude_unset=True))
    await state.clear()
    await show_my_profile(message, is_after_edit=True)

# Неподходящий ввод на шагах регистрации: подсказываем, а не молча удаляем
@router.message(Registration.gender)
@router.message(Registration.target_gender)
async def reg_choice_fallback(message: Message):
    await message.answer("Выбери вариант на клавиатуре 👇")

@router.message(Registration.media)
async def reg_media_fallback(message: Message):
    await message.answer("Пришли именно фото 📸")

@router.message(StateFilter(Registration))
async def reg_fallback(message: Message):
    await message.answer("Отправь ответ текстом ✍️")
