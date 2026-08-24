from telegram import Update,InlineKeyboardButton,InlineKeyboardMarkup,ReplyKeyboardMarkup,KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler,MessageHandler,filters,ContextTypes

TOKEN = "8779458070:AAH8kDG-iBv1XvDWQ-3kUqcHI2meZqB8yY8"
CHANNEL_USERNAME = "@pesaranekarim"
CHANNEL_ID = "-1001586571412"

def make_keyboard(buttons, row_width=2):
    return InlineKeyboardMarkup(
        [buttons[i:i+row_width] for i in range(0, len(buttons), row_width)]
    )

async def real_member(context,user_id):
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID,user_id)
        print(f"🔍 وضعیت کاربر: {member.status}")
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"❌ خطا در بررسی عضویت: {e}")
        return False


BTN_JOIN = InlineKeyboardButton("عضویت در کانال",url="https://t.me/pesaranekarim")
BTN_CHECK = InlineKeyboardButton("بررسی عضویت",callback_data="check")

BTN_MASHHAD = KeyboardButton("شعبه مشهد (خیام)")
BTN_TEHRAN = KeyboardButton("شعبه تهران")

BTN_PHOTO = KeyboardButton("دریافت عکس یادگاری")
BTN_APP = KeyboardButton("اپلیکیشن پسران کریم (اندروید)")
BTN_MENU = KeyboardButton("منوی دو زبانه")
BTN_FULL_MENU = KeyboardButton("منو کامل رستوران")
BTN_ORDER = KeyboardButton("سفارش آنلاین و رزرو مجالس")
BTN_PHONE_ORDER = KeyboardButton("سفارش تلفنی و رزرو مجالس")
BTN_LOCATION = KeyboardButton("مسیریابی به ما")
BTN_ADDRESS = KeyboardButton("آدرس ما")
BTN_SOCIAL = KeyboardButton("شبکه های اجتماعی")
BTN_HISTORY = KeyboardButton("تاریخچه ما")

def membership_kb():
    return make_keyboard([BTN_JOIN,BTN_CHECK], row_width=1)

def branch_kb():
    return ReplyKeyboardMarkup(
        [[BTN_MASHHAD, BTN_TEHRAN]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def main_menu_kb(branch):
    if branch == "mashhad":
        keyboard = [
            [BTN_PHOTO, BTN_APP],           # ۲ تا
            [BTN_MENU, BTN_FULL_MENU],       # ۲ تا
            [BTN_ORDER, BTN_PHONE_ORDER],    # ۲ تا
            [BTN_LOCATION, BTN_ADDRESS],     # ۲ تا
            [BTN_SOCIAL, BTN_HISTORY]        # ۲ تا
        ]
    else:
        keyboard = [
            [BTN_PHOTO],
            [BTN_MENU, BTN_FULL_MENU],
            [BTN_ORDER, BTN_PHONE_ORDER],
            [BTN_LOCATION, BTN_ADDRESS],
            [BTN_SOCIAL, BTN_HISTORY]
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update,context):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "کاربر گرامی"

    if await real_member(context,user_id):
        await update.message.reply_text(
            f"✅ سلام {user_name} عزیز!\n\n"
            "به ربات رستوران **پسران کریم** خوش آمدید.\n\n"
            "📍 لطفاً شعبه مورد نظر خود را انتخاب کنید 👇",
            reply_markup=branch_kb(),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "❌ برای استفاده از ربات، ابتدا در کانال رسمی **رستوران پسران کریم** عضو شوید.\n\n"
            "✅ پس از عضویت، دکمه‌ی **بررسی عضویت** را بزنید.",
            reply_markup = membership_kb(),
            parse_mode="Markdown"
        )

    await update.message.reply_text(
        f"✅ سلام {user_name} عزیز!\n\n"
        "به ربات رستوران **پسران کریم** خوش آمدید.\n\n"
        "📍 لطفاً شعبه مورد نظر خود را انتخاب کنید 👇",
        reply_markup=branch_kb(),
        parse_mode="Markdown"
    )

async def check_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_name = query.from_user.first_name or "کاربر گرامی"

    if await real_member(context,user_id):
        await query.delete_message()

        await context.bot.send_message(
            chat_id = user_id,
            text=f"عضویت شما تایید شد✅\n\n"
            f"سلام {user_name} عزیز!\n"
            "به ربات رستوران پسران کریم خوش آمدید.\n\n"
            "لطفا شعبه مورد نظر خود را انتخاب کنید👇",
            reply_markup =branch_kb(),
            parse_mode="Markdown"
        )
    else:
        await query.answer("شما هنوز عضو کانال نشدید❌ لطفا ابتدا عضو شوید.",show_alert=True)



async def handle_all_messages(update, context):
    user_id = update.effective_user.id 
    text = update.message.text

    if not await real_member(context, user_id):
        await update.message.reply_text(
            "❌ شما از کانال خارج شدید!\n\n"
            "برای استفاده مجدد از ربات، لطفاً در کانال رسمی **رستوران پسران کریم** عضو شوید.\n\n"
            "✅ پس از عضویت، دوباره روی دکمه‌ی **بررسی عضویت** بزنید.",
            reply_markup=membership_kb(),
            parse_mode="Markdown"
        )
        return


    if text == "شعبه مشهد (خیام)":
        context.user_data['branch'] = "mashhad"
        await update.message.reply_text(
            "✅ شعبه **مشهد (خیام)** انتخاب شد.\n\n"
            "📱 لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=main_menu_kb("mashhad"),
            parse_mode="Markdown"
        )
        return
    
    elif text == "شعبه تهران":
        context.user_data['branch'] = "tehran"
        await update.message.reply_text(
            "✅ شعبه **تهران** انتخاب شد.\n\n"
            "📱 لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=main_menu_kb("tehran"),
            parse_mode="Markdown"
        )
        return

    branch = context.user_data.get('branch', 'mashhad')

    if text == "📸 دریافت عکس یادگاری":
        await update.message.reply_text(
            "📸 لطفاً شماره موبایل و کد عکس خود را وارد کنید.\n\n"
            "🔹 شماره موبایل:\n"
            "🔹 کد عکس:",
            parse_mode="Markdown"
        )    
    elif text == "اپلیکیشن پسران کریم (اندروید)":
        if branch == "mashhad":
            await update.message.reply_text(
                "fasfassfa",
                parse_mode="Markdown"
            )

    elif text == "منوی دو زبانه":
        await update.message.reply_text(
            "منوی دو زبانه به همراه قیمت👇\n\n"
            "https://www.pesaranekarim.rest/menu2",
            parse_mode="Markdown"
        )

    elif text == "منو کامل رستوران":
        await update.message.reply_text(
            "منو به همراه تصاویر و توضیحات\n\n"
            "https://www.pesaranekarim.rest/menu",
            parse_mode="Markdown"
        )

    elif text == "سفارش آنلاین و رزرو مجالس":
        await update.message.reply_text(
            "جهت سفارش آنلاین می توانید به آیدی زیر پیام بدهید:\n\n"
            "@PesaranekarimDelivery"
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

    app.add_handler(CallbackQueryHandler(check_callback, pattern="check"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages))

    print("BOT IS UP...")
    app.run_polling()

if __name__=="__main__":
    main()

    
            