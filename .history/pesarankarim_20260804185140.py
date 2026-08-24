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

BTN_MASHHAD = KeyboardButton("شعبه مشهد(خیام)")
BTN_TEHRAN = KeyboardButton("شعبه تهران(هتل پارسیان آزادی)")

BTN_MASHHAD_PHOTO = KeyboardButton("دریافت عکس یادگاری")
BTN_MASHHAD_APP = KeyboardButton("اپلیکیشن پسران کریم")
BTN_MASHHAD_MENU = KeyboardButton("منو به همراه قیمت")
BTN_MASHHAD_FULL_MENU = KeyboardButton("منو به همراه تصویر")
BTN_MASHHAD_ORDER = KeyboardButton("سفارش آنلاین")
BTN_MASHHAD_PHONE_ORDER = KeyboardButton("سفارش تلفنی و رزرو مجالس")
BTN_MASHHAD_LOCATION = KeyboardButton("مسیریابی(لوکیشن)")
BTN_MASHHAD_ADDRESS = KeyboardButton("آدرس ما")
BTN_MASHHAD_SOCIAL = KeyboardButton("شبکه های اجتماعی ما")
BTN_MASHHAD_HISTORY = KeyboardButton("تاریخچه پسران کریم")
BTN_CHANGE_BRANCH = KeyboardButton("تغییر شعبه")

BTN_TEHRAN_PHOTO = KeyboardButton("دریافت عکس یادگاری")
BTN_TEHRAN_APP = KeyboardButton("اپلیکیشن پسران کریم")
BTN_TEHRAN_MENU = KeyboardButton("منو به همراه قیمت")
BTN_TEHRAN_FULL_MENU = KeyboardButton("منو به همراه تصویر")
BTN_TEHRAN_ORDER = KeyboardButton("سفارش آنلاین")
BTN_TEHRAN_PHONE_ORDER = KeyboardButton("سفارش تلفنی و رزرو مجالس")
BTN_TEHRAN_LOCATION = KeyboardButton("مسیریابی(لوکیشن)")
BTN_TEHRAN_ADDRESS = KeyboardButton("آدرس ما")
BTN_TEHRAN_SOCIAL = KeyboardButton("شبکه های اجتماعی ما")
BTN_TEHRAN_HISTORY = KeyboardButton("تاریخچه پسران کریم")
BTN_CHANGE_BRANCH = KeyboardButton("تغییر شعبه")

def membership_kb():
    return make_keyboard([BTN_JOIN,BTN_CHECK], row_width=1)

def branch_kb():
    return ReplyKeyboardMarkup(
        [[BTN_MASHHAD, BTN_TEHRAN]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def mashhad_menu_kb():
    keyboard = [
        [BTN_MASHHAD_PHOTO],
        [BTN_MASHHAD_APP],
        [BTN_MASHHAD_MENU, BTN_MASHHAD_FULL_MENU],
        [BTN_MASHHAD_ORDER, BTN_MASHHAD_PHONE_ORDER],
        [BTN_MASHHAD_LOCATION, BTN_MASHHAD_ADDRESS],
        [BTN_MASHHAD_SOCIAL, BTN_MASHHAD_HISTORY],
        [BTN_CHANGE_BRANCH]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def tehran_menu_kb():
    keyboard = [
        [BTN_TEHRAN_PHOTO],
        [BTN_MASHHAD_APP],
        [BTN_TEHRAN_MENU, BTN_TEHRAN_FULL_MENU],
        [BTN_TEHRAN_ORDER, BTN_TEHRAN_PHONE_ORDER],
        [BTN_TEHRAN_LOCATION, BTN_TEHRAN_ADDRESS],
        [BTN_TEHRAN_SOCIAL, BTN_TEHRAN_HISTORY],
        [BTN_CHANGE_BRANCH]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update,context):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "کاربر گرامی"

    if await real_member(context,user_id):
        msg = await update.message.reply_text(
            f"سلام {user_name} عزیز!\n\n"
            "به ربات رستوران پسران کریم خوش آمدید🌹\n\n"
            "لطفا شعبه مورد نظر خود را انتخاب کنید 👇",
            reply_markup=branch_kb(),
            parse_mode="Markdown"
        )
        context.user_data["start_message_id"] = msg.message_id
    else:
        msg = await update.message.reply_text(
            f"سلام {user_name} عزیز!\n\n"
            "به ربات پسران کریم خوش آمدید🌹\n\n"
            "برای استفاده از ربات، ابتدا در کانال رسمی رستوران پسران کریم عضو شوید🙏\n\n"
            "پس از عضویت، دکمه‌ی بررسی عضویت را بزنید.",
            reply_markup = membership_kb(),
            parse_mode="Markdown"
        )
        context.user_data["start_message_id"] = msg.message_id

    # await update.message.reply_text(
    #     f"سلام {user_name} عزیز!\n\n"
    #     "به ربات رستوران پسران کریم خوش آمدید.\n\n"
    #     "📍 لطفا شعبه مورد نظر خود را انتخاب کنید 👇",
    #     reply_markup=branch_kb(),
    #     parse_mode="Markdown"
    # )

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
            try:
                if "start_message_id" in context.user_data:
                    await context.bot.delete_message(
                        chat_id=user_id,
                        message_id=context.user_data["start_message_id"]
                    )
            except:
                pass

            msg = await update.message.reply_text(        
            "❌ شما از کانال خارج شدید!\n\n"
            "برای استفاده مجدد از ربات، لطفا در کانال رسمی رستوران پسران کریم عضو شوید.\n\n"
            "پس از عضویت، دوباره روی دکمه‌ی بررسی عضویت کلیک کنید..",
            reply_markup=membership_kb(),
            parse_mode="Markdown"
        )
            context.user_data["start_message_id"] = msg.message_id
            return


    if text == "شعبه مشهد(خیام)":
        context.user_data['branch'] = "mashhad"
        await update.message.reply_text(
            "شعبه مشهد (خیام) انتخاب شد✅\n\n"
            "برای استفاده یکی از گزینه های زیر را انتخاب کنید👇:",
            reply_markup=mashhad_menu_kb(),
            parse_mode="Markdown"
        )
        return
    
    elif text == "شعبه تهران(هتل پارسیان آزادی)":
        context.user_data['branch'] = "tehran"
        await update.message.reply_text(
            "شعبه تهران (هتل پارسیان آزادی) انتخاب شد✅\n\n"
            "برای استفاده یکی از گزینه های زیر را انتخاب کنید👇",
            reply_markup=tehran_menu_kb(),
            parse_mode="Markdown"
        )
        return
    elif text == "تغییر شعبه":
        context.user_data['branch'] = None
        await update.message.reply_text(
            "لطفا شعبه مورد نظر خود را انتخاب کنید👇",
            reply_markup=branch_kb(),
            parse_mode="Markdown"
        )
        return

    branch = context.user_data.get('branch', 'mashhad')

    if branch == "mashhad":
        if text == "📸 دریافت عکس یادگاری":
            await update.message.reply_text(
                "📸 لطفاً شماره موبایل و کد عکس خود را وارد کنید.\n\n"
                "🔹 شماره موبایل:\n"
                "🔹 کد عکس:",
                parse_mode = "Markdown"
            )    
        elif text == "اپلیکیشن پسران کریم":
            if branch == "mashhad":
                await update.message.reply_document(
                    document="https://t.me/pesaranekarim/55",
                    caption="اپلیکیشن رستوران پسران کریم، نسخه اندروید",
                    parse_mode = "Markdown"
                )

        elif text == "منو به همراه قیمت":
            await update.message.reply_text(
                "منوی دو زبانه به همراه قیمت👇\n\n"
                "https://www.pesaranekarim.rest/menu2",
                parse_mode = "Markdown"
            )

        elif text == "منو به همراه تصویر":
            await update.message.reply_text(
                "منو به همراه تصاویر و توضیحات\n\n"
                "https://www.pesaranekarim.rest/menu",
                parse_mode = "Markdown"
            )

        elif text == "سفارش آنلاین":
            await update.message.reply_text(
                "جهت سفارش آنلاین می توانید به آیدی زیر پیام بدهید:\n\n"
                "@PesaranekarimDelivery"
            )

        elif text == "سفارش تلفنی و رزرو مجالس":
            await update.message.reply_text(
                "تلفن های ما جهت سفارش و ارسال غذا و رزرو مجالس:\n\n"
                "00985131919000\n\n"
                "00985137530013\n\n"
                "00985137530014\n\n"
                "00985137530015",
                parse_mode = "Markdown"
            )

        elif text == "مسیریابی(لوکیشن)":
            if branch == "mashhad":
                await update.message.reply_text(
                    "🔸 مسیریاب گوگل مپ (Google Map):\n"
                    "https://goo.gl/maps/2uReg6JVGWT3kmXaA\n\n"
                    "🔸 مسیریاب وِیز (Waze):\n"
                    "https://waze.com/ul/htq6qezmz5\n\n"
                    "🔸 مسیریاب بلد (Balad):\n"
                    "https://balad.ir/p/6bfS2o3VBFNV0d\n\n"
                    "🔸 مسیریاب نشان (Neshan):\n"
                    "https://nshn.ir/b77b1ibkpJj8t4\n\n"
                    "🔸 مسیریاب اَپل (iOS/Apple):\n"
                    "https://oia.bio/applemap",
                    parse_mode = "Markdown"
                )

        elif text == "آدرس ما":
            if branch == "mashhad":
                await update.message.reply_photo(
                    photo = "https://t.me/pesaranekarim/10",
                    caption="مشهد، بلوار خیام به سمت الماس شرق، بعد از چهار راه هدایت، بین خیام ۶۱ و ۶۳، ساختمان مروارید.",
                    parse_mode = "Markdown"
                )

        elif text == "شبکه های اجتماعی ما":
            await update.message.reply_text(
                "🔍 **وبسایت رسمی ما:**\n"
                "www.pesaranekarim.rest\n\n"
                "📷 **اینستاگرام ما:**\n"
                "Instagram.com/pesaranekarim\n\n"
                "💬 **ایکس (توییتر سابق) ما:**\n"
                "twitter.com/pesaranekarim\n\n"
                "🅰️ **تردز ما:**\n"
                "threads.net/@pesaranekarim\n\n"
                "🎥 **تیکتاک ما:**\n"
                "tiktok.com/@pesaranekarim\n\n"
                "💬 **فیسبوک ما:**\n"
                "facebook.com/pesaranekarim.rest\n\n"
                "🔵 **لینکدین ما:**\n"
                "linkedin.com/company/pesaranekarim/\n\n"
                "💬 **کانال تلگرام ما:**\n"
                "@pesaranekarim\n\n"
                "💻 **ربات تلگرام ما:**\n"
                "@pesaranekarimbot\n\n"
                "✈️ **سفارش تلگرامی غذا:**\n"
                "@pesaranekarimdelivery\n\n"
                "🔴 **کانال آپارات ما:**\n"
                "aparat.com/pesaranekarim\n\n"
                "📺 **کانال یوتیوب ما:**\n"
                "youtube.com/@pesaranekarim",
                parse_mode="Markdown"
            )

        elif text == "تاریخچه پسران کریم":
            await update.message.reply_text(
                """⭐⭐تاریخچه رستوران پسران کریم⭐⭐

بنیانگذار این رستوران آقای کریم قاسم زاده حاتمی بوده است.

ایشان بيش از يک قرن است كه سبک جدیدی از غذا را در ایران پایه گذاری کرده اند.

غذاهای شیشلیک، ماهیچه، گوشت سرخ کرده، استامبولی پلو که تماما ابتکار خود ایشان بوده است و تا ۱۲ سال اولین و تنها محلی بوده است که در آن شیشلیک سرو می شده است و مشتریان، شیشلیک را فقط و فقط به نام کریم شیشلیکی میشناختند.

ایشان بازحمت بسیار، بهترین قطعات گوشت را از مناطق ییلاقی مشهد مانند شاندیز، طرقبه، زشک، ابرده، عنبران، جاغرق و... تهیه میکردند و به گفته مشتریان قدیمی یکه تاز عرصه کیفیت بوده اند.

نام نیکی که از ایشان به یادگار مانده اگر بی نظیر نباشد کم نظیر است و این به خاطر صداقت و برتری کیفیت و طعم ماندگار غذاهای ایشان بوده است.
کارگران ایشان همگی به رحمت خدا رفته اند و در حال حاضر شاگردان حقیقی ایشان دو فرزندشان میباشند که با همت خود تحت لوای نام رستوران پسران کریم نام پدر را زنده نگه داشته اند.

«در حال حاضر رستوران پسران کریم با سه شعبه خیام، فرهاد و آلتون در شهر مشهد فعالیت میکند و شعبه دیگری در دیگر نقاط ایران و جهان ندارد.»

«لازم به ذکر می‌باشد که برند پسران کریم ثبت قانونی شده است.»

هموطنان ارجمند لطفاً با پیشنهادات سازنده خود ما را در رشد روزافزون یاری فرمایید.""",
parse_mode = "Markdown"
            )

    else:
        if text == "📸 دریافت عکس یادگاری":
            await update.message.reply_text(
                "📸 لطفاً شماره موبایل و کد عکس خود را وارد کنید.\n\n"
                "🔹 شماره موبایل:\n"
                "🔹 کد عکس:",
                parse_mode="Markdown"                   
            )

        elif text == "اپلیکیشن پسران کریم":
            if branch == "tehran":
                await update.message.reply_document(
                document="https://t.me/pesaranekarim/55",
                caption="اپلیکیشن رستوران پسران کریم، نسخه اندروید",
                parse_mode = "Markdown"
            )

        elif text == "منو به همراه قیمت":
                await update.message.reply_text(
                "منوی دو زبانه به همراه قیمت👇\n\n"
                "https://www.pesaranekarim.rest/menu2",
                parse_mode = "Markdown"
            )

        elif text == "منو به همراه تصویر":
            await update.message.reply_text(
                "منو به همراه تصاویر و توضیحات\n\n"
                "https://www.pesaranekarim.rest/menu",
                parse_mode = "Markdown"
            )

        elif text == "سفارش آنلاین":
            await update.message.reply_text(
                "جهت سفارش آنلاین می توانید به آیدی زیر پیام بدهید:\n\n"
                "@PesaranekarimDelivery"
            )

        elif text == "سفارش تلفنی و رزرو مجالس":
            await update.message.reply_text(
                "تلفن های ما جهت سفارش و ارسال غذا و رزرو مجالس:\n\n"
                "00985131919000\n\n"
                "00985137530013\n\n"
                "00985137530014\n\n"
                "00985137530015",
                parse_mode = "Markdown"
            )

        elif text == "مسیریابی(لوکیشن)":
                    if branch == "tehran":
                        await update.message.reply_text(
                            "🔸 مسیریاب گوگل مپ (Google Map):\n"
                            "https://maps.app.goo.gl/VqjfcqXX6TnECLSY6\n\n"
                            "🔸 مسیریاب بلد (Balad):\n"
                            "https://balad.ir/p/2FnU2N9u64ujdN\n\n"
                            "🔸 مسیریاب نشان (Neshan):\n"
                            "https://nshn.ir/8c_bv8zuGxiAqs",
                            parse_mode = "Markdown"
                        )           

        elif text == "آدرس ما":
                if branch == "tehran":
                    await update.message.reply_text(
                    "تهران: تقاطع بزرگراه چمران و یادگار امام، هتل پارسیان آزادی، طبقه 26 ",
                    parse_mode = "Markdown"
                )

        elif text == "شبکه های اجتماعی ما":
            await update.message.reply_text(
                "🔍 **وبسایت رسمی ما:**\n"
                "www.pesaranekarim.rest\n\n"
                "📷 **اینستاگرام ما:**\n"
                "Instagram.com/pesaranekarim\n\n"
                "💬 **ایکس (توییتر سابق) ما:**\n"
                "twitter.com/pesaranekarim\n\n"
                "🅰️ **تردز ما:**\n"
                "threads.net/@pesaranekarim\n\n"
                "🎥 **تیکتاک ما:**\n"
                "tiktok.com/@pesaranekarim\n\n"
                "💬 **فیسبوک ما:**\n"
                "facebook.com/pesaranekarim.rest\n\n"
                "🔵 **لینکدین ما:**\n"
                "linkedin.com/company/pesaranekarim/\n\n"
                "💬 **کانال تلگرام ما:**\n"
                "@pesaranekarim\n\n"
                "💻 **ربات تلگرام ما:**\n"
                "@pesaranekarimbot\n\n"
                "✈️ **سفارش تلگرامی غذا:**\n"
                "@pesaranekarimdelivery\n\n"
                "🔴 **کانال آپارات ما:**\n"
                "aparat.com/pesaranekarim\n\n"
                "📺 **کانال یوتیوب ما:**\n"
                "youtube.com/@pesaranekarim",
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

    app.add_handler(CallbackQueryHandler(check_callback, pattern="check"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages))

    print("BOT IS UP...")
    app.run_polling()

if __name__=="__main__":
    main()

    
            