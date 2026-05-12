from aiogram import Dispatcher

from .help import router as help_router
from .moderation import router as moderation_router
from .search import router as search_router
from .settings import router as settings_router
from .start import router as start_router
from .subscription import router as subscription_router


def setup_handlers(dp: Dispatcher) -> None:
    # subscription_router goes first: its recheck-callback must run before
    # other handlers, and middleware whitelists it.
    dp.include_router(subscription_router)
    # moderation - callbacks like mod:restore:<id>, mod:ban:<id> from admin notifications.
    dp.include_router(moderation_router)
    dp.include_router(start_router)
    dp.include_router(settings_router)
    dp.include_router(help_router)
    dp.include_router(search_router)
