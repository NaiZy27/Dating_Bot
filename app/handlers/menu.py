"""Главное меню и меню редактирования анкеты."""
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app import db
from app import keyboards as kb
from app.handlers.search import show_candidate
from app.states import Registration, EditProfile, SearchState
from app.views import send_main_menu, send_edit_menu, show_my_profile

router = Router()


@router.message(F.text == "1", StateFilter(None))
async def menu_watch(message: Message, state: FSMContext):
    user = await db.get_profile(message.from_user.id)
    if not user or not user.active:
        return await send_main_menu(message)
    # Пустая очередь — show_candidate сам подгрузит анкеты из БД
    await state.update_data(queue=[], current_idx=0, is_viewing_likes=False)
    await state.set_state(SearchState.browsing)
    await show_candidate(message, state)

@router.message(F.text == "2", StateFilter(None))
async def menu_2(message: Message, state: FSMContext):
    if not await db.profile_exists(message.from_user.id):
        return await send_main_menu(message)
    await state.set_state(EditProfile.choosing_field)
    await show_my_profile(message, is_after_edit=False)

@router.message(F.text == "3", StateFilter(None))
async def menu_3(message: Message):
    if await db.profile_exists(message.from_user.id):
        await db.toggle_active(message.from_user.id, False)
    await send_main_menu(message)

@router.message(F.text == "Включить анкету ✅", StateFilter(None))
async def activate_profile(message: Message):
    if await db.profile_exists(message.from_user.id):
        await db.toggle_active(message.from_user.id, True)
        await message.answer("Анкета снова включена ✅")
    await send_main_menu(message)

@router.message(EditProfile.choosing_field, F.text.in_(["1", "2", "3", "4", "5", "6", "7"]))
async def edit_field(message: Message, state: FSMContext):
    fields = {
        "1": (Registration.name, "Введите новое имя:", kb.get_cancel_kb),
        "2": (Registration.age, "Введите новый возраст:", kb.get_cancel_kb),
        "3": (Registration.city, "Введите новый город:", kb.get_cancel_kb),
        "4": (Registration.text, "Введите новый текст:", kb.get_text_kb),
        "5": (Registration.media, "Пришлите новое фото 📸", kb.get_cancel_kb),
        "6": (Registration.gender, "Твой пол:", kb.get_gender_keyboard),
        "7": (Registration.target_gender, "Кто тебе интересен?", kb.target_gender_keyboard),
    }
    st, prompt, keyboard = fields[message.text]
    await state.update_data(is_editing=True)
    await state.set_state(st)
    await message.answer(prompt, reply_markup=keyboard())

@router.message(EditProfile.choosing_field, F.text.in_(["0", "Назад ⬅️"]))
async def edit_back(message: Message, state: FSMContext):
    await state.clear()
    await send_main_menu(message)

@router.message(EditProfile.choosing_field)
async def edit_fallback(message: Message):
    await send_edit_menu(message)
