"""Просмотр анкет, лайки, мэтчи, жалобы и входящие лайки."""
import html
from typing import Optional

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from app import db
from app import keyboards as kb
from app.config import config
from app.loader import redis
from app.models import Profile, Gender
from app.states import Registration, EditProfile, SearchState
from app.utils import contact_link, safe_send, reaction_lock
from app.views import send_main_menu

router = Router()

# Уведомление о новых лайках шлём не чаще одного раза за этот период (сек)
LIKE_NOTIFY_COOLDOWN = 10 * 60

# --- Логика просмотра анкет ---

async def get_current_candidate_id(state: FSMContext) -> Optional[int]:
    data = await state.get_data()
    queue, idx = data.get("queue", []), data.get("current_idx", 0)
    return queue[idx] if idx < len(queue) else None

async def show_candidate(message: Message, state: FSMContext):
    data = await state.get_data()
    queue, idx = data.get("queue", []), data.get("current_idx", 0)
    viewing_likes = data.get("is_viewing_likes", False)

    # Пропускаем анкеты, которые успели выключить, пока они лежали в очереди
    candidate = None
    while idx < len(queue) and candidate is None:
        profile = await db.get_profile(queue[idx])
        if profile and profile.active:
            candidate = profile
        else:
            idx += 1

    if candidate is None:
        return await finish_queue(message, state, viewing_likes)

    await state.update_data(current_idx=idx)
    viewer = await db.get_profile(message.chat.id)
    # Премиум может написать любому из ленты: имя в анкете — ссылка на Telegram
    caption = candidate.preview_text(linked=viewer.premium)
    if viewing_likes:
        caption = f"🤩 <b>Этому человеку понравилась твоя анкета</b>\n\n{caption}"
    await message.answer_photo(candidate.media[0], caption=caption, reply_markup=kb.get_search_kb())
    if viewing_likes:
        # Отдельным сообщением: анкета + сообщение вместе не влезают в лимит подписи Telegram (1024)
        like_message = await db.get_like_message(candidate.id, message.chat.id)
        if like_message:
            await message.answer(f"💌 <b>Сообщение для тебя:</b>\n{html.escape(like_message)}")

async def finish_queue(message: Message, state: FSMContext, viewing_likes: bool):
    if viewing_likes:
        await message.answer("Это были все, кому ты понравился ✨")
    else:
        user = await db.get_profile(message.chat.id)
        new = await db.get_match_candidates(user.id, user.gender, user.target_gender, user.age)
        if new:
            await state.update_data(queue=[c.id for c in new], current_idx=0)
            return await show_candidate(message, state)
        await message.answer("Анкеты кончились, загляни попозже 💤")
    await state.clear()
    await send_main_menu(message)

async def show_next_candidate(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(current_idx=data.get("current_idx", 0) + 1)
    await show_candidate(message, state)

async def leave_search(message: Message, state: FSMContext):
    await state.clear()
    await send_main_menu(message)

# --- Лайки, мэтчи и уведомления ---

async def send_like(message: Message, target_id: int, text: Optional[str] = None) -> bool:
    """Ставит лайк (опционально с сообщением). Возвращает False, если упёрлись в дневной лимит."""
    me = await db.get_profile(message.from_user.id)
    is_mutual = await db.has_liked(target_id, me.id)
    # Ответный лайк лимит не тратит
    if not is_mutual and (error := await me.use_like(redis)):
        await message.answer(error, reply_markup=kb.get_search_kb())
        return False
    await db.add_reaction(me.id, target_id, True, text)
    if is_mutual:
        await notify_match(message, me, target_id, text)
    else:
        if text:
            await message.answer("Лайк с сообщением отправлен 💌")
        await notify_new_like(target_id)
    return True

async def notify_match(message: Message, me: Profile, target_id: int, text: Optional[str]):
    target = await db.get_profile(target_id)
    if not target:
        return
    await message.answer(f"🎉 Есть взаимная симпатия с {html.escape(target.name)}!\nНачинай общаться 👉 {contact_link(target)}")
    note = f"🎉 Есть взаимная симпатия с {html.escape(me.name)}!\nНачинай общаться 👉 {contact_link(me)}"
    if text:
        note += f"\n\n💌 <b>Сообщение для тебя:</b>\n{html.escape(text)}"
    await safe_send(target.id, note, photo=me.media[0])

async def notify_new_like(target_id: int):
    # 0 — лайк не покажут (человек уже ответил лайкнувшему или тот скрыт жалобами), уведомлять не о чем
    count = len(await db.get_incoming_likes(target_id))
    if not count:
        return
    # nx=True: ключ ставится, только если его ещё нет — так не заваливаем человека уведомлениями
    if not await redis.set(f"like_notify:{target_id}", 1, ex=LIKE_NOTIFY_COOLDOWN, nx=True):
        return
    target = await db.get_profile(target_id)
    if not target:
        return
    liked = "понравилась" if target.gender == Gender.FEMALE else "понравился"
    await safe_send(
        target_id,
        f"❤️ Ты кому-то {liked}! Непросмотренных лайков: {count}",
        reply_markup=kb.get_view_likes_inline()
    )

async def notify_admin_about_report(from_id: int, target: Profile, reason: str, reports_count: int):
    if not config.admin_id:
        return
    caption = (
        f"⚠️ <b>Жалоба:</b> {html.escape(reason)}\n"
        f"На: <code>{target.id}</code> {contact_link(target)}\n"
        f"От: <code>{from_id}</code>\n"
        f"Жалоб от разных людей: {reports_count}\n\n"
        f"{target.preview_text()}"
    )
    await safe_send(config.admin_id, caption, photo=target.media[0])

# --- Хендлеры просмотра ---

@router.message(SearchState.browsing, F.text.in_(["❤️", "👎"]))
async def handle_react(message: Message, state: FSMContext):
    async with reaction_lock(message.from_user.id) as acquired:
        if not acquired:
            return
        target_id = await get_current_candidate_id(state)
        if target_id is None:
            return await leave_search(message, state)
        if message.text == "❤️":
            if not await send_like(message, target_id):
                return
        else:
            await db.add_reaction(message.from_user.id, target_id, False)
        await show_next_candidate(message, state)

@router.message(SearchState.browsing, F.text == "💌")
async def ask_like_message(message: Message, state: FSMContext):
    await state.set_state(SearchState.writing_message)
    await message.answer("Напиши сообщение для этого человека — оно придёт вместе с лайком 💌", reply_markup=kb.get_cancel_kb())

@router.message(SearchState.writing_message, F.text)
async def send_like_with_message(message: Message, state: FSMContext):
    if len(message.text) > 400:
        return await message.answer("⚠️ Сообщение не может быть длиннее 400 символов")
    async with reaction_lock(message.from_user.id) as acquired:
        if not acquired:
            return
        target_id = await get_current_candidate_id(state)
        await state.set_state(SearchState.browsing)
        if target_id is None:
            return await leave_search(message, state)
        if not await send_like(message, target_id, message.text):
            return
        await show_next_candidate(message, state)

@router.message(SearchState.writing_message)
async def like_message_fallback(message: Message):
    await message.answer("Отправь сообщение текстом ✍️")

@router.message(SearchState.browsing, F.text == "⚠️ Жалоба")
async def ask_report_reason(message: Message, state: FSMContext):
    await state.set_state(SearchState.choosing_report)
    await message.answer("Что не так с анкетой?", reply_markup=kb.get_report_kb())

@router.message(SearchState.choosing_report, F.text.in_(kb.REPORT_REASONS))
async def handle_report(message: Message, state: FSMContext):
    async with reaction_lock(message.from_user.id) as acquired:
        if not acquired:
            return
        target_id = await get_current_candidate_id(state)
        await state.set_state(SearchState.browsing)
        if target_id is None:
            return await leave_search(message, state)
        reports_count = await db.add_report(message.from_user.id, target_id, message.text)
        # Жалоба работает и как дизлайк: эта анкета пользователю больше не попадётся
        await db.add_reaction(message.from_user.id, target_id, False)
        target = await db.get_profile(target_id)
        if target:
            await notify_admin_about_report(message.from_user.id, target, message.text, reports_count)
        await message.answer("Спасибо, жалоба отправлена. Больше эту анкету не покажем 🙏")
        await show_next_candidate(message, state)

@router.message(SearchState.choosing_report)
async def report_fallback(message: Message):
    await message.answer("Выбери причину на клавиатуре 👇")

@router.message(SearchState.browsing, F.text == "Вернуться в меню ⬅️")
async def exit_search(message: Message, state: FSMContext):
    await leave_search(message, state)

@router.message(SearchState.browsing)
async def browsing_fallback(message: Message):
    await message.answer("Используй кнопки внизу 👇", reply_markup=kb.get_search_kb())

# --- Входящие лайки ---

async def start_viewing_likes(message: Message, state: FSMContext, incoming: list):
    await state.set_state(SearchState.browsing)
    await state.update_data(queue=[c.id for c in incoming], current_idx=0, is_viewing_likes=True)
    await show_candidate(message, state)

@router.message(F.text.startswith("Кто меня лайкнул"), StateFilter(None))
async def view_incoming(message: Message, state: FSMContext):
    incoming = await db.get_incoming_likes(message.from_user.id)
    if not incoming:
        await message.answer("Новых лайков пока нет.")
        return await send_main_menu(message)
    await start_viewing_likes(message, state, incoming)

@router.callback_query(F.data == "show_likes")
async def cb_show_likes(callback: CallbackQuery, state: FSMContext):
    current = await state.get_state()
    if current in Registration or current in EditProfile:
        return await callback.answer("Сначала закончи с анкетой ✍️", show_alert=True)
    profile = await db.get_profile(callback.from_user.id)
    if not profile or not profile.active:
        return await callback.answer("Сначала включи анкету ✅", show_alert=True)
    incoming = await db.get_incoming_likes(callback.from_user.id)
    if not incoming:
        return await callback.answer("Новых лайков пока нет", show_alert=True)
    await callback.answer()
    await start_viewing_likes(callback.message, state, incoming)
