import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler

from src.config import ADMIN_IDS
from src.database import queries as db
from src.middlewares.auth import require_access

logger = logging.getLogger(__name__)


def _build_main_keyboard(uid: int) -> InlineKeyboardMarkup:
    platform = db.get_user_platform(uid)
    platform_emoji = "🤖" if platform == "android" else "🍎"

    kb = []
    if uid in ADMIN_IDS:
        kb.append([InlineKeyboardButton("👑 لوحة التحكم", callback_data="admin_panel")])
    kb.append([InlineKeyboardButton("📱 AppsFlyer", callback_data="af_menu")])
    kb.append([InlineKeyboardButton("📊 Adjust", callback_data="adj_menu")])
    kb.append([InlineKeyboardButton("🌟 Singular", callback_data="singular_menu")])
    kb.append([InlineKeyboardButton("🌾 مزرعة الجمبرة", callback_data="jumper_farm")])
    kb.append([InlineKeyboardButton("🔧 إعدادات البروكسي", callback_data="proxy_settings")])
    kb.append([InlineKeyboardButton(f"{platform_emoji} نظام التشغيل", callback_data="select_platform")])
    return InlineKeyboardMarkup(kb)


@require_access
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    platform = db.get_user_platform(uid)
    platform_name = "Android 🤖" if platform == "android" else "iOS 🍎"

    text = (
        "🔥 *AK Jumper Bot* 🔥\n\n"
        "✨ *اختر الخدمة* ✨\n\n"
        "┃ 📱 AppsFlyer\n"
        "┃ 📊 Adjust\n"
        "┃ 🌟 Singular\n"
        "┃ 🌾 مزرعة الجمبرة\n"
        "┃ 🔧 بروكسي\n\n"
        f"📱 النظام الحالي: {platform_name}"
    )

    kb = _build_main_keyboard(uid)

    if update.message:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
    elif update.callback_query:
        query = update.callback_query
        await query.answer()
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await query.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


@require_access
async def clean_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.set_user_platform(uid, "android")
    await update.message.reply_text(
        "✅ *تم التنظيف الشامل*\n\nالمنصة: Android\nاستخدم /start للبدء.",
        parse_mode="Markdown",
    )


def get_handlers():
    return [
        CommandHandler("start", start),
        CommandHandler("clean", clean_start),
    ]
