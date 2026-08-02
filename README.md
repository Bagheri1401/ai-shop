# 🛍️ ai-shop Professional Edition v3.1.0

<p align="center">
  <strong>Telegram AI Commerce Platform</strong><br>
  فروشگاه حرفه‌ای تلگرام با PostgreSQL، پنل مدیریت وب، پرداخت، رسید و تحویل خودکار
</p>

---

## ✨ تغییرات نسخه 3.1.0

- نصب‌کننده فارسی با چیدمان تمیزتر و خروجی مرحله‌ای
- نوار پیشرفت نصب
- پاک‌سازی خودکار فاصله، Enter، کوتیشن و کاراکتر `\r` از توکن
- بررسی فرمت توکن قبل از ادامه
- اعتبارسنجی آنلاین توکن با Telegram API
- نمایش نام و نام کاربری ربات تأییدشده
- مخفی‌سازی توکن در خروجی نصب
- توقف نصب در صورت نامعتبر بودن توکن
- بررسی اتصال PostgreSQL
- بررسی سلامت برنامه و Webhook
- حفظ اطلاعات دیتابیس هنگام آپدیت
- Rollback خودکار در صورت خرابی نسخه جدید

---

# 🚀 نصب اولیه

## پیش‌نیازها

- Ubuntu 22.04 یا Ubuntu 24.04
- دسترسی `root` یا `sudo`
- دامنه متصل به IP سرور
- باز بودن پورت‌های `80` و `443`
- توکن معتبر BotFather
- شناسه عددی مدیر تلگرام

## دریافت پروژه

```bash
git clone https://github.com/Bagheri1401/AI-SHOP.git ai-shop
cd ai-shop
```

## اجرای نصب

```bash
sudo bash install.sh
```

در بخش توکن، توکن را مستقیماً از BotFather کپی و Paste کنید. نصب‌کننده:

1. فاصله‌های ابتدا و انتهای توکن را حذف می‌کند.
2. کوتیشن‌های اضافی را حذف می‌کند.
3. فرمت توکن را بررسی می‌کند.
4. با دستور `getMe` توکن را از Telegram API تأیید می‌کند.
5. نام کاربری ربات را قبل از ادامه نمایش می‌دهد.

توکن هنگام تایپ روی صفحه نمایش داده نمی‌شود.

---

# 🔄 آپدیت از GitHub

```bash
cd ~/ai-shop
git fetch origin
git reset --hard origin/main
sudo bash remote-update.sh
```

## آپدیت از فایل ZIP استخراج‌شده

```bash
cd /PATH/TO/ai-shop
sudo bash update.sh
```

آپدیتر:

- کد Python و فایل‌های Bash را بررسی می‌کند.
- از نسخه فعلی بکاپ Rollback می‌گیرد.
- `.env` و دیتابیس را حفظ می‌کند.
- نسخه جدید را فعال می‌کند.
- سلامت سرویس و شماره نسخه را کنترل می‌کند.
- در صورت شکست نسخه قبلی را برمی‌گرداند.

---

# 🩺 بررسی سلامت

```bash
cd ~/ai-shop
sudo bash health-check.sh
```

بررسی دستی نسخه:

```bash
curl -s http://127.0.0.1:3000/version
echo
```

خروجی:

```json
{"name":"ai-shop","version":"3.1.0"}
```

---

# 🌐 پنل‌ها

```text
مدیریت:
https://YOUR-DOMAIN/admin

راهنما:
https://YOUR-DOMAIN/admin/help

مدیریت دیتابیس:
https://YOUR-DOMAIN/admin/database
```

---

# 🔧 رفع مشکل توکن

## توکن تأیید نمی‌شود

توکن را در BotFather دوباره ایجاد کنید:

```text
/mybots
Bot Settings
Revoke Current Token
Generate New Token
```

سپس توکن جدید را بدون علامت نقل‌قول وارد کنید.

بررسی دستی توکن:

```bash
curl "https://api.telegram.org/botYOUR_TOKEN/getMe"
```

پاسخ صحیح شامل این مقدار است:

```json
{"ok":true}
```

## نکته امنیتی مهم

توکن‌هایی که در عکس، چت یا صفحه عمومی دیده شده‌اند باید فوراً در BotFather باطل شوند.

---

# 💾 بکاپ

```bash
sudo bash backup.sh
```

# ♻️ بازیابی

```bash
sudo bash restore.sh backups/FILE.tar.gz
```

# 🗑️ حذف

```bash
sudo bash uninstall.sh
```

---

<p align="center">
  <strong>ai-shop Professional Edition v3.1.0</strong>
</p>


---

# 🛡 منوی مدیریت پایین تلگرام

با لمس دکمه زیر یا ارسال دستور `/admin`:

```text
⚙️ مدیریت ai-shop
```

کیبورد مدیریت در پایین صفحه باز می‌شود و شامل این گزینه‌هاست:

- 👥 بخش ادمین‌ها
- 👨‍💼 مدیریت کاربران
- ♻️ پیام همگانی
- 🎁 بخش تخفیفات
- 🚦 بخش راهنماها
- 🔒 بخش جوین اجباری
- 💳 بخش درگاه‌ها
- 🔐 رمز پنل وب
- 🖥 پنل مدیریت وب
- ⬅️ بازگشت

دکمه «⬅️ بازگشت» کیبورد مدیریت را می‌بندد و منوی اصلی را نمایش می‌دهد.

## دریافت رمز پنل از تلگرام

فقط مدیر اصلی می‌تواند یکی از این روش‌ها را استفاده کند:

```text
🔐 رمز پنل وب
```

یا:

```text
/panelpass
```

اطلاعات ورود به‌صورت پیام محافظت‌شده ارسال می‌شود.

## ساخت رمز جدید از سرور

```bash
cd ~/ai-shop
sudo bash reset-panel-password.sh
```

اسکریپت یک رمز تصادفی جدید می‌سازد، فایل `/opt/ai-shop/.env` را اصلاح و سرویس را ریستارت می‌کند.
