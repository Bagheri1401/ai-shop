# 🛍️ ai-shop Professional Edition

<p align="center">
  <strong>Telegram AI Commerce Platform</strong><br>
  فروشگاه حرفه‌ای تلگرام برای فروش اکانت، اشتراک، لایسنس، فایل و خدمات هوش مصنوعی
</p>

<p align="center">
  <code>Version 2.2.1</code>
  · PostgreSQL
  · Zarinpal
  · Card Payment
  · Wallet
  · Automatic Delivery
</p>

---

## ✨ امکانات اصلی

- 🛍️ مدیریت محصولات، دسته‌بندی‌ها، قیمت و موجودی
- 💳 پرداخت آنلاین زرین‌پال
- 🧾 کارت‌به‌کارت و ذخیره تصویر رسید در PostgreSQL
- ✅ مشاهده، تأیید یا رد رسید در پنل مدیریت
- 🔐 ارسال خودکار اطلاعات سرویس بعد از تأیید
- 💰 کیف پول و تاریخچه تراکنش‌ها
- 🎟️ کد تخفیف
- 🎫 تیکت پشتیبانی
- 👥 کاربران، سفارش‌ها و گزارش فروش
- 🗄️ مدیریت داخلی دیتابیس
- 📚 راهنمای گرافیکی داخل پنل
- 💾 بکاپ، بازیابی و Rollback خودکار
- 🔄 آپدیت امن همراه با بررسی نسخه و سلامت سرویس

---

# 🚀 نصب اولیه

## 1. اتصال دامنه

پیش از نصب، رکورد `A` دامنه را روی IP سرور قرار دهید و پورت‌های زیر را باز کنید:

```text
80
443
```

## 2. دریافت پروژه

```bash
git clone https://github.com/Bagheri1401/AI-SHOP.git ai-shop
cd ai-shop
```

## 3. اجرای نصب

```bash
sudo bash install.sh
```

اسکریپت نصب موارد زیر را خودکار انجام می‌دهد:

1. نصب Python، PostgreSQL، Nginx و Certbot
2. اعتبارسنجی کد برنامه
3. ساخت دیتابیس و کاربر امن
4. نصب سرویس در `/opt/ai-shop`
5. تنظیم Nginx و SSL
6. ثبت Webhook تلگرام
7. بررسی سلامت برنامه
8. نمایش رمز پنل مدیریت

> رمز پنل نمایش‌داده‌شده در پایان نصب را در محل امن ذخیره کنید.

---

# 🔄 آپدیت نسخه نصب‌شده

ابتدا مطمئن شوید فایل‌های آخرین نسخه داخل GitHub قرار گرفته‌اند.

```bash
cd ~/ai-shop
git fetch origin
git reset --hard origin/main
sudo bash remote-update.sh
```

آپدیتر حرفه‌ای:

- آخرین نسخه را از GitHub دریافت می‌کند.
- تمام فایل‌های Python و Bash را بررسی می‌کند.
- از برنامه و تنظیمات فعلی بکاپ Rollback می‌گیرد.
- فایل `.env` و دیتابیس را حفظ می‌کند.
- نسخه جدید را نصب و سرویس را ریستارت می‌کند.
- مسیر `/health` و `/version` را کنترل می‌کند.
- در صورت خطا، نسخه قبلی را خودکار برمی‌گرداند.

## بررسی نسخه فعال

```bash
curl -s http://127.0.0.1:3000/version
echo
```

خروجی صحیح:

```json
{"name":"ai-shop","version":"2.2.1"}
```

---

# 🌐 آدرس پنل‌ها

```text
مدیریت فروشگاه:
https://YOUR-DOMAIN/admin

راهنمای گرافیکی:
https://YOUR-DOMAIN/admin/help

مدیریت دیتابیس:
https://YOUR-DOMAIN/admin/database
```

---

# 🩺 بررسی سلامت سیستم

```bash
cd ~/ai-shop
sudo bash health-check.sh
```

بررسی دستی:

```bash
systemctl status ai-shop --no-pager
journalctl -u ai-shop -n 100 --no-pager
curl -s http://127.0.0.1:3000/health
```

---

# 💾 بکاپ

```bash
cd ~/ai-shop
sudo bash backup.sh
```

بکاپ شامل دیتابیس و تنظیمات محافظت‌شده است و در پوشه زیر ذخیره می‌شود:

```text
backups/
```

---

# ♻️ بازیابی

```bash
cd ~/ai-shop
sudo bash restore.sh backups/ai-shop-YYYYMMDD-HHMMSS.tar.gz
```

برای جلوگیری از بازیابی اشتباهی، اسکریپت تأیید نهایی درخواست می‌کند.

---

# 🗑️ حذف

```bash
cd ~/ai-shop
sudo bash uninstall.sh
```

هنگام حذف می‌توانید جداگانه مشخص کنید که:

- دیتابیس حذف شود یا باقی بماند.
- SSL حذف شود یا باقی بماند.
- PostgreSQL و Nginx حذف شوند یا باقی بمانند.

---

# 🛠️ رفع خطاهای رایج

## ربات پاسخ نمی‌دهد

```bash
journalctl -u ai-shop -n 100 --no-pager
curl -s http://127.0.0.1:3000/health
```

## بررسی Webhook

```bash
sudo bash -c '
source /opt/ai-shop/.env
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo"
echo
'
```

## پنل باز نمی‌شود

```bash
nginx -t
systemctl status nginx --no-pager
systemctl status ai-shop --no-pager
```

## تعمیر مجوزها و سرویس

```bash
cd ~/ai-shop
sudo bash repair.sh
```

---

# 🔐 نکات امنیتی

- فایل `.env` را داخل GitHub قرار ندهید.
- بکاپ‌ها شامل اطلاعات حساس هستند.
- توکن ربات را در عکس یا پیام عمومی منتشر نکنید.
- توکن‌های افشاشده را فوراً در BotFather باطل کنید.
- پیش از آپدیت مهم، بکاپ جداگانه بگیرید.
- دسترسی پنل مدیریت را فقط در اختیار مدیران قرار دهید.

---

<p align="center">
  <strong>ai-shop Professional Edition v2.2.1</strong>
</p>


---

# 🛠 پنل مدیریت داخل تلگرام

مدیر تعریف‌شده هنگام نصب می‌تواند دستور زیر را ارسال کند:

```text
/admin
```

منوی مدیریت شامل آمار، وضعیت سرور، تنظیمات، پنل وب، شخصی‌سازی، محصولات، سفارش‌ها، کاربران، کیف پول، تخفیف‌ها، رسیدها، پیام همگانی، درگاه‌ها، موجودی سرویس، دیتابیس، بکاپ، گزارش‌ها، لاگ سیستم، بروزرسانی، سلامت سیستم و راهنما است.

برای امنیت، اجرای مستقیم آپدیت و بکاپ از تلگرام غیرفعال است و دستور امن اجرای آن روی سرور نمایش داده می‌شود.


---

# 🔧 اصلاح فایل نصب و آپدیت در نسخه 2.2.1

این نسخه خطای زیر را رفع می‌کند:

```text
install.sh: line 77: line: command not found
```

علت خطا حذف‌شدن تابع نمایشی `line` از رابط ترمینال بود. در نسخه 2.2.1 تمام توابع رابط نصب و آپدیت در هر فایل به‌صورت مستقل تعریف شده‌اند.

## نصب

```bash
sudo bash install.sh
```

## آپدیت مستقیم از GitHub

```bash
sudo bash remote-update.sh
```

## آپدیت از فایل‌های ZIP استخراج‌شده

```bash
sudo bash update.sh
```

هر دو روش قبل از جایگزینی فایل‌ها، کد Python و اسکریپت‌های Shell را بررسی می‌کنند و در صورت شکست، نسخه قبلی را بازیابی می‌کنند.
