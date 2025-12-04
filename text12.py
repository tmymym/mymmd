import time
import random
import threading
import requests
import telebot
import logging
import os
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from concurrent.futures import ThreadPoolExecutor

# تنظیمات لاگ‌گیری
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bot.log')
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# تنظیمات ربات - توکن شما
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = "https://my.irancell.ir/api/gift/v1/refer_a_friend"
PREFIXES = ["0905", "0901", "0933", "0903"]

# وضعیت ربات
state = {
    "running": False,
    "success": 0,
    "fail": 0,
    "token": "",
    "cookie": "",
    "concurrency": 50,  # پیش‌فرض 50
    "max_concurrency": 200,  # حداکثر 200
    "invite_limit": 0,  # حد دعوت موفق
    "prefix_stats": {p: {"success": 1, "fail": 1} for p in PREFIXES},
    "fail_streak": 0,
    "results": [],
    "executor": None,
    "semaphore": None,
    "start_time": 0
}

logging.info("🤖 در حال ایجاد ربات پرسرعت...")

try:
    bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
    logging.info("✅ ربات ایجاد شد")
except Exception as e:
    logging.error(f"❌ خطا در ایجاد ربات: {e}")
    exit()

# ایجاد صفحه کلید پیشرفته
def create_keyboard():
    keyboard = ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    keyboard.row('🚀 شروع', '⏹ توقف', '📊 وضعیت')
    keyboard.row('⚡ سرعت', '🎯 حد دعوت', '⚙️ تنظیمات')
    keyboard.row('📈 آمار پیشرفته', '❓ راهنما')
    return keyboard

def create_speed_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("🚀 50", callback_data="speed_50"),
        InlineKeyboardButton("💨 100", callback_data="speed_100"),
        InlineKeyboardButton("🔥 200", callback_data="speed_200")
    )
    keyboard.row(
        InlineKeyboardButton("⚡ 30", callback_data="speed_30"),
        InlineKeyboardButton("📶 10", callback_data="speed_10"),
        InlineKeyboardButton("🐢 5", callback_data="speed_5")
    )
    return keyboard

def create_limit_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("🎯 1000", callback_data="limit_1000"),
        InlineKeyboardButton("🎯 5000", callback_data="limit_5000"),
        InlineKeyboardButton("∞ نامحدود", callback_data="limit_0")
    )
    keyboard.row(
        InlineKeyboardButton("🎯 10000", callback_data="limit_10000"),
        InlineKeyboardButton("🎯 20000", callback_data="limit_20000"),
        InlineKeyboardButton("✏️ سفارشی", callback_data="limit_custom")
    )
    return keyboard

def choose_prefix():
    total_weight = sum(state["prefix_stats"][p]["success"] / (state["prefix_stats"][p]["fail"] + 1) for p in PREFIXES)
    r = random.uniform(0, total_weight)
    upto = 0
    for p in PREFIXES:
        weight = state["prefix_stats"][p]["success"] / (state["prefix_stats"][p]["fail"] + 1)
        if upto + weight >= r:
            return p
        upto += weight
    return random.choice(PREFIXES)

def generate_number():
    p = choose_prefix()
    return p + "".join(str(random.randint(0, 9)) for _ in range(7))

def send_irancell_request(number):
    """ارسال درخواست به API ایرانسل - نسخه پرسرعت"""
    try:
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "fa",
            "authorization": state["token"],
            "content-type": "application/json",
            "cookie": state["cookie"],
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        payload = {
            "application_name": "NGMI", 
            "friend_number": "98" + number[1:]
        }
        
        response = requests.post(API_URL, json=payload, headers=headers, timeout=10, verify=False)
        prefix = number[:4]
        
        if response.status_code == 200:
            state["success"] += 1
            state["prefix_stats"][prefix]["success"] += 1
            state["fail_streak"] = 0
            result_msg = f"{number} ✅"
            state["results"].append(result_msg)
            if len(state["results"]) > 20:
                state["results"].pop(0)
            logging.info(f"✅ موفق: {number}")
            return True
        else:
            state["fail"] += 1
            state["prefix_stats"][prefix]["fail"] += 1
            state["fail_streak"] += 1
            result_msg = f"{number} ❌{response.status_code}"
            state["results"].append(result_msg)
            if len(state["results"]) > 20:
                state["results"].pop(0)
            logging.warning(f"❌ خطا {response.status_code}: {number}")
            return False
            
    except Exception as e:
        state["fail"] += 1
        state["fail_streak"] += 1
        result_msg = f"{number} ❌NET"
        state["results"].append(result_msg)
        if len(state["results"]) > 20:
            state["results"].pop(0)
        logging.error(f"❌ خطای شبکه: {number} - {e}")
        return False

def worker_task(number):
    """وظیفه هر worker برای ارسال درخواست"""
    if state["running"]:
        send_irancell_request(number)
        state["semaphore"].release()

def worker_controller():
    """کنترلر اصلی برای مدیریت workerها"""
    logging.info("🚀 کنترلر کارگرها شروع به کار کرد...")
    
    # ایجاد ThreadPoolExecutor برای مدیریت همزمانی
    state["executor"] = ThreadPoolExecutor(max_workers=state["max_concurrency"])
    state["semaphore"] = threading.Semaphore(state["concurrency"])
    state["start_time"] = time.time()
    
    while state["running"]:
        try:
            # بررسی حد دعوت
            if state["invite_limit"] > 0 and state["success"] >= state["invite_limit"]:
                logging.info("🎯 حد دعوت رسیده، توقف خودکار")
                state["running"] = False
                break
                
            if state["fail_streak"] >= 100:
                logging.warning("⛔ توقف خودکار به دلیل 100 خطای متوالی")
                state["running"] = False
                break
                
            # دریافت مجوز برای اجرای کارگر جدید
            acquired = state["semaphore"].acquire(blocking=False)
            if not acquired:
                time.sleep(0.001)  # کاهش تاخیر برای سرعت بیشتر
                continue
                
            # تولید شماره و ارسال درخواست
            number = generate_number()
            state["executor"].submit(worker_task, number)
            
        except Exception as e:
            logging.error(f"خطا در کنترلر: {e}")
            time.sleep(0.1)

@bot.message_handler(commands=['start'])
def start_command(message):
    """دستور شروع"""
    try:
        if state["running"]:
            bot.send_message(message.chat.id, 
                "⚠️ ربات از قبل در حال اجراست!",
                reply_markup=create_keyboard())
            return
        
        if not state["token"] or not state["cookie"]:
            bot.send_message(message.chat.id, 
                "❌ ابتدا توکن و کوکی را تنظیم کنید!\n"
                "از دکمه '⚙️ تنظیمات' استفاده کنید.",
                reply_markup=create_keyboard())
            return
        
        state["running"] = True
        state["success"] = 0
        state["fail"] = 0
        state["fail_streak"] = 0
        state["results"] = []
        
        # شروع thread کنترلر
        controller_thread = threading.Thread(target=worker_controller, daemon=True)
        controller_thread.start()
        
        limit_text = f"🎯 حد دعوت: {state['invite_limit']}" if state["invite_limit"] > 0 else "🎯 حد دعوت: نامحدود"
        
        bot.send_message(message.chat.id,
            f"🚀 ربات با سرعت بالا شروع به کار کرد!\n"
            f"⚡ همزمانی: {state['concurrency']} درخواست\n"
            f"{limit_text}\n\n"
            "📡 در حال ارسال درخواست به ایرانسل...",
            reply_markup=create_keyboard())
            
        logging.info("🚀 ربات شروع به کار کرد")
            
    except Exception as e:
        logging.error(f"خطا در دستور start: {e}")

@bot.message_handler(commands=['stop'])
def stop_command(message):
    """دستور توقف"""
    try:
        if not state["running"]:
            bot.send_message(message.chat.id, 
                "⚠️ ربات در حال اجرا نیست!",
                reply_markup=create_keyboard())
            return
        
        state["running"] = False
        if state["executor"]:
            state["executor"].shutdown(wait=False)
        
        bot.send_message(message.chat.id,
            "⏹ ربات متوقف شد!\n\n"
            "برای مشاهده آمار از '📊 وضعیت' استفاده کنید.",
            reply_markup=create_keyboard())
            
        logging.info("⏹ ربات متوقف شد")
            
    except Exception as e:
        logging.error(f"خطا در دستور stop: {e}")

@bot.message_handler(commands=['speed'])
def speed_command(message):
    """تنظیم سرعت"""
    try:
        bot.send_message(message.chat.id,
            "⚡ انتخاب سرعت ارسال:\n\n"
            "🚀 50 - سرعت بالا\n"
            "💨 100 - سرعت بسیار بالا\n"
            "🔥 200 - حداکثر سرعت\n\n"
            "برای انتخاب یکی از گزینه‌ها را فشار دهید:",
            reply_markup=create_speed_keyboard())
            
    except Exception as e:
        logging.error(f"خطا در دستور speed: {e}")

@bot.message_handler(commands=['limit'])
def limit_command(message):
    """تنظیم حد دعوت"""
    try:
        bot.send_message(message.chat.id,
            "🎯 تنظیم حد دعوت موفق:\n\n"
            "پس از رسیدن به این عدد، ربات به طور خودکار متوقف می‌شود.\n\n"
            "برای انتخاب یکی از گزینه‌ها را فشار دهید:",
            reply_markup=create_limit_keyboard())
            
    except Exception as e:
        logging.error(f"خطا در دستور limit: {e}")

@bot.message_handler(commands=['status'])
def status_command(message):
    """نمایش وضعیت"""
    try:
        status_text = "🟢 در حال اجرا" if state["running"] else "🔴 متوقف شده"
        
        # محاسبه آمار پیشرفته
        elapsed = time.time() - state.get("start_time", time.time())
        total_requests = state["success"] + state["fail"]
        
        if elapsed > 0 and total_requests > 0:
            requests_per_minute = int(total_requests / elapsed * 60)
            success_rate = int((state["success"] / total_requests) * 100) if total_requests > 0 else 0
            remaining_time = ""
            
            if state["invite_limit"] > 0 and state["success"] > 0:
                remaining = max(0, state["invite_limit"] - state["success"])
                if requests_per_minute > 0:
                    minutes_left = remaining / (requests_per_minute / 60)
                    hours, minutes = divmod(minutes_left, 60)
                    if hours > 0:
                        remaining_time = f"\n⏳ زمان باقی‌مانده: {int(hours)}h {int(minutes)}m"
                    else:
                        remaining_time = f"\n⏳ زمان باقی‌مانده: {int(minutes)}m"
        else:
            requests_per_minute = 0
            success_rate = 0
            remaining_time = ""
        
        limit_text = f"🎯 حد دعوت: {state['invite_limit']}" if state["invite_limit"] > 0 else "🎯 حد دعوت: نامحدود"
        
        # ایجاد متن وضعیت با فرمت زیبا
        message_text = (
            f"<b>📊 وضعیت ربات</b>\n\n"
            f"<b>{status_text}</b>\n"
            f"⚡ سرعت: <code>{state['concurrency']}</code> درخواست/ثانیه\n"
            f"{limit_text}{remaining_time}\n\n"
            f"<b>📈 آمار عملکرد:</b>\n"
            f"✅ موفق: <code>{state['success']}</code>\n"
            f"❌ ناموفق: <code>{state['fail']}</code>\n"
            f"📊 مجموع: <code>{total_requests}</code>\n"
            f"🎯 نرخ موفقیت: <code>{success_rate}%</code>\n"
            f"🚀 سرعت: <code>{requests_per_minute}</code> درخواست/دقیقه\n\n"
            f"<b>🔧 تنظیمات:</b>\n"
            f"🔑 توکن: {'✅' if state['token'] else '❌'}\n"
            f"🍪 کوکی: {'✅' if state['cookie'] else '❌'}\n\n"
            f"<b>📋 آخرین نتایج:</b>\n"
        )
        
        # اضافه کردن آخرین نتایج
        recent_results = state["results"][-5:] if state["results"] else ["📭 هنوز نتیجه‌ای موجود نیست"]
        for result in recent_results:
            message_text += f"• {result}\n"
            
        bot.send_message(message.chat.id, message_text, 
                        parse_mode='HTML',
                        reply_markup=create_keyboard())
        
    except Exception as e:
        logging.error(f"خطا در دستور status: {e}")

@bot.message_handler(commands=['settings'])
def settings_command(message):
    """تنظیمات"""
    try:
        help_text = (
            "⚙️ <b>تنظیمات ربات ایرانسل</b>\n\n"
            "برای تنظیم توکن و کوکی، پیام خود را به صورت زیر ارسال کنید:\n\n"
            "<code>توکن: YOUR_TOKEN_HERE</code>\n"
            "<code>کوکی: YOUR_COOKIE_HERE</code>\n\n"
            "📝 <b>مثال:</b>\n"
            "<code>توکن: Bearer abc123xyz...</code>\n"
            "<code>کوکی: session=abcdef123456...</code>\n\n"
            "⚠️ توجه: ابتدا تنظیمات را انجام دهید، سپس ربات را شروع کنید."
        )
        bot.send_message(message.chat.id, help_text, 
                        parse_mode='HTML',
                        reply_markup=create_keyboard())
        
    except Exception as e:
        logging.error(f"خطا در دستور settings: {e}")

@bot.message_handler(commands=['help'])
def help_command(message):
    """راهنما"""
    try:
        help_text = (
            "🤖 <b>راهنمای ربات ایرانسل پرسرعت</b>\n\n"
            "🚀 <b>دستورات اصلی:</b>\n"
            "/start - شروع ارسال دعوت‌نامه\n"
            "/stop - توقف ارسال\n"
            "/status - نمایش وضعیت و آمار\n\n"
            "⚡ <b>تنظیمات سرعت:</b>\n"
            "/speed - تنظیم سرعت (تا 200 درخواست همزمان)\n\n"
            "🎯 <b>تنظیمات حد:</b>\n"
            "/limit - تنظیم حد دعوت موفق\n\n"
            "⚙️ <b>سایر دستورات:</b>\n"
            "/settings - راهنمای تنظیمات\n"
            "/help - نمایش این راهنما\n\n"
            "🔥 <b>ویژگی‌های ویژه:</b>\n"
            "• حداکثر سرعت: 200 درخواست همزمان\n"
            "• حد دعوت قابل تنظیم\n"
            "• آمار پیشرفته زنده\n"
            "• توقف خودکار در صورت رسیدن به حد"
        )
        bot.send_message(message.chat.id, help_text, 
                        parse_mode='HTML',
                        reply_markup=create_keyboard())
        
    except Exception as e:
        logging.error(f"خطا در دستور help: {e}")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """مدیریت callback های اینلاین"""
    try:
        if call.data.startswith('speed_'):
            speed_value = call.data.split('_')[1]
            if speed_value.isdigit():
                new_speed = int(speed_value)
                if 1 <= new_speed <= state["max_concurrency"]:
                    state["concurrency"] = new_speed
                    bot.answer_callback_query(call.id, f"✅ سرعت به {new_speed} تنظیم شد!")
                    bot.edit_message_text("⚡ سرعت ارسال به روز شد!",
                                        call.message.chat.id,
                                        call.message.message_id)
                    logging.info(f"⚡ سرعت به {new_speed} تنظیم شد")
                else:
                    bot.answer_callback_query(call.id, "❌ سرعت خارج از محدوده مجاز!")
            else:
                bot.answer_callback_query(call.id, "❌ مقدار نامعتبر!")
                
        elif call.data.startswith('limit_'):
            limit_value = call.data.split('_')[1]
            if limit_value.isdigit():
                new_limit = int(limit_value)
                state["invite_limit"] = new_limit
                bot.answer_callback_query(call.id, f"✅ حد دعوت به {new_limit} تنظیم شد!")
                bot.edit_message_text(f"🎯 حد دعوت به {new_limit} تنظیم شد!",
                                    call.message.chat.id,
                                    call.message.message_id)
                logging.info(f"🎯 حد دعوت به {new_limit} تنظیم شد")
            elif limit_value == 'custom':
                bot.answer_callback_query(call.id, "✏️ لطفاً عدد مورد نظر را وارد کنید:")
                bot.send_message(call.message.chat.id, 
                                "✏️ لطفاً حد دعوت مورد نظر را وارد کنید:\n\n"
                                "مثال: 15000")
            elif limit_value == '0':
                state["invite_limit"] = 0
                bot.answer_callback_query(call.id, "✅ حد دعوت نامحدود شد!")
                bot.edit_message_text("🎯 حد دعوت نامحدود شد!",
                                    call.message.chat.id,
                                    call.message.message_id)
                logging.info("🎯 حد دعوت نامحدود شد")
                
    except Exception as e:
        logging.error(f"خطا در callback: {e}")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """پردازش تمام پیام‌ها"""
    try:
        text = message.text.strip()
        
        if text == '🚀 شروع':
            start_command(message)
            
        elif text == '⏹ توقف':
            stop_command(message)
            
        elif text == '📊 وضعیت':
            status_command(message)
            
        elif text == '⚡ سرعت':
            speed_command(message)
            
        elif text == '🎯 حد دعوت':
            limit_command(message)
            
        elif text == '⚙️ تنظیمات':
            settings_command(message)
            
        elif text == '📈 آمار پیشرفته':
            status_command(message)
            
        elif text == '❓ راهنما':
            help_command(message)
            
        elif text.startswith('توکن:'):
            token = text.replace('توکن:', '').strip()
            state["token"] = token
            bot.send_message(message.chat.id, 
                            "✅ توکن ذخیره شد!",
                            reply_markup=create_keyboard())
            logging.info("✅ توکن ذخیره شد")
            
        elif text.startswith('کوکی:'):
            cookie = text.replace('کوکی:', '').strip()
            state["cookie"] = cookie
            bot.send_message(message.chat.id, 
                            "✅ کوکی ذخیره شد!",
                            reply_markup=create_keyboard())
            logging.info("✅ کوکی ذخیره شد")
            
        elif text.isdigit() and int(text) > 0:
            # اگر عدد وارد شده، احتمالاً برای حد دعوت است
            custom_limit = int(text)
            if 1 <= custom_limit <= 100000:
                state["invite_limit"] = custom_limit
                bot.send_message(message.chat.id,
                                f"🎯 حد دعوت به {custom_limit} تنظیم شد!",
                                reply_markup=create_keyboard())
                logging.info(f"🎯 حد دعوت به {custom_limit} تنظیم شد")
            else:
                bot.send_message(message.chat.id,
                                "❌ حد دعوت باید بین 1 تا 100,000 باشد!",
                                reply_markup=create_keyboard())
                
        else:
            bot.send_message(message.chat.id,
                "❌ دستور نامعتبر!\n\n"
                "از دکمه‌های زیر استفاده کنید:",
                reply_markup=create_keyboard())
                
    except Exception as e:
        logging.error(f"خطا در پردازش پیام: {e}")

def main():
    """تابع اصلی برای اجرای مستقل"""
    logging.info("🤖 ربات ایرانسل پرسرعت در حال راه اندازی...")
    logging.info(f"✅ توکن: {BOT_TOKEN}")
    logging.info(f"⚡ حداکثر سرعت: {state['max_concurrency']} درخواست همزمان")
    logging.info("🎯 سیستم حد دعوت: فعال")
    logging.info("📞 منتظر پیام‌ها هستیم...")
    
    try:
        logging.info("🔗 تست اتصال به تلگرام...")
        bot_info = bot.get_me()
        logging.info(f"✅ اتصال به تلگرام OK - ربات: {bot_info.first_name}")
        
        # شروع ربات
        logging.info("🔄 شروع polling...")
        bot.polling(none_stop=True, interval=1, timeout=30)
        
    except Exception as e:
        logging.error(f"❌ خطا در اتصال به تلگرام: {e}")
        print(f"خطا: {e}")

# این دو خط را در انتهای فایل اضافه کنید
if __name__ == "__main__":
    main()