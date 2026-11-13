import html
import logging
from contextlib import asynccontextmanager
from typing import Optional

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from app import db
from app.loader import bot, redis
from app.models import Profile

logger = logging.getLogger(__name__)

# В хелперах id пользователя берётся из message.chat.id: в личке он совпадает с id юзера
# и работает в том числе для callback.message, где from_user — это сам бот.

def contact_link(profile: Profile) -> str:
    if profile.username:
        return f"@{profile.username}"
    return f'<a href="{profile.link}">{html.escape(profile.name or "Профиль")}</a>'

async def safe_send(chat_id: int, text: str, photo: Optional[str] = None, **kwargs) -> bool:
    """Отправка другому пользователю, который мог заблокировать бота."""
    try:
        if photo:
            await bot.send_photo(chat_id, photo, caption=text, **kwargs)
        else:
            await bot.send_message(chat_id, text, **kwargs)
        return True
    except TelegramForbiddenError:
        # Бот заблокирован — прячем анкету, чтобы её не лайкали впустую
        await db.toggle_active(chat_id, False)
    except TelegramBadRequest as e:
        logger.warning("Не удалось отправить сообщение %s: %s", chat_id, e)
    return False

@asynccontextmanager
async def reaction_lock(user_id: int):
    """Защита от двойного нажатия: пока обрабатывается реакция, повторные игнорируем."""
    key = f"react_lock:{user_id}"
    acquired = await redis.set(key, 1, ex=10, nx=True)
    try:
        yield bool(acquired)
    finally:
        if acquired:
            await redis.delete(key)
