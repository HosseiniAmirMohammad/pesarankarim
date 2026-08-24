from telegram import Update,InlineKeyboardButton,InlineKeyboardMarkup,ReplyKeyboardMarkup,KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler,MessageHandler,filters,ContextTypes

TOKEN = "8779458070:AAH8kDG-iBv1XvDWQ-3kUqcHI2meZqB8yY8"
CHANNEL_USERNAME = "@pesaranekarim"
CHANNEL_ID = "-1001586571412"

# def make_keyboard(buttons, row_width=2):
#     return InlineKeyboardMarkup(
#         [buttons[i:i+row_width] for i in range(0, len(buttons), row_width)]
#     )

# async def real_member(context,user_id):
#     try:
#         member = await context.bot.get_chat_member(CHANNEL_ID,user_id)
#         return member.status in ["member","administrator","creator"]
#     except:
#         return False


# BTN_JOIN = InlineKeyboardButton("عضویت در کانال",url="https://t.me/pesaranekarim")
# BTN_CHECK = InlineKeyboardButton("بررسی عضویت",callback_data="check")

BTN_MASHHAD = InlineKeyboardButton("شعبه مشهد (خیام)", callback_data="branch_mashhad")
BTN_TEHRAN = InlineKeyboardButton("شعبه تهران", callback_data="branch_tehran")

# def membership_kb():
#     return make_keyboard([BTN_JOIN,BTN_CHECK], row_width=1)

def branch_kb():
    return ReplyKeyboardMarkup(
        [[BTN_MASHHAD, BTN_TEHRAN]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

async def start(update,context):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "کاربر گرامی"

    # if await real_member(context,user_id):
    #     await update.message.reply_text(
    #         "سلام به ربات رستوران پسران کریم خوش آمدید."
    #         "لطفا شعبه مورد نظر خود را انتخاب کنید:",
    #         reply_markup=branch_kb(),
    #         parse_mode="Markdown"
    #     )
    # else:
    #     await update.message.reply_text(
    #         "برای استفاده از ربات ابتدا در کانال رسمی رستوران پسران کریم عضو شوید."
    #         "پس از عضویت دکمه بررسی عضویت را بزنید.",
    #         reply_markup = membership_kb(),
    #         parse_mode="Markdown"
    #     )

    await update.message.reply_text(
        f"✅ سلام {user_name} عزیز!\n\n"
        "به ربات رستوران **پسران کریم** خوش آمدید.\n\n"
        "📍 لطفاً شعبه مورد نظر خود را انتخاب کنید 👇",
        reply_markup=branch_kb(),
        parse_mode="Markdown"
    )

# async def check_callback(update,context):
#     query = update.callback_query
#     await query.answer()

#     user_id = query.from_user.id
#     user_name = query.from_user.first_name or "کاربر گرامی"

#     if await real_member(context,user_id):
#         await query.edit_message_text(
#             "عضویت شما تایید شد✅"
#             "سلام به ربات رستوران پسران کریم خوش آمدید."
#             "لطفا شعبه مورد نظر خود را انتخاب کنید:",
#             reply_markup=branch_kb(),
#             parse_mode="Markdown"
#         )
#     else:
#         await query.answer("شما هنوز عضو کانال نشدید.لطفا ابتدا عضو شوید!",show_alert=True)

async def handle_branch_selection(update,context):
    text = update.message.text
    if text == "شعبه مشهد (خیام)":
        branch = "mashhad"
        branch_name = "مشهد (خیام)"
    elif text == "شعبه تهران":
        branch = "tehran"
        branch_name = "تهران"
    else:
        await update.message.reply_text(
            "لطفا یمی از گزینه های زیر را انتخاب کنید:",
            reply_markup=branch_kb()
        )
        return
    context.user_data["branch"] = branch

    await update.message.reply_text(
        f"شعبه {branch_name} انتخاب شد✅\n"
        "میتوانید از قابلیت های ربات استفاده کنید.",
        parse_mode="Markdown"
    )

# async def branch_callback(update, context):
#     query = update.callback_query
#     await query.answer()
#     branch = query.data.split('_')[1]
#     context.user_data['branch'] = branch
#     branch_name = "مشهد (خیام)" if branch == "mashhad" else "tehran"

#     await query.edit_message_text(
#         f"شعبه {branch_name} انتخاب شد✅"
#         "میتوانید از قابلیت های ربات استفاده کنید.",
#         # reply_markup=main_menu_kb(),
#         parse_mode="Markdown"
#     )

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    # app.add_handler(CallbackQueryHandler(check_callback, pattern="check"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_branch_selection))

    print("BOT IS UP...")
    app.run_polling()

if __name__=="__main__":
    main()

    
            