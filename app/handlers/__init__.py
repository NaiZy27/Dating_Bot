from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from app.handlers import common, registration, menu, premium, search

# Отдельный роутер, чтобы подключиться последним и ловить только то, что не поймали остальные
fallback = Router()

@fallback.message()
async def cleanup(message: Message):
    try: await message.delete()
    except TelegramBadRequest: pass

# Порядок важен: общие команды (/start, «Отмена») раньше заглушек регистрации, cleanup — в самом конце
routers = [common.router, registration.router, menu.router, premium.router, search.router, fallback]
