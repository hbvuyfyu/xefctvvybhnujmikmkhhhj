import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
)

from src.database import queries as db
from src.middlewares.auth import require_access
from src.services.appsflyer import send_af

logger = logging.getLogger(__name__)

AF_GAID, AF_IDFA, AF_IDFV, AF_UID, AF_UID_IOS = range(100, 105)


def _result_text(status: int, resp: str) -> str:
    if status == 200:
        return "✅ *تم الإرسال بنجاح!*"
    return f"❌ *فشل الإرسال*\nالكود: `{status}`\n`{resp[:200]}`"


def _back_kb(data: str = "af_menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data=data)]])


@require_access
async def af_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    games = db.get_all_games_af()
    if not games:
        await query.edit_message_text("❌ *لا توجد ألعاب AppsFlyer*", parse_mode="Markdown", reply_markup=_back_kb("main_menu"))
        return ConversationHandler.END

    kb = [[InlineKeyboardButton(f"{g['emoji']} {g['display_name']}", callback_data=f"af_game_{g['id']}")] for g in games]
    kb.append([InlineKeyboardButton("🔍 بحث", callback_data="af_search")])
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
    await query.edit_message_text("📱 *اختر اللعبة - AppsFlyer*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


@require_access
async def af_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game_id = int(query.data.replace("af_game_", ""))
    game = db.get_game_af_by_id(game_id)
    if not game:
        await query.edit_message_text("❌ خطأ: اللعبة غير موجودة", parse_mode="Markdown")
        return ConversationHandler.END

    context.user_data["af_game_id"] = game_id
    context.user_data["af_game"] = dict(game)
    uid = update.effective_user.id
    platform = db.get_user_platform(uid)

    if platform == "ios":
        await query.edit_message_text(
            f"🍎 *iOS - AppsFlyer*\n\n📱 *أدخل IDFA:*\nمثال: `12345678-1234-1234-1234-123456789012`",
            parse_mode="Markdown",
        )
        return AF_IDFA
    else:
        await query.edit_message_text(
            f"🤖 *Android - AppsFlyer*\n\n📱 *أدخل GAID:*\nمثال: `8de8604d-1318-4fd0-907c-402ea9de2529`",
            parse_mode="Markdown",
        )
        return AF_GAID


@require_access
async def af_gaid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gaid = update.message.text.strip()
    context.user_data["af_gaid"] = gaid
    await update.message.reply_text(
        "📱 *أدخل AF UID (AppsFlyer ID):*\nمثال: `1777884483`",
        parse_mode="Markdown",
    )
    return AF_UID


@require_access
async def af_idfa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    idfa = update.message.text.strip()
    context.user_data["af_idfa"] = idfa
    await update.message.reply_text(
        "🍎 *أدخل IDFV:*\nمثال: `12345678-1234-1234-1234-123456789012`",
        parse_mode="Markdown",
    )
    return AF_IDFV


@require_access
async def af_idfv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    idfv = update.message.text.strip()
    context.user_data["af_idfv"] = idfv
    await update.message.reply_text(
        "📱 *أدخل AF UID (AppsFlyer ID):*\nمثال: `1777884483`",
        parse_mode="Markdown",
    )
    return AF_UID_IOS


@require_access
async def af_uid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    af_uid_val = update.message.text.strip()
    context.user_data["af_uid"] = af_uid_val
    return await _show_af_events(update, context)


@require_access
async def af_uid_ios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    af_uid_val = update.message.text.strip()
    context.user_data["af_uid"] = af_uid_val
    return await _show_af_events(update, context)


async def _show_af_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game_id = context.user_data.get("af_game_id")
    game = context.user_data.get("af_game", {})
    events = db.get_af_events(game_id)
    if not events:
        await update.message.reply_text("❌ *لا توجد أحداث*", parse_mode="Markdown", reply_markup=_back_kb("af_menu"))
        return ConversationHandler.END

    kb = [[InlineKeyboardButton(ev["display_name"], callback_data=f"af_send_{ev['id']}")] for ev in events]
    kb.append([InlineKeyboardButton("✏️ حدث مخصص", callback_data="af_custom")])
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="af_menu")])
    await update.message.reply_text(
        f"🎯 *اختر الحدث - {game.get('display_name', '')}*",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


@require_access
async def af_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    event_id = int(query.data.replace("af_send_", ""))

    events = db.get_af_events(context.user_data.get("af_game_id"))
    event = next((e for e in events if e["id"] == event_id), None)
    if not event:
        await query.edit_message_text("❌ خطأ: الحدث غير موجود", parse_mode="Markdown")
        return

    game = context.user_data.get("af_game", {})
    uid = update.effective_user.id
    platform = db.get_user_platform(uid)
    proxy = db.get_proxy_for_user(uid)

    await query.edit_message_text("🔄 *جاري الإرسال...*", parse_mode="Markdown")

    status, resp = send_af(
        pkg=game.get("package", ""),
        dev_key=game.get("dev_key", ""),
        gaid=context.user_data.get("af_gaid", ""),
        af_uid=context.user_data.get("af_uid", ""),
        event_name=event["event_name"],
        revenue=event.get("revenue"),
        proxy=dict(proxy) if proxy else None,
        platform=platform,
        idfa=context.user_data.get("af_idfa"),
        idfv=context.user_data.get("af_idfv"),
        level=event.get("level_value"),
    )

    result_text = _result_text(status, resp)
    kb = [[InlineKeyboardButton("🎯 حدث آخر", callback_data=f"af_game_{game.get('id')}")],
          [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]]

    await query.edit_message_text(
        f"{result_text}\n\n📝 *الحدث:* {event['display_name']}\n🎮 *اللعبة:* {game.get('display_name', '')}",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )


@require_access
async def af_resend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game_id = int(query.data.replace("af_game_", ""))
    context.user_data["af_game_id"] = game_id
    context.user_data["af_game"] = dict(db.get_game_af_by_id(game_id) or {})
    return await _show_af_events_cb(query, context)


async def _show_af_events_cb(query, context):
    game_id = context.user_data.get("af_game_id")
    game = context.user_data.get("af_game", {})
    events = db.get_af_events(game_id)
    kb = [[InlineKeyboardButton(ev["display_name"], callback_data=f"af_send_{ev['id']}")] for ev in events]
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="af_menu")])
    await query.edit_message_text(
        f"🎯 *اختر الحدث - {game.get('display_name', '')}*",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )


def get_conversation_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(af_menu, pattern="^af_menu$")],
        states={
            AF_GAID: [MessageHandler(filters.TEXT & ~filters.COMMAND, af_gaid)],
            AF_IDFA: [MessageHandler(filters.TEXT & ~filters.COMMAND, af_idfa)],
            AF_IDFV: [MessageHandler(filters.TEXT & ~filters.COMMAND, af_idfv)],
            AF_UID: [MessageHandler(filters.TEXT & ~filters.COMMAND, af_uid)],
            AF_UID_IOS: [MessageHandler(filters.TEXT & ~filters.COMMAND, af_uid_ios)],
        },
        fallbacks=[CallbackQueryHandler(af_menu, pattern="^af_menu$")],
        allow_reentry=True,
    )


def get_handlers():
    return [
        get_conversation_handler(),
        CallbackQueryHandler(af_game, pattern=r"^af_game_\d+$"),
        CallbackQueryHandler(af_send, pattern=r"^af_send_\d+$"),
    ]
