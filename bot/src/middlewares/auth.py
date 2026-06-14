import logging
from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.config import SUPPORT_USER, ADMIN_IDS
from src.database import queries as db
from src.utils.cache import cache_get, cache_set

logger = logging.getLogger(__name__)


def require_access(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            return

        uid = user.id
        uname = user.username or ""
        name = user.full_name or ""

        db.upsert_user(uid, uname, name)
        db.ensure_user_platform(uid)

        if uid in ADMIN_IDS:
            db.increment_requests(uid)
            return await func(update, context, *args, **kwargs)

        cache_key = f"access_{uid}"
        cached = cache_get(cache_key)
        if cached is None:
            allowed = db.is_allowed(uid)
            banned_flag = db.is_banned(uid)
            cache_set(cache_key, (allowed, banned_flag))
        else:
            allowed, banned_flag = cached

        if banned_flag:
            await _reply(update, f"🚫 *أنت محظور*\n\nللتواصل مع الدعم: {SUPPORT_USER}")
            return

        if not allowed:
            await _reply(update, f"🚫 *غير مسموح*\n\nأنت غير مسجل في النظام.\nيرجى التواصل مع المدير: {SUPPORT_USER}")
            return

        db.increment_requests(uid)
        return await func(update, context, *args, **kwargs)

    return wrapper


async def _reply(update: Update, text: str):
    if update.callback_query:
        try:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(text, parse_mode="Markdown")
        except Exception:
            pass
    elif update.message:
        await update.message.reply_text(text, parse_mode="Markdown")
