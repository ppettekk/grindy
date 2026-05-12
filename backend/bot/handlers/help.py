from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router(name="help")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "<b>Команды</b>\n"
        "/start — настроить заново\n"
        "/search — открыть Grindy WebApp\n"
        "/settings — фильтры и пуши\n\n"
        "Если нашёл странную вакансию — жми «Пожаловаться» в карточке. "
        "Спам и MLM мы фильтруем через AI, но иногда что-то проскакивает."
    )
