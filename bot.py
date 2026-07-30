import asyncio
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
from expense_parser import parse_expense
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
        ["ℹ️ Help"],
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
        "/delete — সাম্প্রতিক খরচ Delete"
        ,
        reply_markup=MENU,
    )


async def save_expense(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update):
        return

    text = update.effective_message.text or ""
    parsed = parse_expense(text, settings.categories)
    if not parsed:
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
    app.add_handler(
        MessageHandler(filters.Regex(r"^📅 আজকের হিসাব$"), today)
    )
    app.add_handler(MessageHandler(filters.Regex(r"^🗓️ এই মাস$"), month))
    app.add_handler(MessageHandler(filters.Regex(r"^📊 সারাংশ$"), summary))
    app.add_handler(MessageHandler(filters.Regex(r"^🗑️ Delete$"), delete_menu))
    app.add_handler(MessageHandler(filters.Regex(r"^ℹ️ Help$"), start))
    app.add_handler(
        CallbackQueryHandler(delete_callback, pattern=r"^delete_(pick:|ok:|cancel)")
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_expense))
    app.add_error_handler(error_handler)

    logger.info("Business Expense Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
