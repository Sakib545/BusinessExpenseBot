import asyncio
from datetime import timedelta
from io import BytesIO
import logging

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import settings
from expense_parser import parse_amount_only, parse_expense
from sheets import GoogleSheetStore


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

store = GoogleSheetStore(settings)

MENU = ReplyKeyboardMarkup(
    [
        ["📅 আজকের হিসাব", "🗓️ এই মাস"],
        ["📊 সারাংশ", "🗑️ Delete"],
        ["📤 Export PDF / Excel", "ℹ️ Help"],
    ],
    resize_keyboard=True,
    is_persistent=True,
)


def is_authorized(update: Update) -> bool:
    user = update.effective_user
    return bool(user and user.id in settings.allowed_user_ids)


async def reject_if_unauthorized(update: Update) -> bool:
    if is_authorized(update):
        return False
    if update.effective_message:
        await update.effective_message.reply_text("⛔ এই Bot ব্যবহার করার অনুমতি আপনার নেই।")
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update):
        return
    categories = "\n".join(f"• {name}" for name in settings.categories)
    await update.effective_message.reply_text(
        "✅ ব্যবসার খরচের Bot প্রস্তুত।\n\n"
        "এভাবে খরচ লিখুন:\n"
        "10000 তেলের টাকা\n"
        "৫০০০ পলির টাকা\n"
        "3,000 বেতন\n\n"
        f"ক্যাটাগরি:\n{categories}\n\n"
        "কমান্ড:\n"
        "/today — আজকের হিসাব\n"
        "/month — এই মাসের হিসাব\n"
        "/summary — সব ক্যাটাগরির মোট\n"
        "/delete — সাম্প্রতিক খরচ Delete\n"
        "/export — PDF অথবা Excel Export"
        ,
        reply_markup=MENU,
    )


async def save_expense(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update):
        return

    text = update.effective_message.text or ""
    parsed = parse_expense(text, settings.categories)
    if not parsed:
        amount = parse_amount_only(text)
        if amount is not None:
            context.user_data["pending_amount"] = amount
            category_buttons = []
            for index in range(0, len(settings.categories), 2):
                row = [
                    InlineKeyboardButton(
                        settings.categories[index],
                        callback_data=f"category_pick:{index}",
                    )
                ]
                if index + 1 < len(settings.categories):
                    row.append(
                        InlineKeyboardButton(
                            settings.categories[index + 1],
                            callback_data=f"category_pick:{index + 1}",
                        )
                    )
                category_buttons.append(row)
            category_buttons.append(
                [
                    InlineKeyboardButton(
                        "❌ Cancel", callback_data="category_cancel"
                    )
                ]
            )
            await update.effective_message.reply_text(
                f"💰 পরিমাণ: {amount_text(amount)}\n\nএটা কিসের টাকা?",
                reply_markup=InlineKeyboardMarkup(category_buttons),
            )
            return
        await update.effective_message.reply_text(
            "❌ বুঝতে পারিনি। উদাহরণ: 10000 তেলের টাকা\n"
            "সঠিক ক্যাটাগরির নাম ব্যবহার করুন।"
        )
        return

    try:
        date_text = await asyncio.to_thread(
            store.add_expense, parsed.category, parsed.amount
        )
    except Exception:
        logger.exception("Could not save expense")
        await update.effective_message.reply_text(
            "⚠️ Google Sheet-এ সেভ করা যায়নি। কিছুক্ষণ পর আবার চেষ্টা করুন।"
        )
        return

    await update.effective_message.reply_text(
        "✅ খরচ সেভ হয়েছে\n"
        f"📅 তারিখ: {date_text}\n"
        f"📂 ক্যাটাগরি: {parsed.category}\n"
        f"💰 পরিমাণ: ৳{parsed.amount:,.2f}".replace(".00", "")
    )


async def category_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not is_authorized(update):
        await query.edit_message_text("⛔ এই কাজের অনুমতি আপনার নেই।")
        return

    data = query.data or ""
    if data == "category_cancel":
        context.user_data.pop("pending_amount", None)
        await query.edit_message_text("❌ খরচ Save বাতিল করা হয়েছে।")
        return

    amount = context.user_data.get("pending_amount")
    if amount is None:
        await query.edit_message_text(
            "⚠️ এই request-এর সময় শেষ হয়েছে। Amount আবার পাঠান।"
        )
        return
    try:
        category_index = int(data.split(":", 1)[1])
        category = settings.categories[category_index]
    except (ValueError, IndexError):
        await query.edit_message_text("⚠️ Category নির্বাচন সঠিক নয়।")
        return

    try:
        date_text = await asyncio.to_thread(store.add_expense, category, amount)
    except Exception:
        logger.exception("Could not save categorized expense")
        await query.edit_message_text(
            "⚠️ Google Sheet-এ Save করা যায়নি। আবার চেষ্টা করুন।"
        )
        return

    context.user_data.pop("pending_amount", None)
    await query.edit_message_text(
        "✅ খরচ Save হয়েছে\n"
        f"📅 তারিখ: {date_text}\n"
        f"📂 ক্যাটাগরি: {category}\n"
        f"💰 পরিমাণ: {amount_text(amount)}"
    )


def format_report(title: str, rows: list[dict]) -> str:
    if not rows:
        return f"{title}\n\nকোনো খরচ পাওয়া যায়নি।"

    totals: dict[str, float] = {}
    for row in rows:
        category = row["category"]
        totals[category] = totals.get(category, 0) + row["amount"]

    lines = [title, ""]
    for category in settings.categories:
        amount = totals.get(category)
        if amount:
            lines.append(f"• {category}: ৳{amount:,.2f}".replace(".00", ""))
    grand_total = sum(totals.values())
    lines.extend(["", f"মোট: ৳{grand_total:,.2f}".replace(".00", "")])
    return "\n".join(lines)


async def report(
    update: Update, title: str, report_method: str
) -> None:
    if await reject_if_unauthorized(update):
        return
    try:
        rows = await asyncio.to_thread(getattr(store, report_method))
    except Exception:
        logger.exception("Could not read report")
        await update.effective_message.reply_text(
            "⚠️ Google Sheet থেকে রিপোর্ট আনা যায়নি।"
        )
        return
    await update.effective_message.reply_text(format_report(title, rows))


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await report(update, "📅 আজকের হিসাব", "get_today")


async def month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await report(update, "🗓️ এই মাসের হিসাব", "get_month")


async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await report(update, "📊 সব ক্যাটাগরির মোট হিসাব", "get_all")


def amount_text(amount: float) -> str:
    return f"৳{amount:,.2f}".replace(".00", "")


async def delete_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if await reject_if_unauthorized(update):
        return
    try:
        rows = await asyncio.to_thread(store.get_recent, 10)
    except Exception:
        logger.exception("Could not load recent expenses")
        await update.effective_message.reply_text(
            "⚠️ সাম্প্রতিক খরচ আনা যায়নি।", reply_markup=MENU
        )
        return

    if not rows:
        await update.effective_message.reply_text(
            "Delete করার মতো কোনো খরচ নেই।", reply_markup=MENU
        )
        return

    buttons = []
    for row in rows:
        label = (
            f"#{row['row_number']} • {row['date'].strftime('%d-%m')} • "
            f"{row['category']} • {amount_text(row['amount'])}"
        )
        buttons.append(
            [
                InlineKeyboardButton(
                    label, callback_data=f"delete_pick:{row['row_number']}"
                )
            ]
        )
    buttons.append([InlineKeyboardButton("❌ বাতিল", callback_data="delete_cancel")])
    await update.effective_message.reply_text(
        "🗑️ যে খরচটি Delete করতে চান সেটি নির্বাচন করুন:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def delete_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not is_authorized(update):
        await query.edit_message_text("⛔ এই কাজের অনুমতি আপনার নেই।")
        return

    data = query.data or ""
    if data == "delete_cancel":
        await query.edit_message_text("❌ Delete বাতিল করা হয়েছে।")
        return

    if data.startswith("delete_pick:"):
        try:
            row_number = int(data.split(":", 1)[1])
            row = await asyncio.to_thread(store.get_expense, row_number)
        except (ValueError, TypeError):
            row = None
        except Exception:
            logger.exception("Could not load selected expense")
            row = None

        if not row:
            await query.edit_message_text(
                "⚠️ খরচটি পাওয়া যায়নি বা আগেই Delete হয়েছে।"
            )
            return

        text = (
            "⚠️ এই খরচটি Delete করবেন?\n\n"
            f"📅 {row['date'].strftime('%Y-%m-%d')}\n"
            f"📂 {row['category']}\n"
            f"💰 {amount_text(row['amount'])}"
        )
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Confirm", callback_data=f"delete_ok:{row_number}"
                    ),
                    InlineKeyboardButton("❌ Cancel", callback_data="delete_cancel"),
                ]
            ]
        )
        await query.edit_message_text(text, reply_markup=keyboard)
        return

    if data.startswith("delete_ok:"):
        try:
            row_number = int(data.split(":", 1)[1])
            deleted = await asyncio.to_thread(store.delete_expense, row_number)
        except (ValueError, TypeError):
            deleted = None
        except Exception:
            logger.exception("Could not delete expense")
            deleted = None

        if not deleted:
            await query.edit_message_text(
                "⚠️ খরচটি পাওয়া যায়নি বা আগেই Delete হয়েছে।"
            )
            return
        await query.edit_message_text(
            "✅ খরচ Delete হয়েছে\n\n"
            f"📅 {deleted['date'].strftime('%Y-%m-%d')}\n"
            f"📂 {deleted['category']}\n"
            f"💰 {amount_text(deleted['amount'])}"
        )


async def export_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if await reject_if_unauthorized(update):
        return
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📅 Weekly", callback_data="export_list:week"),
                InlineKeyboardButton("🗓️ Monthly", callback_data="export_list:month"),
            ],
            [InlineKeyboardButton("📚 সব হিসাব", callback_data="export_format:all:0")],
            [InlineKeyboardButton("❌ Cancel", callback_data="export_cancel")],
        ]
    )
    await update.effective_message.reply_text(
        "📤 কোন সময়ের হিসাব Export চান?",
        reply_markup=keyboard,
    )


def month_label(offset: int) -> str:
    month_names = (
        "জানুয়ারি", "ফেব্রুয়ারি", "মার্চ", "এপ্রিল", "মে", "জুন",
        "জুলাই", "আগস্ট", "সেপ্টেম্বর", "অক্টোবর", "নভেম্বর", "ডিসেম্বর",
    )
    now = store.now()
    month_index = now.year * 12 + now.month - 1 - offset
    year, zero_based_month = divmod(month_index, 12)
    if offset == 0:
        prefix = "চলতি মাস"
    elif offset == 1:
        prefix = "গত মাস"
    else:
        prefix = month_names[zero_based_month]
    return f"{prefix} ({month_names[zero_based_month]} {year})"


def week_label(offset: int) -> str:
    today = store.now().date()
    current_monday = today - timedelta(days=today.weekday())
    start = current_monday - timedelta(weeks=offset)
    end = start + timedelta(days=6)
    if offset == 0:
        prefix = "চলতি সপ্তাহ"
    elif offset == 1:
        prefix = "গত সপ্তাহ"
    else:
        prefix = f"{offset} সপ্তাহ আগে"
    return f"{prefix} ({start:%d/%m}–{end:%d/%m})"


async def export_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not is_authorized(update):
        await query.edit_message_text("⛔ এই কাজের অনুমতি আপনার নেই।")
        return

    data = query.data or ""
    if data == "export_cancel":
        await query.edit_message_text("❌ Export বাতিল করা হয়েছে।")
        return

    if data.startswith("export_list:"):
        period = data.split(":", 1)[1]
        if period == "month":
            count = 12
            label_function = month_label
        elif period == "week":
            count = 8
            label_function = week_label
        else:
            return
        buttons = [
            [
                InlineKeyboardButton(
                    label_function(offset),
                    callback_data=f"export_format:{period}:{offset}",
                )
            ]
            for offset in range(count)
        ]
        buttons.append(
            [InlineKeyboardButton("⬅️ পেছনে", callback_data="export_home")]
        )
        await query.edit_message_text(
            "যে সময়ের হিসাব চান সেটি নির্বাচন করুন:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    if data == "export_home":
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("📅 Weekly", callback_data="export_list:week"),
                    InlineKeyboardButton("🗓️ Monthly", callback_data="export_list:month"),
                ],
                [InlineKeyboardButton("📚 সব হিসাব", callback_data="export_format:all:0")],
                [InlineKeyboardButton("❌ Cancel", callback_data="export_cancel")],
            ]
        )
        await query.edit_message_text(
            "📤 কোন সময়ের হিসাব Export চান?", reply_markup=keyboard
        )
        return

    if data.startswith("export_format:"):
        _, period, offset_text = data.split(":")
        offset = int(offset_text)
        period_title = (
            month_label(offset)
            if period == "month"
            else week_label(offset)
            if period == "week"
            else "সব হিসাব"
        )
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "📄 PDF", callback_data=f"export_run:{period}:{offset}:pdf"
                    ),
                    InlineKeyboardButton(
                        "📊 Excel", callback_data=f"export_run:{period}:{offset}:xlsx"
                    ),
                ],
                [InlineKeyboardButton("❌ Cancel", callback_data="export_cancel")],
            ]
        )
        await query.edit_message_text(
            f"📤 {period_title}\n\nকোন format চান?",
            reply_markup=keyboard,
        )
        return

    if not data.startswith("export_run:"):
        return
    _, period, offset_text, file_format = data.split(":")
    offset = int(offset_text)
    period_title = (
        month_label(offset)
        if period == "month"
        else week_label(offset)
        if period == "week"
        else "সব হিসাব"
    )
    label = "PDF" if file_format == "pdf" else "Excel"
    extension = "pdf" if file_format == "pdf" else "xlsx"
    filename = f"business-expenses-{period}-{offset}.{extension}"
    await query.edit_message_text(f"⏳ {period_title}—{label} তৈরি হচ্ছে...")
    try:
        file_bytes = await asyncio.to_thread(
            store.export_period,
            period,
            offset,
            file_format,
            period_title,
        )
    except Exception:
        logger.exception("Could not export spreadsheet")
        await query.edit_message_text(
            "⚠️ Export করা যায়নি। কিছুক্ষণ পর আবার চেষ্টা করুন।"
        )
        return

    document = BytesIO(file_bytes)
    document.name = filename
    await query.message.reply_document(
        document=document,
        filename=filename,
        caption=f"✅ {period_title}—{label} Export",
    )
    await query.edit_message_text(f"✅ {label} file তৈরি হয়েছে।")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled Telegram update error", exc_info=context.error)


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("start", "Bot চালু ও Menu দেখুন"),
            BotCommand("today", "আজকের হিসাব"),
            BotCommand("month", "এই মাসের হিসাব"),
            BotCommand("summary", "সব ক্যাটাগরির মোট"),
            BotCommand("delete", "সাম্প্রতিক খরচ Delete"),
            BotCommand("export", "PDF অথবা Excel Export"),
            BotCommand("help", "সাহায্য ও Menu"),
        ]
    )


def main() -> None:
    settings.validate()
    store.ensure_sheet()

    app = (
        Application.builder()
        .token(settings.bot_token)
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("month", month))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CommandHandler("delete", delete_menu))
    app.add_handler(CommandHandler("export", export_menu))
    app.add_handler(
        MessageHandler(filters.Regex(r"^📅 আজকের হিসাব$"), today)
    )
    app.add_handler(MessageHandler(filters.Regex(r"^🗓️ এই মাস$"), month))
    app.add_handler(MessageHandler(filters.Regex(r"^📊 সারাংশ$"), summary))
    app.add_handler(MessageHandler(filters.Regex(r"^🗑️ Delete$"), delete_menu))
    app.add_handler(
        MessageHandler(filters.Regex(r"^📤 Export PDF / Excel$"), export_menu)
    )
    app.add_handler(MessageHandler(filters.Regex(r"^ℹ️ Help$"), start))
    app.add_handler(
        CallbackQueryHandler(delete_callback, pattern=r"^delete_(pick:|ok:|cancel)")
    )
    app.add_handler(
        CallbackQueryHandler(export_callback, pattern=r"^export_(list:|format:|run:|home|cancel)")
    )
    app.add_handler(
        CallbackQueryHandler(
            category_callback, pattern=r"^category_(pick:|cancel)"
        )
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_expense))
    app.add_error_handler(error_handler)

    logger.info("Business Expense Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
