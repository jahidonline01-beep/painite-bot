import os
import asyncio
import logging
import time
import threading
import uvicorn
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup, error
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, CallbackQueryHandler, ContextTypes
)
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest

import database as db
import admin_api as api
from panel import panel_instance
from utils import detect_country_from_phone, normalize_number, extract_otp, html_escape, mask_phone
from config import (
    TELEGRAM_BOT_TOKEN, GROUP_ID, CHANNEL_ID, ADMIN_ID,
    ADMIN_USERNAME, UPDATE_CHANNEL_LINK, GROUP_LINK,
    PORT, ADMIN_API_TOKEN
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler()]
)

shutdown_event = asyncio.Event()

# ─── Keyboards ───────────────────────────────────────────────────────────────

def main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📱 Paid Number"), KeyboardButton("📱 Get Number (Random)")],
        [KeyboardButton("🌍 Get Country"),  KeyboardButton("🔐 OTP Check")],
    ], resize_keyboard=True)

# ─── Subscription Check ───────────────────────────────────────────────────────

async def check_sub(update: Update, ctx: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    try:
        member = await ctx.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return str(member.status.value).lower() in ['member', 'administrator', 'creator']
    except Exception:
        return False

# ─── /start ──────────────────────────────────────────────────────────────────

async def start_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_sub = await check_sub(update, ctx, user.id)
    if not is_sub:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Join Update Channel", url=UPDATE_CHANNEL_LINK)],
            [InlineKeyboardButton("🔄 Try Again", callback_data="check_join")],
        ])
        text = (
            "<b>🛑 Access Restricted!</b>\n\n"
            "<blockquote>Please join our update channel to use the bot.</blockquote>"
        )
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    db.save_user(str(user.id), user.username or "", user.first_name or "Anonymous")

    welcome = (
        f"<b>🎉 Welcome, {html_escape(user.first_name or 'User')}!</b>\n\n"
        f"<blockquote>⏰ <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}\n"
        f"🤖 <b>Bot:</b> Painite OTP Bot</blockquote>\n\n"
        f"<b>🚀 Choose an option below to get started!</b>"
    )

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                "<b>✅ Access Granted!</b>\n\n<i>Loading...</i>",
                reply_markup=None, parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
        await ctx.bot.send_message(
            chat_id=update.effective_chat.id,
            text=welcome, reply_markup=main_menu(), parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(welcome, reply_markup=main_menu(), parse_mode=ParseMode.HTML)

# ─── Number Assignment ────────────────────────────────────────────────────────

async def send_maintenance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = (
        "<b>🛠 Bot Under Maintenance</b>\n\n"
        "<blockquote>The bot is temporarily turned off by the admin.\n"
        "Please try again later.</blockquote>"
    )
    query = update.callback_query
    if query:
        try:
            await query.edit_message_text(msg, parse_mode=ParseMode.HTML, reply_markup=None)
        except Exception:
            pass
        await ctx.bot.send_message(update.effective_chat.id, "Use the menu below.", reply_markup=main_menu())
    else:
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=main_menu())

async def _reply(update: Update, ctx: ContextTypes.DEFAULT_TYPE, text: str, kb=None):
    """Reply whether the update came from a text button or an inline callback."""
    query = update.callback_query
    if query:
        try:
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        except Exception:
            await ctx.bot.send_message(update.effective_chat.id, text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def allocate(update: Update, ctx: ContextTypes.DEFAULT_TYPE, rid: str, change_cb: str, bypass: bool = False):
    """Allocate one live number from the panel for the given range id (rid)."""
    if not await asyncio.to_thread(db.is_bot_active):
        return await send_maintenance(update, ctx)
    if not rid:
        return await _reply(
            update, ctx,
            "<b>😔 No Ranges Available</b>\n\n"
            "<blockquote>The panel has no active ranges right now. Try again later.</blockquote>",
            main_menu(),
        )

    user = update.effective_user
    user_id = str(user.id)
    user_data = db.get_user(user_id) or {}
    cooldown = 5
    last_time = user_data.get('last_number_time', 0) or 0
    now = time.time()

    if not bypass and (now - last_time) < cooldown:
        remaining = int(cooldown - (now - last_time))
        return await _reply(
            update, ctx,
            f"<b>⏰ Please Wait</b>\n\n<blockquote>🕐 <b>Cooldown:</b> {remaining} seconds</blockquote>",
            main_menu(),
        )

    res = await asyncio.to_thread(panel_instance.get_number, rid)

    if not res.get('success'):
        if res.get('error') == 'out_of_stock':
            body = "This range is out of stock. Try Change Number or another country."
        else:
            body = f"Could not get a number ({html_escape(str(res.get('error', 'error')))})."
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Try Again", callback_data=change_cb)],
            [InlineKeyboardButton("↩️ Back", callback_data="main_menu")],
        ])
        return await _reply(update, ctx, f"<b>❌ No Number</b>\n\n<blockquote>{body}</blockquote>", kb)

    db.update_user_number_time(user_id, now)

    phone = res.get('full_number') or ("+" + str(res.get('no_plus_number', '')))
    c_name = res.get('country') or detect_country_from_phone(phone)[0]
    c_flag = detect_country_from_phone(phone)[1]
    operator = res.get('operator', '')

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Change Number", callback_data=change_cb)],
        [InlineKeyboardButton("🔐 Get OTP", callback_data="main_menu")],
        [InlineKeyboardButton("↩️ Back", callback_data="main_menu")],
    ])

    op_line = f"<blockquote>📡 <b>Operator:</b> {html_escape(operator)}</blockquote>\n\n" if operator else ""
    msg = (
        f"<b>🔥 {html_escape(c_name)} Number Ready!</b>\n\n"
        f"<blockquote>⏰ <b>Time:</b> <code>{datetime.now().strftime('%H:%M:%S')}</code></blockquote>\n\n"
        f"<blockquote>🌍 <b>Country:</b> {html_escape(c_flag)} {html_escape(c_name)}</blockquote>\n\n"
        f"{op_line}"
        f"<blockquote>☎️ <b>Number:</b> <code>{html_escape(phone)}</code></blockquote>\n\n"
        f"<i>Use this number, then tap 🔐 OTP Check and paste it to read the code.</i>"
    )
    await _reply(update, ctx, msg, kb)

# ─── Button Handlers ──────────────────────────────────────────────────────────

async def handle_paid_number(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    admin = ADMIN_USERNAME.lstrip('@')
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 Message Admin", url=f"https://t.me/{admin}")]])
    await update.message.reply_text(
        "<b>🤝 Contact Admin for Paid Number</b>\n\n"
        "<blockquote>Click below to message the admin and say: <i>'sir i want to buy paid number'</i></blockquote>",
        parse_mode=ParseMode.HTML, reply_markup=kb
    )

async def handle_random_number(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await check_sub(update, ctx, update.effective_user.id):
        return await start_command(update, ctx)
    if not await asyncio.to_thread(db.is_bot_active):
        return await send_maintenance(update, ctx)
    await update.message.reply_text("<b>🎲 Getting a number...</b>", parse_mode=ParseMode.HTML)
    rid = await asyncio.to_thread(panel_instance.latest_rid)
    await allocate(update, ctx, rid, "rnd")

async def handle_country_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await check_sub(update, ctx, update.effective_user.id):
        return await start_command(update, ctx)
    if not await asyncio.to_thread(db.is_bot_active):
        return await send_maintenance(update, ctx)

    await update.message.reply_text("<b>🌍 Loading countries...</b>", parse_mode=ParseMode.HTML)
    countries = await asyncio.to_thread(panel_instance.get_countries)
    if not countries:
        await update.message.reply_text(
            "<b>😔 No Countries Available</b>\n\n"
            "<blockquote>The panel has no active ranges right now. Try later.</blockquote>",
            parse_mode=ParseMode.HTML, reply_markup=main_menu()
        )
        return

    btns = [
        [InlineKeyboardButton(
            f"{c['flag']} {c['country']} ({len(c['ranges'])})",
            callback_data=f"gc:{c['ranges'][0]}"
        )]
        for c in countries
    ]
    btns.append([InlineKeyboardButton("↩️ Back", callback_data="main_menu")])
    await update.message.reply_text(
        f"<b>🌍 Choose Country</b>\n\n<blockquote>📊 <b>Available:</b> {len(countries)} countries</blockquote>",
        parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btns)
    )

async def handle_otp_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await check_sub(update, ctx, update.effective_user.id):
        return await start_command(update, ctx)
    if not await asyncio.to_thread(db.is_bot_active):
        return await send_maintenance(update, ctx)
    ctx.user_data['state'] = 'WAITING_OTP'
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Join OTP Group", url=GROUP_LINK)],
        [InlineKeyboardButton("❌ Cancel", callback_data="main_menu")],
    ])
    await update.message.reply_text(
        "<b>🔐 OTP Check</b>\n\n"
        "<blockquote>Send the full phone number (with country code)\ne.g: +8801XXXXXXXXX</blockquote>",
        parse_mode=ParseMode.HTML, reply_markup=kb
    )

async def handle_otp_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data.get('state') != 'WAITING_OTP':
        return
    ctx.user_data['state'] = None
    input_num = update.message.text.strip()
    normalized = normalize_number(input_num)

    if len(normalized) < 5:
        await update.message.reply_text(
            "<b>❌ Invalid Number</b>\n\n<blockquote>Please send a valid phone number.</blockquote>",
            parse_mode=ParseMode.HTML, reply_markup=main_menu()
        )
        return

    await update.message.reply_text("<b>🔍 Checking... Please wait.</b>", parse_mode=ParseMode.HTML)

    sms_list = await asyncio.to_thread(panel_instance.fetch_sms)
    found = [s for s in sms_list if normalize_number(s.get('phone', '')) == normalized]

    if found:
        sms = found[-1]
        otp = extract_otp(sms.get('message', ''))
        otp_display = f"<code>{otp}</code>" if otp != "N/A" else "Not found"
        await update.message.reply_text(
            f"<b>✅ OTP Found!</b>\n\n"
            f"<blockquote>☎️ <b>Number:</b> <code>{html_escape(sms.get('phone', ''))}</code></blockquote>\n\n"
            f"<blockquote>⚙️ <b>Service:</b> {html_escape(sms.get('service', 'Unknown'))}</blockquote>\n\n"
            f"<blockquote>🔑 <b>OTP:</b> {otp_display}</blockquote>\n\n"
            f"<b>✉️ Full Message:</b>\n<blockquote><i>{html_escape(sms.get('message', ''))}</i></blockquote>",
            parse_mode=ParseMode.HTML, reply_markup=main_menu()
        )
    else:
        await update.message.reply_text(
            f"<b>😔 No OTP Found</b>\n\n"
            f"<blockquote>No messages found for <code>{html_escape(input_num)}</code>.\nWait a moment and try again.</blockquote>",
            parse_mode=ParseMode.HTML, reply_markup=main_menu()
        )

# ─── Callback Handler ─────────────────────────────────────────────────────────

async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data
    if data in ('main_menu', 'check_join'):
        await start_command(update, ctx)
    elif data == 'rnd':
        rid = await asyncio.to_thread(panel_instance.latest_rid)
        await allocate(update, ctx, rid, "rnd", bypass=True)
    elif data.startswith('gc:'):
        rid = data.split(':', 1)[1]
        await allocate(update, ctx, rid, f"gn:{rid}", bypass=False)
    elif data.startswith('gn:'):
        rid = data.split(':', 1)[1]
        await allocate(update, ctx, rid, f"gn:{rid}", bypass=True)

# ─── Text Handler ─────────────────────────────────────────────────────────────

async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        return
    text = update.message.text

    if ctx.user_data.get('state') == 'WAITING_OTP':
        await handle_otp_input(update, ctx)
        return

    if text == "📱 Paid Number":
        await handle_paid_number(update, ctx)
    elif text == "📱 Get Number (Random)":
        await handle_random_number(update, ctx)
    elif text == "🌍 Get Country":
        await handle_country_menu(update, ctx)
    elif text == "🔐 OTP Check":
        await handle_otp_menu(update, ctx)
    else:
        await update.message.reply_text(
            "<b>❌ Unknown command</b>\n\n<blockquote>Please use the buttons below.</blockquote>",
            parse_mode=ParseMode.HTML, reply_markup=main_menu()
        )

# ─── Admin Commands ───────────────────────────────────────────────────────────

async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if (update.effective_user.username or "").lstrip('@') != ADMIN_USERNAME.lstrip('@'):
        return
    s = db.get_stats()
    await update.message.reply_text(
        f"<b>📊 Bot Statistics</b>\n\n"
        f"<blockquote>👥 Users: <b>{s['users']}</b>\n"
        f"📱 Numbers: <b>{s['numbers']}</b>\n"
        f"📨 SMS Sent: <b>{s['sms_sent']}</b></blockquote>",
        parse_mode=ParseMode.HTML
    )

async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if (update.effective_user.username or "").lstrip('@') != ADMIN_USERNAME.lstrip('@'):
        return
    if not ctx.args:
        await update.message.reply_text("<b>Usage:</b> /update your message here", parse_mode=ParseMode.HTML)
        return
    msg = " ".join(ctx.args)
    users = db.get_all_users()
    ok = fail = 0
    await update.message.reply_text(f"📢 Sending to {len(users)} users...")
    for u in users:
        try:
            await ctx.bot.send_message(
                chat_id=u['user_id'],
                text=f"<blockquote>{html_escape(msg)}</blockquote>",
                parse_mode=ParseMode.HTML
            )
            ok += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1
    await update.message.reply_text(
        f"<b>📢 Done!</b>\n✅ {ok} sent | ❌ {fail} failed", parse_mode=ParseMode.HTML
    )

# ─── SMS Watcher ──────────────────────────────────────────────────────────────

async def sms_watcher(application: Application):
    logging.info("SMS watcher started")
    while not shutdown_event.is_set():
        try:
            if not await asyncio.to_thread(db.is_bot_active):
                await asyncio.sleep(10)
                continue
            sms_list = await asyncio.to_thread(panel_instance.fetch_sms)
            for sms in sms_list:
                phone = sms.get('phone', '')
                message = sms.get('message', '')
                if not phone or not message:
                    continue

                unique_key = sms.get('otp_id') or f"{phone}|{message}"
                if db.is_sms_sent(unique_key):
                    continue

                otp = extract_otp(message)
                country, flag = detect_country_from_phone(phone)
                masked = mask_phone(phone)
                otp_display = f"<code>{otp}</code>" if otp != "N/A" else "Not found"

                group_msg = (
                    f"<b>📱 New {'OTP' if otp != 'N/A' else 'SMS'} Received! ✨</b>\n\n"
                    f"<blockquote>📞 <b>Number:</b> <code>{html_escape(masked)}</code></blockquote>\n\n"
                    f"<blockquote>🌍 <b>Country:</b> {html_escape(flag)} {html_escape(country)}</blockquote>\n\n"
                    f"<blockquote>🔑 <b>OTP:</b> {otp_display}</blockquote>\n\n"
                    f"<blockquote>⏰ <b>Time:</b> <code>{datetime.now().strftime('%H:%M:%S')}</code></blockquote>\n\n"
                    f"<b>✉️ Message:</b>\n<blockquote><i>{html_escape(message)}</i></blockquote>"
                )
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("📢 Update Channel", url=UPDATE_CHANNEL_LINK)]])

                try:
                    await application.bot.send_message(GROUP_ID, group_msg, parse_mode=ParseMode.HTML, reply_markup=kb)
                except Exception as e:
                    logging.error(f"Group send error: {e}")

                try:
                    admin_msg = (
                        f"<b>📱 New SMS (Admin)</b>\n\n"
                        f"<blockquote>📞 <b>Number:</b> <code>{html_escape(phone)}</code>\n"
                        f"🌍 <b>Country:</b> {html_escape(flag)} {html_escape(country)}\n"
                        f"🔑 <b>OTP:</b> {otp_display}\n\n"
                        f"📝 <b>Message:</b>\n{html_escape(message)}</blockquote>"
                    )
                    await application.bot.send_message(ADMIN_ID, admin_msg, parse_mode=ParseMode.HTML)
                except Exception as e:
                    logging.error(f"Admin send error: {e}")

                db.mark_sms_sent(unique_key, phone, message, otp, country)

        except Exception as e:
            logging.error(f"SMS watcher error: {e}")

        await asyncio.sleep(10)

# ─── Broadcast Callback for Admin API ─────────────────────────────────────────

_app_ref = None

async def _do_broadcast(message: str, user_ids: list) -> dict:
    if not _app_ref:
        return {"success": False, "sent": 0, "failed": 0}
    ok = fail = 0
    for uid in user_ids:
        try:
            await _app_ref.bot.send_message(
                chat_id=uid,
                text=f"<blockquote>{html_escape(message)}</blockquote>",
                parse_mode=ParseMode.HTML
            )
            ok += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1
    return {"success": True, "sent": ok, "failed": fail}

# ─── Admin API Server ─────────────────────────────────────────────────────────

def run_api_server():
    uvicorn.run(api.app, host="0.0.0.0", port=PORT, log_level="warning")

# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    global _app_ref
    db.init_db()

    request = HTTPXRequest(connection_pool_size=8, read_timeout=30, write_timeout=30, connect_timeout=10)
    application = (Application.builder().token(TELEGRAM_BOT_TOKEN).request(request).build())
    _app_ref = application

    api.set_broadcast_callback(_do_broadcast)

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("update", cmd_broadcast))
    application.add_handler(CommandHandler("stats", cmd_stats))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    api_thread = threading.Thread(target=run_api_server, daemon=True)
    api_thread.start()
    logging.info(f"Admin API running on port {PORT}")

    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    logging.info("Bot started successfully")

    try:
        await application.bot.send_message(GROUP_ID, "✅ <b>Painite Bot is Active</b>", parse_mode=ParseMode.HTML)
    except Exception:
        pass

    sms_task = asyncio.create_task(sms_watcher(application))

    await shutdown_event.wait()

    sms_task.cancel()
    await application.updater.stop()
    await application.stop()
    await application.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped.")
