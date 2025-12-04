#!/bin/bash
echo "🚀 نصب کامل ربات تلگرام (نسخه مخصوص Ubuntu 24.04 + Python 3.12)"

# ===========================
# گرفتن توکن ربات
# ===========================
echo -n "🔑 لطفاً توکن ربات تلگرام را وارد کنید: "
read BOT_TOKEN
if [[ -z "$BOT_TOKEN" ]]; then
    echo "❌ توکن وارد نشده! نصب متوقف شد."
    exit 1
fi

echo "export BOT_TOKEN=\"$BOT_TOKEN\"" >> ~/.bashrc
export BOT_TOKEN="$BOT_TOKEN"
echo "✅ توکن ذخیره شد!"

# ===========================
# نصب Python3 و pip3 اگر نبود
# ===========================
echo "🔍 بررسی Python3..."
if ! command -v python3 &> /dev/null
then
    echo "⛔ Python3 نصب نیست. درحال نصب..."
    sudo apt update -y
    sudo apt install python3 -y
fi

echo "🔍 بررسی pip3..."
if ! command -v pip3 &> /dev/null
then
    echo "⛔ pip3 نصب نیست. نصب می‌شود..."
    sudo apt install python3-pip -y
fi

# ===========================
# نصب کتابخانه‌ها (روش سازگار با Python 3.12)
# ===========================
echo "📦 نصب کتابخانه‌های پایتون..."
sudo python3 -m pip install pyTelegramBotAPI requests --break-system-packages

# ===========================
# دانلود فایل ربات
# ===========================
echo "⬇️ دانلود text12.py..."
curl -o /root/text12.py https://raw.githubusercontent.com/tmymym/mymmd/main/text12.py

# ===========================
# پیدا کردن مسیر صحیح python3
# ===========================
PY_PATH=$(which python3)
echo "📌 مسیر Python3: $PY_PATH"

# ===========================
# ساخت سرویس systemd
# ===========================
echo "⚙️ ساخت سرویس دائمی irancellbot..."

sudo bash -c "cat > /etc/systemd/system/irancellbot.service" <<EOF
[Unit]
Description=Irancell Telegram Bot
After=network.target

[Service]
User=root
Environment=BOT_TOKEN=$BOT_TOKEN
WorkingDirectory=/root
ExecStart=$PY_PATH /root/text12.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# ===========================
# فعال‌سازی سرویس
# ===========================
sudo systemctl daemon-reload
sudo systemctl enable irancellbot
sudo systemctl restart irancellbot

echo ""
echo "🎉 نصب با موفقیت انجام شد!"
echo "🤖 ربات اکنون به‌صورت دائمی اجرا می‌شود."
echo ""
echo "🔍 وضعیت سرویس:"
echo "sudo systemctl status irancellbot"
echo ""
echo "📜 مشاهده لاگ زنده:"
echo "journalctl -u irancellbot -f"
echo ""
