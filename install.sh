#!/bin/bash
echo "🚀 نصب و اجرای خودکار ربات تلگرام (نسخه کامل)"

# ===============================
#  دریافت توکن از کاربر
# ===============================
echo -n "🔑 لطفاً توکن ربات تلگرام را وارد کنید: "
read BOT_TOKEN

if [[ -z "$BOT_TOKEN" ]]; then
    echo "⛔ توکن وارد نشده! نصب لغو شد."
    exit 1
fi

# ذخیره توکن
echo "export BOT_TOKEN=\"$BOT_TOKEN\"" >> ~/.bashrc
export BOT_TOKEN="$BOT_TOKEN"
echo "✅ توکن ذخیره شد."

# ===============================
# نصب Python3 و pip3 اگر وجود نداشت
# ===============================
echo "🔍 بررسی Python3..."
if ! command -v python3 &> /dev/null
then
    echo "⛔ Python3 وجود ندارد. نصب می‌کنیم..."
    sudo apt update -y
    sudo apt install python3 -y
fi

echo "🔍 بررسی pip3..."
if ! command -v pip3 &> /dev/null
then
    echo "⛔ pip3 نصب نیست. نصب می‌شود..."
    sudo apt install python3-pip -y
fi

# ===============================
# نصب کتابخانه‌های پایتون
# ===============================
echo "📦 نصب pyTelegramBotAPI و requests ..."
sudo pip3 install pyTelegramBotAPI requests --upgrade

# ===============================
# دانلود جدیدترین نسخه text12.py
# ===============================
echo "⬇️ دانلود فایل text12.py ..."
curl -o /root/text12.py https://raw.githubusercontent.com/tmymym/mymmd/main/text12.py

# ===============================
# ساخت سرویس دائمی systemd
# ===============================
echo "⚙️ ساخت سرویس irancellbot ..."

sudo bash -c "cat > /etc/systemd/system/irancellbot.service" <<EOF
[Unit]
Description=Irancell Telegram Bot
After=network.target

[Service]
User=root
WorkingDirectory=/root
Environment=BOT_TOKEN=$BOT_TOKEN
ExecStart=/usr/bin/python3 /root/text12.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# ===============================
# فعال‌سازی سرویس
# ===============================
sudo systemctl daemon-reload
sudo systemctl enable irancellbot
sudo systemctl restart irancellbot

echo ""
echo "🎉 نصب کامل شد!"
echo "🤖 ربات اکنون به صورت دائمی اجرا می‌شود."
echo ""
echo "🔍 برای دیدن وضعیت:"
echo "sudo systemctl status irancellbot"
echo ""
echo "📜 برای دیدن لاگ زنده:"
echo "journalctl -u irancellbot -f"
echo ""
