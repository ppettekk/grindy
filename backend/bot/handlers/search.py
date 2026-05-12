from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from ..keyboards.onboarding import kb_open_webapp

router = Router(name="search")


@router.message(Command("search"))
async def cmd_search(message: Message) -> None:
    await message.answer(
        "Открываю Grindy ↓\nВся лента, фильтры и сохранёнки внутри.",
        reply_markup=kb_open_webapp(),
    )
