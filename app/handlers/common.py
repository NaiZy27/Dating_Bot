"""/start, создание анкеты и отмена — работают из любого состояния."""
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app import db
from app import keyboards as kb
from app.handlers.search import show_candidate
from app.states import Registration, SearchState
from app.views import send_main_menu

router = Router()


@router.message(CommandStart())
async def command_start(message: Message, state: FSMContext):
    await state.clear()
    if await db.profile_exists(message.from_user.id):
        # username мог смениться — без актуального не получится связать людей при мэтче
        await db.update_username(message.from_user.id, message.from_user.username)
        await send_main_menu(message)
    else:
        await message.answer("Привет в NewDating! ❤️", reply_markup=kb.get_start_menu())

@router.message(F.text == "Создать анкету 📝")
async def start_reg(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Registration.name)
    await message.answer("Как тебя зовут?", reply_markup=kb.get_cancel_kb())

@router.message(F.text == "Отмена ❌")
async def cancel_handler(message: Message, state: FSMContext):
    # Отмена сообщения/жалобы возвращает к той же анкете, а не в главное меню
    if await state.get_state() in (SearchState.writing_message.state, SearchState.choosing_report.state):
        await state.set_state(SearchState.browsing)
        return await show_candidate(message, state)
    await state.clear()
    if await db.profile_exists(message.from_user.id):
        await send_main_menu(message)
    else:
        await message.answer("Отменено.", reply_markup=kb.get_start_menu())
