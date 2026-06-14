import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
)

from src.database import queries as db
from src.middlewares.auth import require_access
from src.services.singular import send_singular

logger = logging.getLogger(__name__)

SNG_AIFA, SNG_IDFA, SNG_IDFV, SNG_UID, SNG_UID_IOS = range(300, 305)


def _result_text(status: int, resp: str) -> str:
    if status == 200:
        return "✅ *تم الإرسال بنجاح!*"
    return f"❌ *فشل الإرسال*\nالكود: `{status}`\n`{resp[:200]}`"


def _back_kb(data: str = "singular_menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data=data)]])


@require_access
async def singular_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    games = db.get_all_games_singular()
    if not games:
        await query.edit_message_text("❌ *لا توجد ألعاب Singular*", parse_mode="Markdown", reply_markup=_back_kb("main_menu"))
        return ConversationHandler.END

    kb = [[InlineKeyboardButton(f"{g['emoji']} {g['display_name']}", callback_data=f"sg_game_{g['id']}")] for g in games]
    kb.append([InlineKeyboardButton("🔍 بحث", callback_data="sg_search")])
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
    await query.edit_message_text("🌟 *اختر اللعبة - Singular*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


@require_access
async def singular_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game_id = int(query.data.replace("sg_game_", ""))
    game = db.get_game_singular_by_id(game_id)
    if not game:
        await query.edit_message_text("❌ خطأ: اللعبة غير موجودة", parse_mode="Markdown")
        return ConversationHandler.END

    context.user_data["sg_game_id"] = game_id
    context.user_data["sg_game"] = dict(game)
    uid = update.effective_user.id
    platform = db.get_user_platform(uid)

    if platform == "ios":
        await query.edit_message_text(
            "🍎 *iOS - Singular*\n\n📱 *أدخل IDFA:*\nمثال: `12345678-1234-1234-1234-123456789012`",
            parse_mode="Markdown",
        )
        return SNG_IDFA
    else:
        await query.edit_message_text(
            "🤖 *Android - Singular*\n\n📱 *أدخل AIFA (GAID):*\nمثال: `8de8604d-1318-4fd0-907c-402ea9de2529`",
            parse_mode="Markdown",
        )
        return SNG_AIFA


@require_access
async def singular_aifa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sg_aifa"] = update.message.text.strip()
    await update.message.reply_text(
        "🆔 *أدخل Custom User ID:*\nمثال: `your_user_id`",
        parse_mode="Markdown",
    )
    return SNG_UID


@require_access
async def singular_idfa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sg_idfa"] = update.message.text.strip()
    await update.message.reply_text(
        "🍎 *أدخل IDFV:*\nمثال: `12345678-1234-1234-1234-123456789012`",
        parse_mode="Markdown",
    )
    return SNG_IDFV


@require_access
async def singular_idfv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sg_idfv"] = update.message.text.strip()
    await update.message.reply_text(
        "🆔 *أدخل Custom User ID:*\nمثال: `your_user_id`",
        parse_mode="Markdown",
    )
    return SNG_UID_IOS


@require_access
async def singular_uid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sg_uid"] = update.message.text.strip()
    return await _show_singular_events(update, context)


@require_access
async def singular_uid_ios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sg_uid"] = update.message.text.strip()
    return await _show_singular_events(update, context)


async def _show_singular_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game_id = context.user_data.get("sg_game_id")
    game = context.user_data.get("sg_game", {})
    events = db.get_singular_events(game_id)
    if not events:
        await update.message.reply_text("❌ *لا توجد أحداث*", parse_mode="Markdown", reply_markup=_back_kb("singular_menu"))
        return ConversationHandler.END

    kb = [[InlineKeyboardButton(ev["display_name"], callback_data=f"sg_send_{ev['id']}")] for ev in events]
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="singular_menu")])
    await update.message.reply_text(
        f"🎯 *اختر الحدث - {game.get('display_name', '')}*",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


@require_access
async def singular_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    event_id = int(query.data.replace("sg_send_", ""))

    game_id = context.user_data.get("sg_game_id")
    events = db.get_singular_events(game_id)
    event = next((e for e in events if e["id"] == event_id), None)
    if not event:
        await query.edit_message_text("❌ خطأ: الحدث غير موجود", parse_mode="Markdown")
        return

    game = context.user_data.get("sg_game", {})
    uid = update.effective_user.id
    platform = db.get_user_platform(uid)
    proxy = db.get_proxy_for_user(uid)

    if not game.get("package"):
        await query.edit_message_text("❌ خطأ: Package Name غير موجود", parse_mode="Markdown")
        return
    if not game.get("app_key"):
        await query.edit_message_text("❌ خطأ: App Key غير موجود", parse_mode="Markdown")
        return
    if not context.user_data.get("sg_aifa") and not context.user_data.get("sg_idfa"):
        await query.edit_message_text("❌ خطأ: GAID/AIFA غير موجود. الرجاء إعادة الإدخال.", parse_mode="Markdown")
        return

    await query.edit_message_text("🔄 *جاري الإرسال...*", parse_mode="Markdown")

    status, resp = send_singular(
        event_name=event["event_name"],
        aifa=context.user_data.get("sg_aifa", ""),
        uid=context.user_data.get("sg_uid", ""),
        package=game.get("package", ""),
        app_key=game.get("app_key", ""),
        level=event.get("level_value"),
        proxy=dict(proxy) if proxy else None,
        platform=platform,
        idfa=context.user_data.get("sg_idfa"),
        idfv=context.user_data.get("sg_idfv"),
        singular_uid=context.user_data.get("sg_uid"),
    )

    result_text = "✅ *تم الإرسال بنجاح!*" if status == 200 else f"❌ *فشل الإرسال*\nالكود: `{status}`\n`{resp[:200]}`"
    kb = [[InlineKeyboardButton("🎯 حدث آخر", callback_data=f"sg_game_{game.get('id')}")],
          [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]]

    await query.edit_message_text(
        f"{result_text}\n\n📝 *الحدث:* {event['display_name']}\n🎮 *اللعبة:* {game.get('display_name', '')}",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )


def get_conversation_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(singular_menu, pattern="^singular_menu$")],
        states={
            SNG_AIFA: [MessageHandler(filters.TEXT & ~filters.COMMAND, singular_aifa)],
            SNG_IDFA: [MessageHandler(filters.TEXT & ~filters.COMMAND, singular_idfa)],
            SNG_IDFV: [MessageHandler(filters.TEXT & ~filters.COMMAND, singular_idfv)],
            SNG_UID: [MessageHandler(filters.TEXT & ~filters.COMMAND, singular_uid)],
            SNG_UID_IOS: [MessageHandler(filters.TEXT & ~filters.COMMAND, singular_uid_ios)],
        },
        fallbacks=[CallbackQueryHandler(singular_menu, pattern="^singular_menu$")],
        allow_reentry=True,
    )


def get_handlers():
    return [
        get_conversation_handler(),
        CallbackQueryHandler(singular_game, pattern=r"^sg_game_\d+$"),
        CallbackQueryHandler(singular_send, pattern=r"^sg_send_\d+$"),
    ]
