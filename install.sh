#!/bin/bash
echo "🚀 نصب و اجرای خودکار ربات تلگرام (نسخه دائمی)"

# --- گرفتن توکن از کاربر ---
echo -n "🔑 لطفاً توکن ربات تلگرام را وارد کنید: "
read BOT_TOKEN

if [[ -z "$BOT_TOKEN" ]]; then
    echo "⛔ توکن وارد نشده! نصب لغو شد."
    exit 1
fi

# ذخیره توکن در محیط سیستم
echo "export BOT_TOKEN=\"$BOT_TOKEN\"" >> ~/.bashrc
export BOT_TOKEN="$BOT_TOKEN"

echo "✅ توکن ذخیره شد."


# --- دانلود فایل ربات ---
echo "⬇️ دریافت فایل text12.py..."
curl -o /root/text12.py https://raw.githubusercontent.com/tmymym/mymmd/main/text12.py


# --- نصب Python ---
echo "🔍 بررسی Python3..."
if ! command -v python3 &> /dev/null
then
    echo "⛔ Python3 وجود ندارد، نصب می‌کنیم..."
    sudo apt update -y
    sudo apt install python3 -y
fi

# --- نصب pip ---
echo "🔍 بررسی pip..."
if ! command -v pip3 &> /dev/null
then
    echo "⛔ pip نصب نیست، درحال نصب..."
    sudo apt install python3-pip -y
fi


# --- نصب کتابخانه‌ها ---
echo "📦 نصب پیش‌نیازهای پایتون..."
pip3 install requests pyTelegramBotAPI --upgrade


# --- ساخت سرویس systemd ---
echo "⚙️ در حال ساخت سرویس دائمی ربات..."

sudo bash -c 'cat > /etc/systemd/system/irancellbot.service <<EOF
[Unit]
Description=Irancell Telegram Bot
After=network.target

[Service]
User=root
WorkingDirectory=/root
Environment="BOT_TOKEN='""$BOT_TOKEN""'"
ExecStart=/usr/bin/python3 /root/text12.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF'

echo "✅ سرویس ساخته شد."


# --- فعال‌سازی سرویس ---
sudo systemctl daemon-reload
sudo systemctl enable irancellbot
sudo systemctl restart irancellbot

echo ""
echo "🎉 نصب کامل شد!"
echo "🤖 ربات اکنون همیشه روشن است و بعد از ریبوت سرور هم اجرا می‌شود."
echo ""
echo "📌 وضعیت ربات:"
echo "sudo systemctl status irancellbot"
echo ""
echo "📜 مشاهده لاگ زنده:"
echo "journalctl -u irancellbot -f"
