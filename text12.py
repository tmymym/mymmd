import time
import random
import threading
import requests
import telebot
import logging
import os
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from concurrent.futures import ThreadPoolExecutor

# ===============================
#   دریافت توکن از محیط سیستم
# ===============================
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    print("❌ BOT_TOKEN تنظیم نشده است! لطفاً در سرور مقدار BOT_TOKEN را ست کنید.")
    print("مثال:")
    print('export BOT_TOKEN="123456:ABCDEF"')
    exit(1)

# ===============================
#   تنظیمات ثابت
# ===============================
API_URL = "https://my.irancell.ir/api/gift/v1/refer_a_friend"
PREFIXES = ["0905", "0901", "0933", "0903"]

# لیست User-Agent های مختلف برای ضدبلاک (گزینه ۳)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Mozilla/5.0 (X11; Linux x86_64)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)",
    "Mozilla/5.0 (Linux; Android 10; SM-G960F)",
    "Mozilla/5.0 (Linux; Android 11; Mi 9T Pro)"
]

# ===============================
#   وضعیت ربات
# ===============================
state = {
    "running": False,
    "success": 0,
    "fail": 0,
    "token": "",
    "cookie": "",
    "concurrency": 50,          # تعداد درخواست همزمان
    "max_concurrency": 200,     # سقف همزمانی
    "invite_limit": 0,          # حد دعوت موفق (۰ = نامحدود)
    "prefix_stats": {p: {"success": 1, "fail": 1} for p in PREFIXES},
    "fail_streak": 0,
    "results": [],
    "executor": None,
    "semaphore": None,
    "start_time": 0
}

# ===============================
#   تنظیم لاگ‌گیری
# ===============================
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bot.log')
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logging.info("🤖 ربات ایرانسل در حال راه‌اندازی است...")

# ===============================
#   ساخت ربات تلگرام
# ===============================
try:
    bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
    logging.info("✅ ربات با موفقیت به تلگرام متصل شد")
except Exception as e:
    logging.error(f"❌ خطا در ساخت ربات: {e}")
    print(f"خطا در ساخت ربات: {e}")
    exit(1)

# ===============================
#   ساخت کیبورد‌ها
# ===============================
def create_keyboard():
    kb = ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    kb.row('🚀 شروع', '⏹ توقف', '📊 وضعیت')
    kb.row('⚡ سرعت', '🎯 حد دعوت', '⚙️ تنظیمات')
    kb.row('📈 آمار پیشرفته', '❓ راهنما')
    return kb

def create_speed_keyboard():
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("🚀 50", callback_data="speed_50"),
        InlineKeyboardButton("💨 100", callback_data="speed_100"),
        InlineKeyboardButton("🔥 200", callback_data="speed_200")
    )
    kb.row(
        InlineKeyboardButton("⚡ 30", callback_data="speed_30"),
        InlineKeyboardButton("📶 10", callback_data="speed_10"),
        InlineKeyboardButton("🐢 5", callback_data="speed_5")
    )
    return kb

def create_limit_keyboard():
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("🎯 1000", callback_data="limit_1000"),
        InlineKeyboardButton("🎯 5000", callback_data="limit_5000"),
        InlineKeyboardButton("∞ نامحدود", callback_data="limit_0")
    )
    kb.row(
        InlineKeyboardButton("🎯 10000", callback_data="limit_10000"),
        InlineKeyboardButton("🎯 20000", callback_data="limit_20000"),
        InlineKeyboardButton("✏️ سفارشی", callback_data="limit_custom")
    )
    return kb

# ===============================
#   تولید شماره
# ===============================
def choose_prefix():
    total_weight = sum(
        state["prefix_stats"][p]["success"] / (state["prefix_stats"][p]["fail"] + 1)
        for p in PREFIXES
    )
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

# ===============================
#   ارسال درخواست به API ایرانسل (ضدبلاک)
# ===============================
def send_irancell_request(number: str) -> bool:
    try:
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "fa",
            "authorization": state["token"],
            "content-type": "application/json",
            "cookie": state["cookie"],
            # User-Agent تصادفی برای طبیعی‌تر شدن درخواست‌ها
            "user-agent": random.choice(USER_AGENTS)
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
            if len(state["results"]) > 50:
                state["results"].pop(0)
            logging.info(f"✅ موفق: {number}")
            return True
        else:
            state["fail"] += 1
            state["prefix_stats"][prefix]["fail"] += 1
            state["fail_streak"] += 1
            result_msg = f"{number} ❌{response.status_code}"
            state["results"].append(result_msg)
            if len(state["results"]) > 50:
                state["results"].pop(0)
            logging.warning(f"❌ خطا {response.status_code}: {number}")
            return False

    except Exception as e:
        state["fail"] += 1
        state["fail_streak"] += 1
        result_msg = f"{number} ❌NET"
        state["results"].append(result_msg)
        if len(state["results"]) > 50:
            state["results"].pop(0)
        logging.error(f"❌ خطای شبکه: {number} - {e}")
        return False

# ===============================
#   Worker ها
# ===============================
def worker_task(number: str):
    if state["running"]:
        send_irancell_request(number)
        # آزاد کردن یک اسلات همزمانی
        state["semaphore"].release()

def worker_controller():
    logging.info("🚀 کنترلر کارگرها شروع شد...")
    state["executor"] = ThreadPoolExecutor(max_workers=state["max_concurrency"])
    state["semaphore"] = threading.Semaphore(state["concurrency"])
    state["start_time"] = time.time()

    while state["running"]:
        try:
            # رسیدن به حد دعوت
            if state["invite_limit"] > 0 and state["success"] >= state["invite_limit"]:
                logging.info("🎯 حد دعوت رسیده، توقف خودکار")
                state["running"] = False
                break

            # خطای متوالی زیاد
            if state["fail_streak"] >= 100:
                logging.warning("⛔ توقف خودکار به دلیل 100 خطای متوالی")
                state["running"] = False
                break

            acquired = state["semaphore"].acquire(blocking=False)
            if not acquired:
                # اگر ظرفیت پر است، کمی صبر
                time.sleep(0.001)
                continue

            number = generate_number()

            # 🔥 Delay تصادفی کوچک برای ضدبلاک (گزینه ۲)
            time.sleep(random.uniform(0.05, 0.25))

            state["executor"].submit(worker_task, number)

        except Exception as e:
            logging.error(f"خطا در کنترلر: {e}")
            time.sleep(0.1)

# ===============================
#   دستورات ربات
# ===============================
@bot.message_handler(commands=['start'])
def start_command(message):
    try:
        if state["running"]:
            bot.send_message(
                message.chat.id,
                "⚠️ ربات از قبل در حال اجراست!",
                reply_markup=create_keyboard()
            )
            return

        if not state["token"] or not state["cookie"]:
            bot.send_message(
                message.chat.id,
                "❌ ابتدا توکن و کوکی را تنظیم کنید!\n"
                "از دکمه '⚙️ تنظیمات' استفاده کنید.",
                reply_markup=create_keyboard()
            )
            return

        state["running"] = True
        state["success"] = 0
        state["fail"] = 0
        state["fail_streak"] = 0
        state["results"] = []

        controller_thread = threading.Thread(target=worker_controller, daemon=True)
        controller_thread.start()

        limit_text = (
            f"🎯 حد دعوت: {state['invite_limit']}"
            if state["invite_limit"] > 0 else "🎯 حد دعوت: نامحدود"
        )

        bot.send_message(
            message.chat.id,
            f"🚀 ربات با سرعت بالا شروع شد!\n"
            f"⚡ همزمانی: {state['concurrency']} درخواست\n"
            f"{limit_text}\n\n"
            "📡 در حال ارسال درخواست...",
            reply_markup=create_keyboard()
        )

        logging.info("🚀 ربات شروع به کار کرد")

    except Exception as e:
        logging.error(f"خطا در دستور start: {e}")

@bot.message_handler(commands=['stop'])
def stop_command(message):
    try:
        if not state["running"]:
            bot.send_message(
                message.chat.id,
                "⚠️ ربات در حال اجرا نیست!",
                reply_markup=create_keyboard()
            )
            return

        state["running"] = False
        if state["executor"]:
            state["executor"].shutdown(wait=False)

        bot.send_message(
            message.chat.id,
            "⏹ ربات متوقف شد!\n\n"
            "برای مشاهده آمار از '📊 وضعیت' استفاده کنید.",
            reply_markup=create_keyboard()
        )

        logging.info("⏹ ربات متوقف شد")

    except Exception as e:
        logging.error(f"خطا در دستور stop: {e}")

@bot.message_handler(commands=['speed'])
def speed_command(message):
    try:
        bot.send_message(
            message.chat.id,
            "⚡ سرعت ارسال را انتخاب کنید:",
            reply_markup=create_speed_keyboard()
        )
    except Exception as e:
        logging.error(f"خطا در دستور speed: {e}")

@bot.message_handler(commands=['limit'])
def limit_command(message):
    try:
        bot.send_message(
            message.chat.id,
            "🎯 حد دعوت موفق را انتخاب کنید:",
            reply_markup=create_limit_keyboard()
        )
    except Exception as e:
        logging.error(f"خطا در دستور limit: {e}")

@bot.message_handler(commands=['status'])
def status_command(message):
    try:
        status_text = "🟢 در حال اجرا" if state["running"] else "🔴 متوقف شده"
        elapsed = time.time() - state.get("start_time", time.time())
        total_requests = state["success"] + state["fail"]

        if elapsed > 0 and total_requests > 0:
            rpm = int(total_requests / elapsed * 60)
            success_rate = int((state["success"] / total_requests) * 100)
        else:
            rpm = 0
            success_rate = 0

        limit_text = (
            f"🎯 حد دعوت: {state['invite_limit']}"
            if state["invite_limit"] > 0 else "🎯 حد دعوت: نامحدود"
        )

        msg = (
            f"<b>📊 وضعیت ربات</b>\n\n"
            f"{status_text}\n"
            f"⚡ سرعت: <code>{state['concurrency']}</code> درخواست/ثانیه\n"
            f"{limit_text}\n\n"
            f"<b>📈 آمار:</b>\n"
            f"✅ موفق: <code>{state['success']}</code>\n"
            f"❌ ناموفق: <code>{state['fail']}</code>\n"
            f"📡 مجموع: <code>{total_requests}</code>\n"
            f"🎯 نرخ موفقیت: <code>{success_rate}%</code>\n"
            f"🚀 سرعت تقریبی: <code>{rpm}</code> درخواست/دقیقه\n\n"
            f"<b>📋 آخرین نتایج:</b>\n"
        )

        recent = state["results"][-5:] if state["results"] else ["📭 هنوز نتیجه‌ای نیست"]
        for r in recent:
            msg += f"• {r}\n"

        bot.send_message(
            message.chat.id,
            msg,
            parse_mode='HTML',
            reply_markup=create_keyboard()
        )

    except Exception as e:
        logging.error(f"خطا در دستور status: {e}")

@bot.message_handler(commands=['settings'])
def settings_command(message):
    try:
        txt = (
            "⚙️ <b>تنظیمات ربات</b>\n\n"
            "برای تنظیم توکن و کوکی، پیام را به این شکل بفرست:\n\n"
            "<code>توکن: Bearer ....</code>\n"
            "<code>کوکی: session=....</code>\n"
        )
        bot.send_message(message.chat.id, txt, parse_mode='HTML', reply_markup=create_keyboard())
    except Exception as e:
        logging.error(f"خطا در دستور settings: {e}")

@bot.message_handler(commands=['help'])
def help_command(message):
    try:
        txt = (
            "🤖 <b>راهنمای ربات</b>\n\n"
            "/start - شروع ارسال دعوت‌نامه\n"
            "/stop - توقف\n"
            "/status - نمایش وضعیت\n"
            "/speed - تنظیم سرعت\n"
            "/limit - تنظیم حد دعوت\n"
            "/settings - تنظیم توکن و کوکی\n"
            "/help - همین راهنما\n"
        )
        bot.send_message(message.chat.id, txt, parse_mode='HTML', reply_markup=create_keyboard())
    except Exception as e:
        logging.error(f"خطا در دستور help: {e}")

# ===============================
#   Callback دکمه‌های اینلاین
# ===============================
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        if call.data.startswith('speed_'):
            speed_value = call.data.split('_')[1]
            if speed_value.isdigit():
                new_speed = int(speed_value)
                if 1 <= new_speed <= state["max_concurrency"]:
                    state["concurrency"] = new_speed
                    bot.answer_callback_query(call.id, f"✅ سرعت به {new_speed} تنظیم شد")
                    bot.edit_message_text(
                        "⚡ سرعت به‌روزرسانی شد.",
                        call.message.chat.id,
                        call.message.message_id
                    )
                else:
                    bot.answer_callback_query(call.id, "❌ سرعت خارج از محدوده است")
            else:
                bot.answer_callback_query(call.id, "❌ مقدار نامعتبر!")

        elif call.data.startswith('limit_'):
            limit_value = call.data.split('_')[1]
            if limit_value == '0':
                state["invite_limit"] = 0
                bot.answer_callback_query(call.id, "✅ حد دعوت نامحدود شد")
                bot.edit_message_text(
                    "🎯 حد دعوت نامحدود شد.",
                    call.message.chat.id,
                    call.message.message_id
                )
            elif limit_value == 'custom':
                bot.answer_callback_query(call.id, "✏️ عدد دلخواه را ارسال کنید")
                bot.send_message(
                    call.message.chat.id,
                    "✏️ حد دعوت مورد نظر را وارد کنید (مثلاً 15000):"
                )
            elif limit_value.isdigit():
                new_limit = int(limit_value)
                state["invite_limit"] = new_limit
                bot.answer_callback_query(call.id, f"✅ حد دعوت {new_limit} تنظیم شد")
                bot.edit_message_text(
                    f"🎯 حد دعوت به {new_limit} تنظیم شد.",
                    call.message.chat.id,
                    call.message.message_id
                )
    except Exception as e:
        logging.error(f"خطا در callback: {e}")

# ===============================
#   هندل تمام پیام‌ها
# ===============================
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    try:
        text = message.text.strip()

        if text == '🚀 شروع':
            start_command(message)
        elif text == '⏹ توقف':
            stop_command(message)
        elif text == '📊 وضعیت' or text == '📈 آمار پیشرفته':
            status_command(message)
        elif text == '⚡ سرعت':
            speed_command(message)
        elif text == '🎯 حد دعوت':
            limit_command(message)
        elif text == '⚙️ تنظیمات':
            settings_command(message)
        elif text == '❓ راهنما':
            help_command(message)

        elif text.startswith('توکن:'):
            token = text.replace('توکن:', '').strip()
            state["token"] = token
            bot.send_message(message.chat.id, "✅ توکن ذخیره شد.", reply_markup=create_keyboard())
            logging.info("توکن ذخیره شد")

        elif text.startswith('کوکی:'):
            cookie = text.replace('کوکی:', '').strip()
            state["cookie"] = cookie
            bot.send_message(message.chat.id, "✅ کوکی ذخیره شد.", reply_markup=create_keyboard())
            logging.info("کوکی ذخیره شد")

        elif text.isdigit():
            val = int(text)
            if 1 <= val <= 100000:
                state["invite_limit"] = val
                bot.send_message(
                    message.chat.id,
                    f"🎯 حد دعوت به {val} تنظیم شد.",
                    reply_markup=create_keyboard()
                )
                logging.info(f"حد دعوت به {val} تنظیم شد")
            else:
                bot.send_message(
                    message.chat.id,
                    "❌ حد دعوت باید بین 1 تا 100000 باشد.",
                    reply_markup=create_keyboard()
                )
        else:
            bot.send_message(
                message.chat.id,
                "❌ دستور نامعتبر! از دکمه‌های زیر استفاده کنید:",
                reply_markup=create_keyboard()
            )

    except Exception as e:
        logging.error(f"خطا در پردازش پیام: {e}")

# ===============================
#   تابع اصلی
# ===============================
def main():
    logging.info("🔄 شروع polling ربات...")
    bot.polling(none_stop=True, interval=1, timeout=30)

if __name__ == "__main__":
    main()