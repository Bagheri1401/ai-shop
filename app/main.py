#!/usr/bin/env python3
import os
import json
import base64
import html
import urllib.request
import urllib.parse
import urllib.error
import csv
import shutil
import subprocess
import io
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from datetime import datetime
import psycopg2
import psycopg2.extras

def load_env(path):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k,v=line.split("=",1)
            os.environ.setdefault(k.strip(), v.strip())

BASE_DIR=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_env(os.path.join(BASE_DIR, ".env"))

HOST=os.getenv("APP_HOST","127.0.0.1")
PORT=int(os.getenv("APP_PORT","3000"))
DOMAIN=os.getenv("DOMAIN","")
PUBLIC_URL=os.getenv("PUBLIC_URL","").rstrip("/")
BOT_TOKEN=os.getenv("TELEGRAM_BOT_TOKEN","")
WEBHOOK_SECRET=os.getenv("TELEGRAM_WEBHOOK_SECRET","")
ADMIN_ID=os.getenv("ADMIN_TELEGRAM_ID","")
ADMIN_USER=os.getenv("ADMIN_USERNAME","admin")
ADMIN_PASS=os.getenv("ADMIN_PASSWORD","change-me")
CURRENCY=os.getenv("CURRENCY","IRR")
APP_VERSION="3.1.0"

def db():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME","ai_shop"),
        user=os.getenv("DB_USER","ai_shop"),
        password=os.getenv("DB_PASSWORD",""),
        host=os.getenv("DB_HOST","127.0.0.1"),
        port=os.getenv("DB_PORT","5432"),
    )

class PersistentState:
    def get(self, key, default=None):
        try:
            conn=db(); cur=conn.cursor()
            cur.execute("SELECT state_json FROM user_sessions WHERE telegram_id=%s",(int(key),))
            row=cur.fetchone(); cur.close(); conn.close()
            return json.loads(row[0]) if row else default
        except Exception as exc:
            print("state get error",repr(exc)); return default
    def __setitem__(self, key, value):
        conn=db(); cur=conn.cursor()
        cur.execute("""INSERT INTO user_sessions(telegram_id,state_json,updated_at) VALUES(%s,%s,NOW())
                       ON CONFLICT(telegram_id) DO UPDATE SET state_json=EXCLUDED.state_json,updated_at=NOW()""",
                    (int(key),json.dumps(value,ensure_ascii=False)))
        conn.commit(); cur.close(); conn.close()
    def pop(self, key, default=None):
        old=self.get(key,default)
        try:
            conn=db(); cur=conn.cursor(); cur.execute("DELETE FROM user_sessions WHERE telegram_id=%s",(int(key),)); conn.commit(); cur.close(); conn.close()
        except Exception as exc: print("state pop error",repr(exc))
        return old

STATE=PersistentState()

def init_db():
    conn=db(); cur=conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
      id BIGSERIAL PRIMARY KEY,
      telegram_id BIGINT UNIQUE NOT NULL,
      username TEXT,
      first_name TEXT,
      full_name TEXT,
      phone TEXT,
      wallet_balance BIGINT NOT NULL DEFAULT 0,
      referral_code TEXT UNIQUE,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS products(
      id BIGSERIAL PRIMARY KEY,
      title TEXT NOT NULL,
      description TEXT NOT NULL DEFAULT '',
      price BIGINT NOT NULL CHECK(price>=0),
      delivery_text TEXT NOT NULL DEFAULT '',
      active BOOLEAN NOT NULL DEFAULT TRUE,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS orders(
      id BIGSERIAL PRIMARY KEY,
      telegram_id BIGINT NOT NULL,
      product_id BIGINT REFERENCES products(id),
      amount BIGINT NOT NULL,
      payment_method TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending',
      authority TEXT UNIQUE,
      ref_id TEXT,
      receipt_file_id TEXT,
      receipt_data BYTEA,
      receipt_mime TEXT,
      receipt_size BIGINT NOT NULL DEFAULT 0,
      customer_name TEXT,
      customer_phone TEXT,
      discount_code TEXT,
      discount_amount BIGINT NOT NULL DEFAULT 0,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      paid_at TIMESTAMPTZ
    );
    CREATE TABLE IF NOT EXISTS discount_codes(
      id BIGSERIAL PRIMARY KEY,
      code TEXT UNIQUE NOT NULL,
      percent INTEGER NOT NULL DEFAULT 0 CHECK(percent BETWEEN 0 AND 100),
      amount BIGINT NOT NULL DEFAULT 0 CHECK(amount>=0),
      active BOOLEAN NOT NULL DEFAULT TRUE,
      usage_limit INTEGER,
      used_count INTEGER NOT NULL DEFAULT 0,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS categories(
      id BIGSERIAL PRIMARY KEY,
      title TEXT NOT NULL,
      emoji TEXT NOT NULL DEFAULT '🛍',
      active BOOLEAN NOT NULL DEFAULT TRUE,
      sort_order INTEGER NOT NULL DEFAULT 0,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS service_inventory(
      id BIGSERIAL PRIMARY KEY,
      product_id BIGINT REFERENCES products(id) ON DELETE CASCADE,
      payload TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'available',
      order_id BIGINT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      delivered_at TIMESTAMPTZ
    );
    CREATE TABLE IF NOT EXISTS wallet_transactions(
      id BIGSERIAL PRIMARY KEY,
      telegram_id BIGINT NOT NULL,
      amount BIGINT NOT NULL,
      kind TEXT NOT NULL,
      description TEXT,
      order_id BIGINT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS payment_gateways(
      id BIGSERIAL PRIMARY KEY,
      code TEXT UNIQUE NOT NULL,
      title TEXT NOT NULL,
      enabled BOOLEAN NOT NULL DEFAULT FALSE,
      config_json TEXT NOT NULL DEFAULT '{}',
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS app_settings(
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL DEFAULT '',
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS audit_logs(
      id BIGSERIAL PRIMARY KEY,
      actor TEXT NOT NULL,
      action TEXT NOT NULL,
      entity_type TEXT,
      entity_id TEXT,
      details TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS user_sessions(
      telegram_id BIGINT PRIMARY KEY,
      state_json TEXT NOT NULL DEFAULT '{}',
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS tickets(
      id BIGSERIAL PRIMARY KEY,
      telegram_id BIGINT NOT NULL,
      subject TEXT NOT NULL,
      body TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'open',
      admin_reply TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """)
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name TEXT")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS wallet_balance BIGINT NOT NULL DEFAULT 0")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_code TEXT")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_name TEXT")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_phone TEXT")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS discount_code TEXT")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS discount_amount BIGINT NOT NULL DEFAULT 0")

    cur.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS category_id BIGINT REFERENCES categories(id)")
    cur.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS emoji TEXT NOT NULL DEFAULT '💎'")
    cur.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS duration_label TEXT NOT NULL DEFAULT ''")
    cur.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS warranty_label TEXT NOT NULL DEFAULT ''")
    cur.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS auto_delivery BOOLEAN NOT NULL DEFAULT FALSE")
    cur.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS stock_mode TEXT NOT NULL DEFAULT 'manual'")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_payload TEXT")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMPTZ")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS receipt_data BYTEA")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS receipt_mime TEXT")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS receipt_size BIGINT NOT NULL DEFAULT 0")
    cur.execute("INSERT INTO payment_gateways(code,title,enabled) VALUES('zarinpal','زرین‌پال',FALSE) ON CONFLICT(code) DO NOTHING")
    cur.execute("INSERT INTO payment_gateways(code,title,enabled) VALUES('card','کارت‌به‌کارت',TRUE) ON CONFLICT(code) DO NOTHING")
    cur.execute("INSERT INTO payment_gateways(code,title,enabled) VALUES('wallet','کیف پول',TRUE) ON CONFLICT(code) DO NOTHING")
    cur.execute("INSERT INTO app_settings(key,value) VALUES('shop_title','ai-shop') ON CONFLICT(key) DO NOTHING")
    cur.execute("INSERT INTO app_settings(key,value) VALUES('support_text','پشتیبانی فروشگاه') ON CONFLICT(key) DO NOTHING")
    cur.execute("INSERT INTO app_settings(key,value) VALUES('premium_emoji_welcome_id','') ON CONFLICT(key) DO NOTHING")

    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO products(title,description,price,delivery_text) VALUES(%s,%s,%s,%s)",
            ("محصول آزمایشی هوش مصنوعی","این محصول را از پنل مدیریت ویرایش کنید.",10000,"تحویل آزمایشی محصول")
        )
    conn.commit(); cur.close(); conn.close()


def audit(action, entity_type="", entity_id="", details="", actor="admin"):
    try:
        conn=db(); cur=conn.cursor()
        cur.execute("INSERT INTO audit_logs(actor,action,entity_type,entity_id,details) VALUES(%s,%s,%s,%s,%s)",
                    (actor,action,entity_type,str(entity_id or ""),details))
        conn.commit(); cur.close(); conn.close()
    except Exception as exc:
        print("audit error",repr(exc))

def get_setting(key, default=""):
    conn=db(); cur=conn.cursor()
    cur.execute("SELECT value FROM app_settings WHERE key=%s",(key,))
    row=cur.fetchone(); cur.close(); conn.close()
    return row[0] if row else default

def deliver_order(order_id):
    conn=db(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""SELECT o.*,p.title,p.delivery_text,p.auto_delivery,p.stock_mode
                   FROM orders o LEFT JOIN products p ON p.id=o.product_id WHERE o.id=%s""",(order_id,))
    order=cur.fetchone()
    if not order:
        cur.close(); conn.close(); return False,"سفارش پیدا نشد"
    payload=order.get("delivery_payload") or ""
    if not payload and order.get("stock_mode")=="inventory":
        cur.execute("""SELECT id,payload FROM service_inventory
                       WHERE product_id=%s AND status='available' ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1""",
                    (order["product_id"],))
        inv=cur.fetchone()
        if inv:
            payload=inv["payload"]
            cur.execute("""UPDATE service_inventory SET status='delivered',order_id=%s,delivered_at=NOW()
                           WHERE id=%s""",(order_id,inv["id"]))
    if not payload:
        payload=order.get("delivery_text") or "سفارش شما تأیید شد؛ اطلاعات سرویس توسط پشتیبانی ارسال می‌شود."
    cur.execute("""UPDATE orders SET status='paid',delivery_payload=%s,paid_at=COALESCE(paid_at,NOW()),
                   delivered_at=NOW() WHERE id=%s""",(payload,order_id))
    conn.commit(); cur.close(); conn.close()
    tg("sendMessage",{"chat_id":order["telegram_id"],
       "text":f"✅ سفارش #{order_id} تأیید و تحویل شد.\n\n🛍 {order['title'] or ''}\n\n🔐 اطلاعات سرویس:\n{payload}"})
    audit("deliver_order","order",order_id,"automatic/manual delivery")
    return True,payload

class TelegramAPIError(RuntimeError):
    def __init__(self, method, status, body):
        super().__init__(f"Telegram {method} HTTP {status}: {body}")
        self.method=method; self.status=status; self.body=body

def http_json(url, data, label="HTTP"):
    req=urllib.request.Request(url,data=json.dumps(data,ensure_ascii=False).encode("utf-8"),headers={"Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body=exc.read().decode("utf-8","replace")
        raise TelegramAPIError(label,exc.code,body) from exc

def tg(method, payload):
    if not BOT_TOKEN: raise RuntimeError("TELEGRAM_BOT_TOKEN is empty")
    out=http_json(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",payload,method)
    if not out.get("ok"): raise TelegramAPIError(method,200,json.dumps(out,ensure_ascii=False))
    return out.get("result")

def tg_safe(method,payload):
    try: return tg(method,payload)
    except TelegramAPIError as exc:
        print("telegram api error:",exc)
        audit("telegram_error",method,"",str(exc),actor="system")
        return None

def money(n):
    return f"{int(n):,} ریال"

def main_keyboard(is_admin=False):
    rows=[
      [{"text":"💎 خرید اکانت و سرویس","callback_data":"products"}],
      [{"text":"✨ خرید ارزان‌تر","callback_data":"cheap_products"},{"text":"💳 کیف پول","callback_data":"wallet"}],
      [{"text":"👤 حساب من","callback_data":"account"},{"text":"🧷 دعوت دوستان","callback_data":"referral"}],
      [{"text":"📦 سفارش‌های من","callback_data":"orders"},{"text":"📨 پشتیبانی","callback_data":"ticket"}]
    ]
    if is_admin: rows.append([{"text":"⚙️ مدیریت ai-shop","callback_data":"adm:menu"}])
    return {"inline_keyboard":rows}

def admin_keyboard():
    return {"inline_keyboard":[
      [{"text":"📊 آمار ربات","callback_data":"adm:stats"}],
      [
        {"text":"📈 وضعیت‌ها","callback_data":"adm:status"},
        {"text":"⚙️ تنظیمات","callback_data":"adm:settings"}
      ],
      [{"text":"🖥 پنل مدیریت تحت وب","url":f"{PUBLIC_URL}/admin"}],
      [{"text":"🎨 شخصی‌سازی","callback_data":"adm:customize"}],
      [
        {"text":"🛍 محصولات","callback_data":"adm:products"},
        {"text":"📦 سفارش‌ها","callback_data":"adm:orders"}
      ],
      [
        {"text":"👥 کاربران","callback_data":"adm:users"},
        {"text":"💰 کیف پول","callback_data":"adm:wallet"}
      ],
      [
        {"text":"🎟 تخفیف‌ها","callback_data":"adm:discounts"},
        {"text":"🧾 رسیدها","callback_data":"adm:receipts"}
      ],
      [
        {"text":"📢 پیام همگانی","callback_data":"adm:broadcast"},
        {"text":"📬 ارسال به کاربر","callback_data":"adm:send_user"}
      ],
      [
        {"text":"💳 درگاه‌ها","callback_data":"adm:gateway"},
        {"text":"🔑 موجودی سرویس","callback_data":"adm:inventory"}
      ],
      [
        {"text":"🗄 دیتابیس","url":f"{PUBLIC_URL}/admin/database"},
        {"text":"💾 بکاپ","callback_data":"adm:backup"}
      ],
      [
        {"text":"📑 گزارش‌ها","callback_data":"adm:reports"},
        {"text":"📋 لاگ سیستم","callback_data":"adm:logs"}
      ],
      [
        {"text":"🔄 بروزرسانی","callback_data":"adm:update"},
        {"text":"🩺 سلامت سیستم","callback_data":"adm:health"}
      ],
      [
        {"text":"🔐 رمز پنل وب","callback_data":"adm:panel_password"},
        {"text":"📚 راهنما","url":f"{PUBLIC_URL}/admin/help"}
      ],
      [{"text":"❌ بستن","callback_data":"adm:close"}],
      [{"text":"🏠 منوی اصلی","callback_data":"home"}]
    ]}

def admin_back_keyboard():
    return {"inline_keyboard":[
      [{"text":"⬅️ بازگشت به پنل مدیریت","callback_data":"adm:menu"}],
      [{"text":"🏠 منوی اصلی","callback_data":"home"}]
    ]}

def admin_bottom_keyboard():
    return {
      "keyboard":[
        [
          {"text":"👥 بخش ادمین‌ها"},
          {"text":"👨‍💼 مدیریت کاربران"}
        ],
        [{"text":"♻️ پیام همگانی"}],
        [
          {"text":"🎁 بخش تخفیفات"},
          {"text":"🚦 بخش راهنماها"}
        ],
        [
          {"text":"🔒 بخش جوین اجباری"},
          {"text":"💳 بخش درگاه‌ها"}
        ],
        [
          {"text":"🔐 رمز پنل وب"},
          {"text":"🖥 پنل مدیریت وب"}
        ],
        [{"text":"⬅️ بازگشت"}]
      ],
      "resize_keyboard":True,
      "one_time_keyboard":False,
      "is_persistent":True,
      "input_field_placeholder":"یک بخش مدیریتی را انتخاب کنید"
    }

def remove_bottom_keyboard():
    return {"remove_keyboard":True}

def send_panel_credentials(chat_id):
    text=(
      "🔐 اطلاعات ورود پنل مدیریت\n\n"
      f"🌐 آدرس: {PUBLIC_URL}/admin\n"
      f"👤 نام کاربری: {ADMIN_USER}\n"
      f"🔑 رمز عبور: {ADMIN_PASS}\n\n"
      "⚠️ این پیام محرمانه است و فقط برای مدیر ربات نمایش داده شده."
    )
    return tg("sendMessage",{
      "chat_id":chat_id,
      "text":text,
      "protect_content":True,
      "reply_markup":admin_bottom_keyboard()
    })

def admin_users_text():
    rows=admin_text_list("""SELECT telegram_id,username,full_name,wallet_balance
      FROM users ORDER BY created_at DESC LIMIT 20""")
    if not rows:
        return "👨‍💼 هنوز کاربری ثبت نشده است."
    body="\n".join(
      f"• {r['telegram_id']} | @{r['username'] or '-'} | {r['full_name'] or '-'} | {money(r['wallet_balance'] or 0)}"
      for r in rows
    )
    return "👨‍💼 آخرین کاربران\n\n"+body

def admin_discounts_text():
    rows=admin_text_list("""SELECT code,percent,amount,active,used_count
      FROM discount_codes ORDER BY id DESC LIMIT 20""")
    if not rows:
        return "🎁 هنوز کد تخفیفی ساخته نشده است."
    body="\n".join(
      f"• {r['code']} | {r['percent']}٪ | {money(r['amount'] or 0)} | مصرف {r['used_count']} | {'فعال' if r['active'] else 'غیرفعال'}"
      for r in rows
    )
    return "🎁 کدهای تخفیف\n\n"+body

def server_status_text():
    try:
        load1,load5,load15=os.getloadavg()
    except Exception:
        load1=load5=load15=0
    disk=shutil.disk_usage("/")
    mem_total=mem_available=0
    try:
        values={}
        with open("/proc/meminfo","r",encoding="utf-8") as f:
            for line in f:
                key,val=line.split(":",1)
                values[key]=int(val.strip().split()[0])*1024
        mem_total=values.get("MemTotal",0)
        mem_available=values.get("MemAvailable",0)
    except Exception:
        pass
    mem_used=max(mem_total-mem_available,0)
    def gb(v): return round(v/1024/1024/1024,2)
    def pct(a,b): return round((a/b)*100,1) if b else 0
    service=subprocess.run(
        ["systemctl","is-active","ai-shop"],
        capture_output=True,text=True
    ).stdout.strip() or "unknown"
    return (
      "📈 وضعیت سرور و سرویس‌ها\n\n"
      f"🤖 سرویس ai-shop: {service}\n"
      f"🧠 RAM: {gb(mem_used)} / {gb(mem_total)} GB ({pct(mem_used,mem_total)}%)\n"
      f"💽 Disk: {gb(disk.used)} / {gb(disk.total)} GB ({pct(disk.used,disk.total)}%)\n"
      f"⚙️ Load: {load1:.2f} / {load5:.2f} / {load15:.2f}\n"
      f"🔖 نسخه: {APP_VERSION}"
    )

def send_main(chat_id, uid=None):
    is_admin=str(uid or chat_id)==str(ADMIN_ID)
    tg("sendMessage", {"chat_id":chat_id,"text":"✨ به AI-SHOP خوش آمدید.\nفروشگاه محصولات و خدمات هوش مصنوعی","reply_markup":main_keyboard(is_admin)})

def send_admin_menu(chat_id):
    tg("sendMessage",{
      "chat_id":chat_id,
      "text":"🛡 پنل مدیریت ai-shop\n\nمنوی مدیریتی در پایین صفحه باز شد. بخش موردنظر را انتخاب کنید.",
      "reply_markup":admin_bottom_keyboard()
    })

def upsert_user(frm):
    if not frm or not frm.get("id"): return
    conn=db(); cur=conn.cursor()
    cur.execute("""
      INSERT INTO users(telegram_id,username,first_name)
      VALUES(%s,%s,%s)
      ON CONFLICT(telegram_id) DO UPDATE SET username=EXCLUDED.username,first_name=EXCLUDED.first_name
    """,(frm["id"],frm.get("username"),frm.get("first_name")))
    cur.execute("UPDATE users SET referral_code=COALESCE(referral_code,%s) WHERE telegram_id=%s",(f"AI{frm['id']}",frm['id']))
    conn.commit(); cur.close(); conn.close()

def show_products(chat_id):
    conn=db(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM products WHERE active=true ORDER BY id")
    rows=cur.fetchall(); cur.close(); conn.close()
    if not rows:
        tg("sendMessage",{"chat_id":chat_id,"text":"محصول فعالی وجود ندارد."}); return
    kb=[[{"text":f"{r['title']} — {money(r['price'])}","callback_data":f"product:{r['id']}"}] for r in rows]
    tg("sendMessage",{"chat_id":chat_id,"text":"محصول را انتخاب کنید:","reply_markup":{"inline_keyboard":kb}})

def product_details(chat_id, product_id):
    conn=db(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM products WHERE id=%s AND active=true",(product_id,))
    p=cur.fetchone(); cur.close(); conn.close()
    if not p: return
    tg("sendMessage",{
      "chat_id":chat_id,
      "text":f"💎 {p['title']}\n\n💰 قیمت: {money(p['price'])}\n\n{p['description']}\n\nبرای ادامه خرید، دکمه زیر را بزنید.",
      "reply_markup":{"inline_keyboard":[
        [{"text":"✅ ادامه خرید","callback_data":f"order:start:{p['id']}"}],
        [{"text":"🔙 بازگشت به محصولات","callback_data":"products"}]
      ]}
    })

def discount_for(code_text, price):
    if not code_text: return None,0
    conn=db(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM discount_codes WHERE UPPER(code)=UPPER(%s) AND active=true AND (usage_limit IS NULL OR used_count<usage_limit)",(code_text,))
    row=cur.fetchone(); cur.close(); conn.close()
    if not row: return None,0
    amount=max(int(row['amount'] or 0), int(price)*int(row['percent'] or 0)//100)
    return row,min(amount,int(price))

def create_order(telegram_id, product_id, method, customer_name="", customer_phone="", discount_code="", discount_amount=0):
    conn=db(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM products WHERE id=%s AND active=true",(product_id,))
    p=cur.fetchone()
    if not p:
        cur.close(); conn.close(); raise RuntimeError("Product not found")
    cur.execute("""
      INSERT INTO orders(telegram_id,product_id,amount,payment_method,customer_name,customer_phone,discount_code,discount_amount)
      VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *
    """,(telegram_id,p["id"],max(0,int(p["price"])-int(discount_amount)),method,customer_name,customer_phone,discount_code,discount_amount))
    o=cur.fetchone(); conn.commit(); cur.close(); conn.close()
    return o,p

def zarinpal_endpoints():
    if os.getenv("ZARINPAL_SANDBOX","true").lower()=="true":
        return (
            "https://sandbox.zarinpal.com/pg/v4/payment/request.json",
            "https://sandbox.zarinpal.com/pg/v4/payment/verify.json",
            "https://sandbox.zarinpal.com/pg/StartPay/"
        )
    return (
        "https://payment.zarinpal.com/pg/v4/payment/request.json",
        "https://payment.zarinpal.com/pg/v4/payment/verify.json",
        "https://www.zarinpal.com/pg/StartPay/"
    )

def create_payment(amount, callback_url, description):
    req_url,_,start_url=zarinpal_endpoints()
    out=http_json(req_url,{
      "merchant_id":os.getenv("ZARINPAL_MERCHANT_ID",""),
      "amount":int(amount),
      "callback_url":callback_url,
      "description":description,
      "currency":CURRENCY
    })
    authority=((out.get("data") or {}).get("authority"))
    if not authority: raise RuntimeError(str(out))
    return authority,start_url+authority

def verify_payment(amount, authority):
    _,verify_url,_=zarinpal_endpoints()
    out=http_json(verify_url,{
      "merchant_id":os.getenv("ZARINPAL_MERCHANT_ID",""),
      "amount":int(amount),
      "authority":authority
    })
    data=out.get("data") or {}
    code=data.get("code")
    return code in (100,101), code, str(data.get("ref_id") or "")

def admin_allowed(uid):
    return str(uid)==str(ADMIN_ID)

def admin_text_list(query, params=()):
    conn=db(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(query,params); rows=cur.fetchall(); cur.close(); conn.close(); return rows

def handle_admin_menu(q):
    uid=q["from"]["id"]; chat_id=q["message"]["chat"]["id"]; data=q.get("data","")
    if not admin_allowed(uid):
        return tg("answerCallbackQuery",{
          "callback_query_id":q["id"],
          "text":"دسترسی ندارید",
          "show_alert":True
        })
    tg("answerCallbackQuery",{"callback_query_id":q["id"]})

    if data=="adm:menu": return send_admin_menu(chat_id)
    if data=="adm:close":
        tg("sendMessage",{
          "chat_id":chat_id,
          "text":"پنل مدیریت بسته شد.",
          "reply_markup":remove_bottom_keyboard()
        })
        return tg("editMessageText",{
          "chat_id":chat_id,
          "message_id":q["message"]["message_id"],
          "text":"پنل مدیریت بسته شد."
        })

    if data=="adm:panel_password":
        return send_panel_credentials(chat_id)

    if data in ("adm:stats","adm:reports"):
        conn=db(); cur=conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users"); users=cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM products WHERE active=true"); products=cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM orders"); orders=cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM orders WHERE status='paid'"); paid=cur.fetchone()[0]
        cur.execute("SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='paid'"); sales=cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM tickets WHERE status='open'"); tickets=cur.fetchone()[0]
        cur.close(); conn.close()
        return tg("sendMessage",{
          "chat_id":chat_id,
          "text":(
            "📊 آمار و گزارش ai-shop\n\n"
            f"👥 کاربران: {users:,}\n"
            f"🛍 محصولات فعال: {products:,}\n"
            f"📦 کل سفارش‌ها: {orders:,}\n"
            f"✅ سفارش موفق: {paid:,}\n"
            f"💰 فروش موفق: {money(sales)}\n"
            f"🎫 تیکت باز: {tickets:,}\n\n"
            f"🔖 نسخه: {APP_VERSION}"
          ),
          "reply_markup":admin_back_keyboard()
        })

    if data in ("adm:status","adm:health"):
        return tg("sendMessage",{
          "chat_id":chat_id,
          "text":server_status_text(),
          "reply_markup":admin_back_keyboard()
        })

    if data=="adm:products":
        rows=admin_text_list("SELECT id,title,price,active FROM products ORDER BY id DESC LIMIT 30")
        text="\n".join(
          f"#{r['id']} | {r['title']} | {money(r['price'])} | {'فعال' if r['active'] else 'غیرفعال'}"
          for r in rows
        ) or "محصولی نیست."
        return tg("sendMessage",{
          "chat_id":chat_id,
          "text":"🛍 محصولات\n\n"+text,
          "reply_markup":{"inline_keyboard":[
            [{"text":"➕ محصول جدید","callback_data":"adm:add_product"}],
            [{"text":"🌐 مدیریت کامل در وب","url":f"{PUBLIC_URL}/admin#products"}],
            [{"text":"⬅️ بازگشت","callback_data":"adm:menu"}]
          ]}
        })

    if data=="adm:add_product":
        STATE[uid]={"step":"admin_product_title"}
        return tg("sendMessage",{
          "chat_id":chat_id,
          "text":"➕ عنوان محصول جدید را ارسال کنید."
        })

    if data=="adm:orders":
        rows=admin_text_list("""SELECT o.id,o.telegram_id,o.amount,o.status,p.title
          FROM orders o LEFT JOIN products p ON p.id=o.product_id
          ORDER BY o.id DESC LIMIT 30""")
        text="\n".join(
          f"#{r['id']} | {r['title'] or '-'} | {r['status']} | {money(r['amount'])}"
          for r in rows
        ) or "سفارشی نیست."
        return tg("sendMessage",{
          "chat_id":chat_id,
          "text":"📦 سفارش‌ها\n\n"+text,
          "reply_markup":{"inline_keyboard":[
            [{"text":"🌐 مدیریت سفارش‌ها","url":f"{PUBLIC_URL}/admin#orders"}],
            [{"text":"⬅️ بازگشت","callback_data":"adm:menu"}]
          ]}
        })

    if data=="adm:receipts":
        rows=admin_text_list("""SELECT id,telegram_id,amount,status
          FROM orders WHERE receipt_file_id IS NOT NULL
          ORDER BY id DESC LIMIT 30""")
        text="\n".join(
          f"#{r['id']} | کاربر {r['telegram_id']} | {money(r['amount'])} | {r['status']}"
          for r in rows
        ) or "رسیدی نیست."
        return tg("sendMessage",{
          "chat_id":chat_id,
          "text":"🧾 رسیدها\n\n"+text,
          "reply_markup":{"inline_keyboard":[
            [{"text":"🌐 مشاهده رسیدها","url":f"{PUBLIC_URL}/admin#orders"}],
            [{"text":"⬅️ بازگشت","callback_data":"adm:menu"}]
          ]}
        })

    if data=="adm:users":
        rows=admin_text_list("""SELECT telegram_id,full_name,wallet_balance
          FROM users ORDER BY created_at DESC LIMIT 30""")
        text="\n".join(
          f"{r['telegram_id']} | {r['full_name'] or '-'} | {money(r['wallet_balance'])}"
          for r in rows
        ) or "کاربری نیست."
        return tg("sendMessage",{
          "chat_id":chat_id,
          "text":"👥 کاربران جدید\n\n"+text,
          "reply_markup":admin_back_keyboard()
        })

    if data=="adm:wallet":
        rows=admin_text_list("""SELECT telegram_id,wallet_balance
          FROM users ORDER BY wallet_balance DESC LIMIT 20""")
        text="\n".join(
          f"{r['telegram_id']} | {money(r['wallet_balance'])}"
          for r in rows
        ) or "اطلاعاتی نیست."
        return tg("sendMessage",{
          "chat_id":chat_id,
          "text":"💰 بالاترین موجودی کیف پول\n\n"+text,
          "reply_markup":admin_back_keyboard()
        })

    if data=="adm:discounts":
        rows=admin_text_list("""SELECT code,percent,amount,active,used_count
          FROM discount_codes ORDER BY id DESC LIMIT 30""")
        text="\n".join(
          f"{r['code']} | {r['percent']}٪ | {money(r['amount'])} | مصرف {r['used_count']} | {'فعال' if r['active'] else 'غیرفعال'}"
          for r in rows
        ) or "کد تخفیفی نیست."
        return tg("sendMessage",{
          "chat_id":chat_id,
          "text":"🎟 کدهای تخفیف\n\n"+text,
          "reply_markup":admin_back_keyboard()
        })

    if data=="adm:broadcast":
        STATE[uid]={"step":"admin_broadcast"}
        return tg("sendMessage",{
          "chat_id":chat_id,
          "text":"📢 متن پیام همگانی را ارسال کنید.\nبرای لغو /cancel را بفرستید."
        })

    if data=="adm:send_user":
        return tg("sendMessage",{
          "chat_id":chat_id,
          "text":"📬 ارسال به کاربر\n\nاین قابلیت در پنل وب با جستجوی کاربر و ثبت لاگ مدیریتی انجام می‌شود.",
          "reply_markup":{"inline_keyboard":[
            [{"text":"🌐 بازکردن پنل کاربران","url":f"{PUBLIC_URL}/admin"}],
            [{"text":"⬅️ بازگشت","callback_data":"adm:menu"}]
          ]}
        })

    if data=="adm:gateway":
        mode='آزمایشی' if os.getenv('ZARINPAL_SANDBOX','true').lower()=='true' else 'واقعی'
        merchant='تنظیم شده' if os.getenv('ZARINPAL_MERCHANT_ID','') else 'تنظیم نشده'
        card='تنظیم شده' if os.getenv('CARD_NUMBER','') else 'تنظیم نشده'
        return tg("sendMessage",{
          "chat_id":chat_id,
          "text":f"💳 درگاه‌ها\n\nزرین‌پال: {merchant}\nحالت: {mode}\nکارت‌به‌کارت: {card}\nکیف پول: فعال",
          "reply_markup":admin_back_keyboard()
        })

    if data=="adm:inventory":
        rows=admin_text_list("""SELECT i.id,i.status,p.title
          FROM service_inventory i
          LEFT JOIN products p ON p.id=i.product_id
          ORDER BY i.id DESC LIMIT 30""")
        text="\n".join(
          f"#{r['id']} | {r['title'] or '-'} | {r['status']}"
          for r in rows
        ) or "موجودی ثبت نشده است."
        return tg("sendMessage",{
          "chat_id":chat_id,
          "text":"🔑 موجودی سرویس\n\n"+text,
          "reply_markup":{"inline_keyboard":[
            [{"text":"🌐 مدیریت موجودی","url":f"{PUBLIC_URL}/admin#inventory"}],
            [{"text":"⬅️ بازگشت","callback_data":"adm:menu"}]
          ]}
        })

    if data=="adm:settings":
        return tg("sendMessage",{
          "chat_id":chat_id,
          "text":f"⚙️ تنظیمات ai-shop\n\nدامنه: {DOMAIN}\nپنل وب: {PUBLIC_URL}/admin\nشناسه مدیر: {ADMIN_ID}",
          "reply_markup":{"inline_keyboard":[
            [{"text":"⚙️ تنظیمات وب","url":f"{PUBLIC_URL}/admin#settings"}],
            [{"text":"⬅️ بازگشت","callback_data":"adm:menu"}]
          ]}
        })

    if data=="adm:customize":
        return tg("sendMessage",{
          "chat_id":chat_id,
          "text":"🎨 شخصی‌سازی\n\nعنوان فروشگاه، متن‌ها و Custom Emoji ID را در پنل وب تنظیم کنید.",
          "reply_markup":{"inline_keyboard":[
            [{"text":"🎨 شخصی‌سازی در وب","url":f"{PUBLIC_URL}/admin#settings"}],
            [{"text":"⬅️ بازگشت","callback_data":"adm:menu"}]
          ]}
        })

    if data=="adm:backup":
        return tg("sendMessage",{
          "chat_id":chat_id,
          "text":"💾 بکاپ امن\n\nبرای جلوگیری از اجرای دستور سیستمی از تلگرام، روی سرور اجرا کنید:\n\ncd ~/ai-shop\nsudo bash backup.sh",
          "reply_markup":admin_back_keyboard()
        })

    if data=="adm:logs":
        try:
            logs=subprocess.run(
              ["journalctl","-u","ai-shop","-n","20","--no-pager"],
              capture_output=True,text=True,timeout=8
            ).stdout[-3500:]
        except Exception as exc:
            logs=str(exc)
        return tg("sendMessage",{
          "chat_id":chat_id,
          "text":"📋 آخرین لاگ‌های سرویس\n\n"+logs,
          "reply_markup":admin_back_keyboard()
        })

    if data=="adm:update":
        return tg("sendMessage",{
          "chat_id":chat_id,
          "text":"🔄 بروزرسانی امن\n\nروی سرور اجرا کنید:\n\ncd ~/ai-shop\nsudo bash remote-update.sh",
          "reply_markup":admin_back_keyboard()
        })

    if data=="adm:tickets":
        rows=admin_text_list("SELECT id,telegram_id,subject,status FROM tickets ORDER BY id DESC LIMIT 30")
        text="\n".join(
          f"#{r['id']} | {r['subject']} | {r['status']} | کاربر {r['telegram_id']}"
          for r in rows
        ) or "تیکتی نیست."
        return tg("sendMessage",{
          "chat_id":chat_id,
          "text":"🎫 تیکت‌ها\n\n"+text,
          "reply_markup":admin_back_keyboard()
        })

def handle_callback(q):
    chat_id=q["message"]["chat"]["id"]; data=q.get("data","")
    if data.startswith("adm:"): return handle_admin_menu(q)
    tg("answerCallbackQuery",{"callback_query_id":q["id"]})
    if data=="home": return send_main(chat_id,q["from"]["id"])
    if data=="payment_info": return tg("sendMessage",{"chat_id":chat_id,"text":"💳 پرداخت آنلاین زرین‌پال و کارت‌به‌کارت در AI-SHOP فعال است."})
    if data=="help": return tg("sendMessage",{"chat_id":chat_id,"text":"راهنما: محصول را انتخاب کنید، روش پرداخت را بزنید و پس از پرداخت محصول تحویل می‌شود."})
    if data=="wallet":
        conn=db(); cur=conn.cursor(); cur.execute("SELECT wallet_balance FROM users WHERE telegram_id=%s",(q["from"]["id"],)); row=cur.fetchone(); cur.close(); conn.close()
        bal=row[0] if row else 0
        return tg("sendMessage",{"chat_id":chat_id,"text":f"💳 کیف پول شما\n\nموجودی: {money(bal)}","reply_markup":{"inline_keyboard":[[{"text":"➕ شارژ کیف پول","callback_data":"wallet:charge"}],[{"text":"🏠 منوی اصلی","callback_data":"home"}]]}})
    if data=="wallet:charge":
        return tg("sendMessage",{"chat_id":chat_id,"text":f"برای شارژ کیف پول به کارت زیر واریز و رسید را برای پشتیبانی بفرستید:\n\n{os.getenv('CARD_NUMBER','تنظیم نشده')}\nبه نام {os.getenv('CARD_HOLDER','-')}"})
    if data=="account":
        conn=db(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor); cur.execute("SELECT * FROM users WHERE telegram_id=%s",(q["from"]["id"],)); u=cur.fetchone(); cur.close(); conn.close()
        return tg("sendMessage",{"chat_id":chat_id,"text":f"👤 حساب من\n\nنام: {(u or {}).get('full_name') or (u or {}).get('first_name') or '-'}\nتلفن: {(u or {}).get('phone') or '-'}\nموجودی: {money((u or {}).get('wallet_balance') or 0)}"})
    if data=="referral":
        code_ref=f"AI{q['from']['id']}"
        return tg("sendMessage",{"chat_id":chat_id,"text":f"🧷 کد دعوت شما: {code_ref}\nاین کد را برای دوستانتان ارسال کنید."})
    if data=="cheap_products": return show_products(chat_id)
    if data.startswith("order:start:"):
        pid=data.split(":")[2]; STATE[q["from"]["id"]]={"step":"checkout_name","product_id":pid}
        return tg("sendMessage",{"chat_id":chat_id,"text":"👤 نام و نام خانوادگی را ارسال کنید.","reply_markup":{"inline_keyboard":[[{"text":"🏠 منوی اصلی","callback_data":"home"}]]}})
    if data.startswith("checkout:discount:"):
        answer=data.split(":")[2]; s=STATE.get(q["from"]["id"])
        if not s: return send_main(chat_id,q["from"]["id"])
        if answer=="no": s["discount_code"]=""; s["discount_amount"]=0; return send_checkout_confirmation(chat_id,q["from"]["id"])
        s["step"]="checkout_discount"; return tg("sendMessage",{"chat_id":chat_id,"text":"🎟 کد تخفیف را ارسال کنید."})
    if data=="checkout:confirm":
        s=STATE.get(q["from"]["id"]);
        if not s: return send_main(chat_id,q["from"]["id"])
        s["step"]="payment_choice"
        return tg("sendMessage",{"chat_id":chat_id,"text":"روش پرداخت را انتخاب کنید:","reply_markup":{"inline_keyboard":[[{"text":"💳 زرین‌پال","callback_data":"checkout:pay:zarinpal"}],[{"text":"🏦 کارت‌به‌کارت","callback_data":"checkout:pay:card"}],[{"text":"💰 کیف پول","callback_data":"checkout:pay:wallet"}],[{"text":"❌ لغو","callback_data":"checkout:cancel"}]]}})
    if data=="checkout:cancel": STATE.pop(q["from"]["id"],None); return send_main(chat_id,q["from"]["id"])
    if data.startswith("checkout:pay:"):
        method=data.split(":")[2]; s=STATE.get(q["from"]["id"]);
        if not s: return send_main(chat_id,q["from"]["id"])
        o,p=create_order(q["from"]["id"],s["product_id"],method,s.get("name",""),s.get("phone",""),s.get("discount_code",""),s.get("discount_amount",0))
        if method=="wallet":
            conn=db(); cur=conn.cursor(); cur.execute("SELECT wallet_balance FROM users WHERE telegram_id=%s FOR UPDATE",(q["from"]["id"],)); bal=cur.fetchone()[0]
            if bal<o["amount"]: conn.rollback(); cur.close(); conn.close(); return tg("sendMessage",{"chat_id":chat_id,"text":"❌ موجودی کیف پول کافی نیست."})
            cur.execute("UPDATE users SET wallet_balance=wallet_balance-%s WHERE telegram_id=%s",(o["amount"],q["from"]["id"])); cur.execute("UPDATE orders SET status='paid',paid_at=NOW() WHERE id=%s",(o["id"],)); conn.commit(); cur.close(); conn.close(); STATE.pop(q["from"]["id"],None)
            return deliver_order(o["id"])
        if method=="zarinpal":
            authority,url=create_payment(o["amount"],f"{PUBLIC_URL}/payment/callback?order_id={o['id']}",f"خرید {p['title']} - سفارش {o['id']}")
            conn=db(); cur=conn.cursor(); cur.execute("UPDATE orders SET authority=%s WHERE id=%s",(authority,o["id"])); conn.commit(); cur.close(); conn.close(); STATE.pop(q["from"]["id"],None)
            return tg("sendMessage",{"chat_id":chat_id,"text":f"سفارش #{o['id']} ایجاد شد.","reply_markup":{"inline_keyboard":[[{"text":"💳 ورود به درگاه","url":url}]]}})
        STATE[q["from"]["id"]]={"step":"card_receipt","order_id":o["id"]}
        return tg("sendMessage",{"chat_id":chat_id,"text":f"سفارش #{o['id']}\nمبلغ: {money(o['amount'])}\n\nشماره کارت: {os.getenv('CARD_NUMBER','تنظیم نشده')}\nبه نام: {os.getenv('CARD_HOLDER','-')}\n\nتصویر رسید را ارسال کنید."})
    if data=="products": return show_products(chat_id)
    if data=="orders":
        conn=db(); cur=conn.cursor()
        cur.execute("""SELECT o.id,o.status,o.amount,p.title FROM orders o
          LEFT JOIN products p ON p.id=o.product_id
          WHERE o.telegram_id=%s ORDER BY o.id DESC LIMIT 10""",(q["from"]["id"],))
        rows=cur.fetchall(); cur.close(); conn.close()
        text="\n".join([f"#{r[0]} | {r[3] or '-'} | {r[1]} | {money(r[2])}" for r in rows]) or "سفارشی ندارید."
        return tg("sendMessage",{"chat_id":chat_id,"text":text})
    if data=="ticket":
        STATE[q["from"]["id"]]={"step":"ticket_subject"}
        return tg("sendMessage",{"chat_id":chat_id,"text":"موضوع تیکت را ارسال کنید."})
    if data.startswith("product:"):
        return product_details(chat_id,data.split(":")[1])

def send_checkout_confirmation(chat_id, uid):
    s=STATE.get(uid);
    if not s: return send_main(chat_id,uid)
    conn=db(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor); cur.execute("SELECT * FROM products WHERE id=%s",(s["product_id"],)); p=cur.fetchone(); cur.close(); conn.close()
    final=max(0,int(p["price"])-int(s.get("discount_amount",0)))
    s["step"]="checkout_confirm"
    tg("sendMessage",{"chat_id":chat_id,"text":f"🌟 تأیید سفارش\n\nپلن: {p['title']}\nقیمت: {money(p['price'])}\nتخفیف: {money(s.get('discount_amount',0))}\nپرداخت نهایی: {money(final)}\nنام: {s.get('name','-')}\nتلفن: {s.get('phone','-')}\n\nاگر اطلاعات درست است، تأیید کنید.","reply_markup":{"inline_keyboard":[[{"text":"✅ تأیید","callback_data":"checkout:confirm"},{"text":"❌ لغو","callback_data":"checkout:cancel"}],[{"text":"🏠 منوی اصلی","callback_data":"home"}]]}})

def deliver_order(order_id):
    conn=db(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""SELECT o.*,p.title,p.delivery_text FROM orders o LEFT JOIN products p ON p.id=o.product_id WHERE o.id=%s""",(order_id,)); o=cur.fetchone(); cur.close(); conn.close()
    if not o: return
    text=f"✅ سفارش #{order_id} تأیید شد.\n\nمحصول: {o['title']}\n\n📦 اطلاعات سرویس خریداری‌شده:\n{o['delivery_text'] or 'اطلاعات سرویس به‌زودی توسط پشتیبانی ارسال می‌شود.'}"
    return tg("sendMessage",{"chat_id":o["telegram_id"],"text":text})

def telegram_file_bytes(file_id):
    meta=tg("getFile",{"file_id":file_id}); path=meta.get("file_path")
    if not path: raise RuntimeError("Telegram file path missing")
    with urllib.request.urlopen(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{path}",timeout=30) as r:
        return r.read(), (r.headers.get_content_type() or "image/jpeg")

def handle_admin_callback(q):
    if str(q["from"]["id"]) != str(ADMIN_ID): return
    _,action,order_id=q["data"].split(":")
    conn=db(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""SELECT o.*,p.delivery_text FROM orders o
      LEFT JOIN products p ON p.id=o.product_id WHERE o.id=%s""",(order_id,))
    o=cur.fetchone()
    if not o: cur.close(); conn.close(); return
    if action=="approve":
        cur.execute("UPDATE orders SET status='paid',paid_at=NOW() WHERE id=%s",(order_id,))
        conn.commit()
        deliver_order(order_id)
    else:
        cur.execute("UPDATE orders SET status='rejected' WHERE id=%s",(order_id,))
        conn.commit()
        tg("sendMessage",{"chat_id":o["telegram_id"],"text":f"رسید سفارش #{order_id} رد شد."})
    cur.close(); conn.close()
    tg("answerCallbackQuery",{"callback_query_id":q["id"],"text":"انجام شد"})

def download_telegram_file(file_id):
    info=tg("getFile",{"file_id":file_id})
    file_path=info.get("file_path")
    if not file_path: raise RuntimeError("Telegram file_path missing")
    with urllib.request.urlopen(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}",timeout=30) as response:
        data=response.read(15*1024*1024+1)
        if len(data)>15*1024*1024: raise RuntimeError("Receipt file is larger than 15MB")
        return data,response.headers.get_content_type() or "image/jpeg"

def handle_message(msg):
    upsert_user(msg.get("from"))
    chat_id=msg["chat"]["id"]; uid=msg["from"]["id"]; text=msg.get("text","")

    if text in ("/start","/menu"):
        tg("sendMessage",{"chat_id":chat_id,"text":"منوی اصلی","reply_markup":remove_bottom_keyboard()})
        return send_main(chat_id,uid)

    if text in ("/admin","⚙️ مدیریت ai-shop") and admin_allowed(uid):
        return send_admin_menu(chat_id)

    if text=="/panelpass" and admin_allowed(uid):
        return send_panel_credentials(chat_id)

    if admin_allowed(uid):
        if text=="🔐 رمز پنل وب":
            return send_panel_credentials(chat_id)

        if text=="🖥 پنل مدیریت وب":
            return tg("sendMessage",{
              "chat_id":chat_id,
              "text":"🖥 ورود به پنل مدیریت وب:",
              "reply_markup":{"inline_keyboard":[[
                {"text":"ورود به پنل مدیریت","url":f"{PUBLIC_URL}/admin"}
              ]]}
            })

        if text=="👥 بخش ادمین‌ها":
            return tg("sendMessage",{
              "chat_id":chat_id,
              "text":(
                "👥 بخش ادمین‌ها\n\n"
                f"مدیر اصلی: {ADMIN_ID}\n"
                "سطح دسترسی: مدیر کل\n"
                "ورود مدیران دیگر در نسخه فعلی از پنل وب مدیریت می‌شود."
              ),
              "reply_markup":admin_bottom_keyboard()
            })

        if text=="👨‍💼 مدیریت کاربران":
            return tg("sendMessage",{
              "chat_id":chat_id,
              "text":admin_users_text(),
              "reply_markup":admin_bottom_keyboard()
            })

        if text=="♻️ پیام همگانی":
            STATE[uid]={"step":"admin_broadcast"}
            return tg("sendMessage",{
              "chat_id":chat_id,
              "text":"♻️ متن پیام همگانی را ارسال کنید.\nبرای لغو /cancel را بفرستید.",
              "reply_markup":admin_bottom_keyboard()
            })

        if text=="🎁 بخش تخفیفات":
            return tg("sendMessage",{
              "chat_id":chat_id,
              "text":admin_discounts_text(),
              "reply_markup":{"inline_keyboard":[
                [{"text":"مدیریت تخفیف‌ها در وب","url":f"{PUBLIC_URL}/admin#coupons"}]
              ]}
            })

        if text=="🚦 بخش راهنماها":
            return tg("sendMessage",{
              "chat_id":chat_id,
              "text":"🚦 راهنمای کامل نصب، آپدیت و مدیریت:",
              "reply_markup":{"inline_keyboard":[[
                {"text":"بازکردن راهنما","url":f"{PUBLIC_URL}/admin/help"}
              ]]}
            })

        if text=="💳 بخش درگاه‌ها":
            mode="آزمایشی" if os.getenv("ZARINPAL_SANDBOX","true").lower()=="true" else "واقعی"
            merchant="تنظیم شده" if os.getenv("ZARINPAL_MERCHANT_ID","") else "تنظیم نشده"
            card="تنظیم شده" if os.getenv("CARD_NUMBER","") else "تنظیم نشده"
            return tg("sendMessage",{
              "chat_id":chat_id,
              "text":(
                "💳 وضعیت درگاه‌ها\n\n"
                f"زرین‌پال: {merchant}\n"
                f"حالت زرین‌پال: {mode}\n"
                f"کارت‌به‌کارت: {card}\n"
                "کیف پول: فعال"
              ),
              "reply_markup":admin_bottom_keyboard()
            })

        if text=="🔒 بخش جوین اجباری":
            return tg("sendMessage",{
              "chat_id":chat_id,
              "text":(
                "🔒 جوین اجباری\n\n"
                "برای تنظیم کانال و فعال‌سازی این بخش، از تنظیمات پنل وب استفاده کنید."
              ),
              "reply_markup":{"inline_keyboard":[[
                {"text":"بازکردن تنظیمات","url":f"{PUBLIC_URL}/admin#settings"}
              ]]}
            })

        if text=="⬅️ بازگشت":
            tg("sendMessage",{
              "chat_id":chat_id,
              "text":"به منوی اصلی برگشتید.",
              "reply_markup":remove_bottom_keyboard()
            })
            return send_main(chat_id,uid)

    if text=="/cancel":
        STATE.pop(uid,None)
        if admin_allowed(uid):
            return send_admin_menu(chat_id)
        return send_main(chat_id,uid)

    s=STATE.get(uid)
    if not s: return send_main(chat_id,uid)
    if s["step"]=="ticket_subject" and text:
        STATE[uid]={"step":"ticket_body","subject":text}; return tg("sendMessage",{"chat_id":chat_id,"text":"متن تیکت را ارسال کنید."})
    if s["step"]=="ticket_body" and text:
        conn=db(); cur=conn.cursor(); cur.execute("INSERT INTO tickets(telegram_id,subject,body) VALUES(%s,%s,%s) RETURNING id",(uid,s["subject"],text)); tid=cur.fetchone()[0]; conn.commit(); cur.close(); conn.close(); STATE.pop(uid,None)
        return tg("sendMessage",{"chat_id":chat_id,"text":f"تیکت #{tid} ثبت شد."})
    if s["step"]=="checkout_name" and text:
        s["name"]=text.strip(); s["step"]="checkout_phone"
        return tg("sendMessage",{"chat_id":chat_id,"text":"📱 شماره تلفن را ارسال کنید."})
    if s["step"]=="checkout_phone" and text:
        phone=text.replace(" ","").replace("-","")
        if len(phone)<10: return tg("sendMessage",{"chat_id":chat_id,"text":"شماره تلفن معتبر نیست؛ دوباره ارسال کنید."})
        s["phone"]=phone; s["step"]="checkout_discount_question"
        conn=db(); cur=conn.cursor(); cur.execute("UPDATE users SET full_name=%s,phone=%s WHERE telegram_id=%s",(s["name"],phone,uid)); conn.commit(); cur.close(); conn.close()
        return tg("sendMessage",{"chat_id":chat_id,"text":"🎟 کد تخفیف دارید؟","reply_markup":{"inline_keyboard":[[{"text":"✅ بله","callback_data":"checkout:discount:yes"},{"text":"❌ خیر","callback_data":"checkout:discount:no"}],[{"text":"🏠 منوی اصلی","callback_data":"home"}]]}})
    if s["step"]=="checkout_discount" and text:
        conn=db(); cur=conn.cursor(); cur.execute("SELECT price FROM products WHERE id=%s",(s["product_id"],)); price=cur.fetchone()[0]; cur.close(); conn.close()
        row,amount=discount_for(text.strip(),price)
        if not row: return tg("sendMessage",{"chat_id":chat_id,"text":"کد تخفیف معتبر نیست. دوباره ارسال کنید یا /cancel بزنید."})
        s["discount_code"]=row["code"]; s["discount_amount"]=amount
        return send_checkout_confirmation(chat_id,uid)
    if admin_allowed(uid) and s["step"]=="admin_product_title" and text:
        STATE[uid]={"step":"admin_product_description","title":text}; return tg("sendMessage",{"chat_id":chat_id,"text":"توضیحات محصول را ارسال کنید."})
    if admin_allowed(uid) and s["step"]=="admin_product_description" and text:
        s["description"]=text; s["step"]="admin_product_price"; return tg("sendMessage",{"chat_id":chat_id,"text":"قیمت به ریال را فقط عددی ارسال کنید."})
    if admin_allowed(uid) and s["step"]=="admin_product_price" and text:
        try: price=int(text.replace(',','').strip())
        except: return tg("sendMessage",{"chat_id":chat_id,"text":"قیمت نامعتبر است؛ فقط عدد بفرستید."})
        s["price"]=price; s["step"]="admin_product_delivery"; return tg("sendMessage",{"chat_id":chat_id,"text":"متن تحویل محصول را ارسال کنید."})
    if admin_allowed(uid) and s["step"]=="admin_product_delivery" and text:
        conn=db(); cur=conn.cursor(); cur.execute("INSERT INTO products(title,description,price,delivery_text) VALUES(%s,%s,%s,%s) RETURNING id",(s['title'],s['description'],s['price'],text)); pid=cur.fetchone()[0]; conn.commit(); cur.close(); conn.close(); STATE.pop(uid,None)
        return tg("sendMessage",{"chat_id":chat_id,"text":f"✅ محصول #{pid} ثبت شد.","reply_markup":admin_keyboard()})
    if admin_allowed(uid) and s["step"]=="admin_broadcast" and text:
        rows=admin_text_list("SELECT telegram_id FROM users")
        ok=0; fail=0
        for r in rows:
            try: tg("sendMessage",{"chat_id":r['telegram_id'],"text":text}); ok+=1
            except Exception: fail+=1
        STATE.pop(uid,None); return tg("sendMessage",{
          "chat_id":chat_id,
          "text":f"📣 ارسال تمام شد. موفق: {ok} | ناموفق: {fail}",
          "reply_markup":admin_bottom_keyboard()
        })
    if s["step"]=="card_receipt" and msg.get("photo"):
        file_id=msg["photo"][-1]["file_id"]
        receipt_data=None; receipt_mime=None
        try: receipt_data,receipt_mime=download_telegram_file(file_id)
        except Exception as exc: print("receipt download error",repr(exc))
        conn=db(); cur=conn.cursor()
        cur.execute("""UPDATE orders SET receipt_file_id=%s,receipt_data=%s,receipt_mime=%s,receipt_size=%s,status='receipt_sent'
                       WHERE id=%s AND telegram_id=%s""",
                    (file_id,psycopg2.Binary(receipt_data) if receipt_data else None,receipt_mime,len(receipt_data or b''),s["order_id"],uid))
        conn.commit(); cur.close(); conn.close(); STATE.pop(uid,None)
        if ADMIN_ID:
            tg_safe("sendPhoto",{"chat_id":ADMIN_ID,"photo":file_id,"caption":f"رسید سفارش #{s['order_id']}","reply_markup":{"inline_keyboard":[[{"text":"✅ تأیید","callback_data":f"admin:approve:{s['order_id']}"},{"text":"❌ رد","callback_data":f"admin:reject:{s['order_id']}"}]]}})
        return tg_safe("sendMessage",{"chat_id":chat_id,"text":"رسید در دیتابیس ثبت شد و در انتظار بررسی است."})

class Handler(BaseHTTPRequestHandler):
    server_version="ai-shop/3.1.0"

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt%args}")

    def send_text(self, code, text, content_type="text/plain; charset=utf-8"):
        data=text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type",content_type)
        self.send_header("Content-Length",str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_bytes(self, code, data, content_type="application/octet-stream"):
        self.send_response(code); self.send_header("Content-Type",content_type); self.send_header("Content-Length",str(len(data))); self.send_header("Cache-Control","private, max-age=60"); self.end_headers(); self.wfile.write(data)

    def read_body(self):
        length=int(self.headers.get("Content-Length","0") or "0")
        return self.rfile.read(length) if length else b""

    def admin_ok(self):
        auth=self.headers.get("Authorization","")
        if not auth.startswith("Basic "): return False
        try:
            raw=base64.b64decode(auth.split(" ",1)[1]).decode("utf-8")
            user,pwd=raw.split(":",1)
            return user==ADMIN_USER and pwd==ADMIN_PASS
        except Exception:
            return False

    def require_admin(self):
        if self.admin_ok(): return True
        self.send_response(401)
        self.send_header("WWW-Authenticate",'Basic realm="AI-SHOP Admin"')
        self.end_headers()
        return False

    def do_GET(self):
        parsed=urllib.parse.urlparse(self.path)
        if parsed.path=="/health":
            return self.send_text(200,json.dumps({"ok":True,"version":APP_VERSION}),"application/json")
        if parsed.path=="/version":
            return self.send_text(200,json.dumps({"name":"ai-shop","version":APP_VERSION}),"application/json")
        if parsed.path=="/payment/callback":
            return self.payment_callback(parsed)
        if parsed.path=="/admin":
            if not self.require_admin(): return
            return self.admin_page()
        if parsed.path=="/admin/help":
            if not self.require_admin(): return
            return self.help_page()
        if parsed.path=="/admin/database":
            if not self.require_admin(): return
            return self.database_page()
        if parsed.path=="/admin/database/export":
            if not self.require_admin(): return
            return self.database_export(parsed)
        if parsed.path=="/admin/receipt":
            if not self.require_admin(): return
            return self.receipt_proxy(parsed)
        if parsed.path=="/admin/receipt":
            if not self.require_admin(): return
            q=urllib.parse.parse_qs(parsed.query); oid=q.get("order_id",[""])[0]
            conn=db(); cur=conn.cursor(); cur.execute("SELECT receipt_file_id FROM orders WHERE id=%s",(oid,)); row=cur.fetchone(); cur.close(); conn.close()
            if not row or not row[0]: return self.send_text(404,"رسید موجود نیست")
            try:
                data,ctype=telegram_file_bytes(row[0]); return self.send_bytes(200,data,ctype)
            except Exception as e: return self.send_text(502,"خطا در دریافت رسید: "+str(e))
        return self.send_text(404,"not found")

    def do_POST(self):
        parsed=urllib.parse.urlparse(self.path)
        if parsed.path=="/telegram/webhook":
            if self.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
                return self.send_text(403,"forbidden")
            try:
                u=json.loads(self.read_body().decode("utf-8"))
                if (u.get("callback_query") or {}).get("data","").startswith("admin:"):
                    handle_admin_callback(u["callback_query"])
                elif u.get("callback_query"):
                    handle_callback(u["callback_query"])
                elif u.get("message"):
                    handle_message(u["message"])
                return self.send_text(200,"ok")
            except TelegramAPIError as e:
                print("webhook telegram error:",str(e))
                audit("webhook_telegram_error","telegram",getattr(e,"method",""),str(e),actor="system")
                return self.send_text(200,"ok")
            except Exception as e:
                print("webhook internal error:",repr(e))
                audit("webhook_internal_error","webhook","",repr(e),actor="system")
                return self.send_text(200,"ok")
        if parsed.path.startswith("/admin/"):
            if not self.require_admin(): return
            data=urllib.parse.parse_qs(self.read_body().decode("utf-8"))
            def val(name, default=""):
                return data.get(name,[default])[0].strip()
            try:
                conn=db(); cur=conn.cursor()
                if parsed.path=="/admin/products/create":
                    cur.execute("""INSERT INTO products(title,description,price,delivery_text,active)
                                   VALUES(%s,%s,%s,%s,true)""",
                                (val("title"),val("description"),int(val("price","0").replace(",","")),val("delivery_text")))
                elif parsed.path=="/admin/products/update":
                    cur.execute("""UPDATE products SET title=%s,description=%s,price=%s,delivery_text=%s
                                   WHERE id=%s""",
                                (val("title"),val("description"),int(val("price","0").replace(",","")),val("delivery_text"),int(val("id"))))
                elif parsed.path=="/admin/products/price":
                    cur.execute("UPDATE products SET price=%s WHERE id=%s",
                                (int(val("price","0").replace(",","")),int(val("id"))))
                elif parsed.path=="/admin/products/toggle":
                    cur.execute("UPDATE products SET active=NOT active WHERE id=%s",(int(val("id")),))
                elif parsed.path=="/admin/products/delete":
                    cur.execute("DELETE FROM products WHERE id=%s",(int(val("id")),))
                elif parsed.path=="/admin/orders/status":
                    oid=int(val("id")); status=val("status")
                    cur.execute("UPDATE orders SET status=%s,paid_at=CASE WHEN %s='paid' THEN NOW() ELSE paid_at END WHERE id=%s",(status,status,oid))
                    conn.commit()
                    if status=='paid': deliver_order(oid)
                elif parsed.path=="/admin/orders/approve":
                    oid=int(val("id")); cur.execute("UPDATE orders SET status='paid',paid_at=NOW() WHERE id=%s",(oid,)); conn.commit(); deliver_order(oid)
                elif parsed.path=="/admin/orders/reject":
                    oid=int(val("id")); cur.execute("UPDATE orders SET status='rejected' WHERE id=%s RETURNING telegram_id",(oid,)); row=cur.fetchone(); conn.commit()
                    if row: tg("sendMessage",{"chat_id":row[0],"text":f"❌ رسید سفارش #{oid} رد شد. لطفاً با پشتیبانی تماس بگیرید."})
                elif parsed.path=="/admin/coupons/create":
                    cur.execute("INSERT INTO discount_codes(code,percent,amount,usage_limit) VALUES(%s,%s,%s,%s)",(val("code").upper(),int(val("percent","0")),int(val("amount","0")),int(val("usage_limit","0")) or None))
                elif parsed.path=="/admin/tickets/reply":
                    tid=int(val("id")); reply=val("reply")
                    cur.execute("UPDATE tickets SET admin_reply=%s,status='closed' WHERE id=%s RETURNING telegram_id",(reply,tid))
                    row=cur.fetchone()
                    if row and reply:
                        try: tg("sendMessage",{"chat_id":row[0],"text":f"📨 پاسخ تیکت #{tid}\n\n{reply}"})
                        except Exception as exc: print("ticket notify error",repr(exc))
                    audit("reply_ticket","ticket",tid,reply[:200])
                elif parsed.path=="/admin/orders/approve":
                    oid=int(val("id")); conn.commit(); cur.close(); conn.close()
                    ok,message=deliver_order(oid)
                    self.send_response(303); self.send_header("Location","/admin"); self.end_headers(); return
                elif parsed.path=="/admin/orders/reject":
                    oid=int(val("id"))
                    cur.execute("UPDATE orders SET status='rejected' WHERE id=%s RETURNING telegram_id",(oid,))
                    row=cur.fetchone()
                    if row:
                        try: tg("sendMessage",{"chat_id":row[0],"text":f"❌ رسید سفارش #{oid} رد شد. لطفاً با پشتیبانی تماس بگیرید."})
                        except Exception: pass
                    audit("reject_order","order",oid)
                elif parsed.path=="/admin/inventory/create":
                    cur.execute("INSERT INTO service_inventory(product_id,payload) VALUES(%s,%s)",
                                (int(val("product_id")),val("payload")))
                    audit("add_inventory","product",val("product_id"))
                elif parsed.path=="/admin/settings/save":
                    for key in ["shop_title","support_text","premium_emoji_welcome_id"]:
                        cur.execute("""INSERT INTO app_settings(key,value) VALUES(%s,%s)
                                     ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value,updated_at=NOW()""",
                                    (key,val(key)))
                    audit("save_settings","settings")
                else:
                    cur.close(); conn.close()
                    return self.send_text(404,"not found")
                conn.commit(); cur.close(); conn.close()
                self.send_response(303); self.send_header("Location","/admin"); self.end_headers(); return
            except Exception as e:
                print("admin action error:",repr(e))
                return self.send_text(400,"عملیات ناموفق بود: "+html.escape(str(e)))
        return self.send_text(404,"not found")

    def payment_callback(self, parsed):
        try:
            q=urllib.parse.parse_qs(parsed.query)
            oid=q.get("order_id",[""])[0]; authority=q.get("Authority",[""])[0]; status=q.get("Status",[""])[0]
            conn=db(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("""SELECT o.*,p.delivery_text FROM orders o
              LEFT JOIN products p ON p.id=o.product_id WHERE o.id=%s""",(oid,))
            o=cur.fetchone()
            if not o or not authority or authority!=o["authority"] or status!="OK":
                cur.close(); conn.close(); return self.send_text(400,"پرداخت ناموفق یا لغو شد.")
            if o["status"]=="paid":
                cur.close(); conn.close(); return self.send_text(200,f"این سفارش قبلاً پرداخت شده است. کد پیگیری: {o['ref_id'] or '-'}")
            ok,code,ref_id=verify_payment(o["amount"],authority)
            if not ok:
                cur.close(); conn.close(); return self.send_text(400,f"تأیید پرداخت ناموفق بود. کد: {code}")
            cur.execute("UPDATE orders SET status='paid',ref_id=%s,paid_at=NOW() WHERE id=%s AND status<>'paid'",(ref_id,o["id"]))
            conn.commit(); cur.close(); conn.close()
            deliver_order(o["id"])
            return self.send_text(200,f"پرداخت موفق بود. کد پیگیری: {ref_id or '-'}")
        except Exception as e:
            print("payment error:",repr(e))
            return self.send_text(500,"خطای داخلی")

    def help_page(self):
        path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"docs","index.html")
        try:
            with open(path,"r",encoding="utf-8") as f:
                return self.send_text(200,f.read(),"text/html; charset=utf-8")
        except FileNotFoundError:
            return self.send_text(404,"راهنما نصب نشده است.")

    def receipt_proxy(self, parsed):
        q=urllib.parse.parse_qs(parsed.query)
        oid=q.get("order_id",[""])[0]
        conn=db(); cur=conn.cursor()
        cur.execute("SELECT receipt_file_id,receipt_data,receipt_mime FROM orders WHERE id=%s",(oid,))
        row=cur.fetchone(); cur.close(); conn.close()
        if not row: return self.send_text(404,"رسید موجود نیست")
        if row[1]: return self.send_bytes(200,bytes(row[1]),row[2] or "image/jpeg")
        if not row[0]: return self.send_text(404,"رسید موجود نیست")
        try:
            data,ctype=download_telegram_file(row[0])
            return self.send_bytes(200,data,ctype)
        except Exception as exc:
            self.send_text(500,"خطا در دریافت رسید: "+str(exc))

    def database_export(self, parsed):
        allowed={"users","products","orders","tickets","discount_codes","service_inventory","wallet_transactions","audit_logs","user_sessions"}
        q=urllib.parse.parse_qs(parsed.query); table=q.get("table",[""])[0]
        if table not in allowed: return self.send_text(400,"جدول مجاز نیست")
        conn=db(); cur=conn.cursor()
        cur.execute(f'SELECT * FROM "{table}" ORDER BY 1 DESC LIMIT 10000')
        rows=cur.fetchall(); headers=[d[0] for d in cur.description]
        cur.close(); conn.close()
        out=io.StringIO(); writer=csv.writer(out); writer.writerow(headers); writer.writerows(rows)
        data=out.getvalue().encode("utf-8-sig")
        self.send_response(200); self.send_header("Content-Type","text/csv; charset=utf-8")
        self.send_header("Content-Disposition",f'attachment; filename="{table}.csv"')
        self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data)

    def database_page(self):
        allowed=["users","categories","products","service_inventory","orders","discount_codes","tickets","wallet_transactions","payment_gateways","app_settings","audit_logs","user_sessions"]
        conn=db(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cards=[]; sections=[]
        for table in allowed:
            cur.execute(f'SELECT COUNT(*) AS c FROM "{table}"'); count=cur.fetchone()["c"]
            cards.append(f"<a class='dbcard' href='#{table}'><b>{html.escape(table)}</b><span>{count:,} رکورد</span></a>")
            cur.execute(f'SELECT * FROM "{table}" ORDER BY 1 DESC LIMIT 20')
            rows=cur.fetchall()
            if rows:
                headers=list(rows[0].keys())
                th="".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
                body="".join("<tr>"+"".join(f"<td>{html.escape(str(r.get(h,'')))[:500]}</td>" for h in headers)+"</tr>" for r in rows)
            else:
                th="<th>بدون داده</th>"; body=""
            sections.append(f"<section id='{table}'><h2>{table}</h2><a class='btn' href='/admin/database/export?table={table}'>خروجی CSV</a><div class='table'><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div></section>")
        cur.close(); conn.close()
        page=f"""<!doctype html><html lang='fa' dir='rtl'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>مدیریت دیتابیس ai-shop</title><style>
body{{margin:0;background:#07111f;color:#edf5ff;font-family:Tahoma,Arial;padding:24px}}a{{color:inherit;text-decoration:none}}
header{{display:flex;justify-content:space-between;align-items:center}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:25px 0}}
.dbcard,section{{background:#101d31;border:1px solid #263b58;border-radius:16px;padding:16px}}.dbcard span{{display:block;color:#91a4bd;margin-top:8px}}
section{{margin:18px 0}}.btn{{display:inline-block;background:#56a8ff;color:#04111f;padding:8px 12px;border-radius:10px;font-weight:bold}}
.table{{overflow:auto;margin-top:12px}}table{{border-collapse:collapse;width:100%;min-width:900px}}th,td{{padding:9px;border-bottom:1px solid #263b58;text-align:right;max-width:320px;white-space:pre-wrap;word-break:break-word}}th{{color:#8ec4ff}}
</style><header><div><h1>مدیریت دیتابیس</h1><p>نمایش امن و فقط‌خواندنی شبیه phpMyAdmin</p></div><a class='btn' href='/admin'>بازگشت به پنل</a></header>
<div class='cards'>{''.join(cards)}</div>{''.join(sections)}</html>"""
        self.send_text(200,page,"text/html; charset=utf-8")

    def admin_page(self):
        conn=db()
        cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT COUNT(*) AS c FROM users"); user_count=cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM products"); product_count=cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM orders"); order_count=cur.fetchone()["c"]
        cur.execute("SELECT COALESCE(SUM(amount),0) AS s FROM orders WHERE status='paid'"); sales=cur.fetchone()["s"]
        cur.execute("SELECT * FROM products ORDER BY id DESC"); products=cur.fetchall()
        cur.execute("""SELECT o.*,p.title FROM orders o LEFT JOIN products p ON p.id=o.product_id
                       ORDER BY o.id DESC LIMIT 100"""); orders=cur.fetchall()
        cur.execute("SELECT * FROM tickets ORDER BY id DESC LIMIT 100"); tickets=cur.fetchall()
        cur.execute("SELECT * FROM discount_codes ORDER BY id DESC LIMIT 50"); coupons=cur.fetchall()
        cur.close(); conn.close()

        esc=lambda x: html.escape(str(x if x is not None else ""))
        status_badge=lambda s: {
          "paid":"<span class='badge success'>پرداخت‌شده</span>",
          "pending":"<span class='badge warning'>در انتظار</span>",
          "receipt_sent":"<span class='badge info'>رسید ارسال‌شده</span>",
          "rejected":"<span class='badge danger'>ردشده</span>"
        }.get(str(s),f"<span class='badge'>{esc(s)}</span>")

        product_rows="".join(f"""
        <tr>
          <td>#{p['id']}</td>
          <td><strong>{esc(p['title'])}</strong><small>{esc(p['description'])}</small></td>
          <td>
            <form class="inline" method="post" action="/admin/products/price">
              <input type="hidden" name="id" value="{p['id']}">
              <input class="price" name="price" type="number" min="0" value="{p['price']}">
              <button class="btn small primary">ذخیره قیمت</button>
            </form>
          </td>
          <td>{"فعال" if p['active'] else "غیرفعال"}</td>
          <td class="actions">
            <details><summary class="btn small">ویرایش کامل</summary>
              <form class="editbox" method="post" action="/admin/products/update">
                <input type="hidden" name="id" value="{p['id']}">
                <input name="title" value="{esc(p['title'])}" required>
                <textarea name="description">{esc(p['description'])}</textarea>
                <input name="price" type="number" min="0" value="{p['price']}" required>
                <textarea name="delivery_text">{esc(p['delivery_text'])}</textarea>
                <button class="btn primary">ذخیره تغییرات</button>
              </form>
            </details>
            <form class="inline" method="post" action="/admin/products/toggle">
              <input type="hidden" name="id" value="{p['id']}">
              <button class="btn small">{"غیرفعال‌کردن" if p['active'] else "فعال‌کردن"}</button>
            </form>
            <form class="inline" method="post" action="/admin/products/delete" onsubmit="return confirm('محصول حذف شود؟')">
              <input type="hidden" name="id" value="{p['id']}">
              <button class="btn small danger">حذف</button>
            </form>
          </td>
        </tr>""" for p in products)

        def order_receipt_button(order):
            if order.get("receipt_file_id"):
                return (
                    '<a class="btn small info" target="_blank" '
                    'href="/admin/receipt?order_id=%s">مشاهده رسید</a>'
                    % order["id"]
                )
            return '<span class="subtitle">بدون رسید</span>'

        order_rows="".join(f"""
        <tr>
          <td>#{o['id']}</td>
          <td>{esc(o['title'])}</td>
          <td>{o['telegram_id']}</td>
          <td>{money(o['amount'])}</td>
          <td>{esc(o['payment_method'])}</td>
          <td>{status_badge(o['status'])}</td>
          <td>
            {order_receipt_button(o)}
            <br>
            <form class="inline" method="post" action="/admin/orders/status">
              <input type="hidden" name="id" value="{o['id']}">
              <select name="status">
                {''.join(
                    '<option value="%s" %s>%s</option>' % (
                        status,
                        'selected' if o["status"] == status else '',
                        label
                    )
                    for status, label in [
                        ("pending", "در انتظار"),
                        ("receipt_sent", "رسید ارسال‌شده"),
                        ("paid", "پرداخت‌شده"),
                        ("rejected", "ردشده")
                    ]
                )}
              </select>
              <button class="btn small">اعمال</button>
            </form>

            <form class="inline" method="post" action="/admin/orders/approve">
              <input type="hidden" name="id" value="{o['id']}">
              <button class="btn small primary">تأیید و تحویل</button>
            </form>

            <form class="inline" method="post" action="/admin/orders/reject">
              <input type="hidden" name="id" value="{o['id']}">
              <button class="btn small danger">رد رسید</button>
            </form>
          </td>
        </tr>""" for o in orders)

        ticket_rows="".join(f"""
        <tr>
          <td>#{t['id']}</td><td>{t['telegram_id']}</td><td><strong>{esc(t['subject'])}</strong><small>{esc(t['body'])}</small></td>
          <td>{esc(t['status'])}</td>
          <td><form method="post" action="/admin/tickets/reply">
            <input type="hidden" name="id" value="{t['id']}">
            <textarea name="reply" placeholder="پاسخ مدیر">{esc(t['admin_reply'] or '')}</textarea>
            <button class="btn small primary">ارسال و بستن</button>
          </form></td>
        </tr>""" for t in tickets)

        coupon_rows="".join(f"<tr><td>{esc(c['code'])}</td><td>{c['percent']}٪</td><td>{money(c['amount'])}</td><td>{c['used_count']}/{c['usage_limit'] or '∞'}</td><td>{'فعال' if c['active'] else 'غیرفعال'}</td></tr>" for c in coupons)

        page=f"""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>پنل مدیریت ai-shop</title>
<style>
:root{{--bg:#07111f;--panel:#101d31;--panel2:#14243b;--text:#ecf4ff;--muted:#91a4bd;--line:#263b58;--accent:#56a8ff;--green:#25c58a;--red:#ff647c;--yellow:#f3b84b}}
*{{box-sizing:border-box}} body{{margin:0;background:linear-gradient(135deg,#06101c,#0d1b30 55%,#102443);color:var(--text);font-family:Vazirmatn,Tahoma,Arial,sans-serif}}
.shell{{display:grid;grid-template-columns:230px 1fr;min-height:100vh}} aside{{background:rgba(7,16,29,.92);border-left:1px solid var(--line);padding:24px;position:sticky;top:0;height:100vh}}
.brand{{font-size:24px;font-weight:900;letter-spacing:1px}} .version{{font-size:12px;color:var(--muted);margin-top:6px}} nav a{{display:block;color:var(--muted);text-decoration:none;padding:12px 14px;border-radius:12px;margin:8px 0}} nav a:hover{{background:var(--panel2);color:white}}
main{{padding:28px;max-width:1500px;width:100%}} .top{{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}} h1,h2{{margin:0 0 16px}} .subtitle{{color:var(--muted)}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:22px}} .card,.section{{background:rgba(16,29,49,.88);border:1px solid var(--line);border-radius:18px;box-shadow:0 16px 50px rgba(0,0,0,.18)}}
.card{{padding:20px}} .card b{{display:block;font-size:28px;margin-top:8px}} .section{{padding:20px;margin-bottom:22px;overflow:auto}}
.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}} input,textarea,select{{width:100%;background:#091628;color:white;border:1px solid var(--line);border-radius:10px;padding:10px;font:inherit}} textarea{{min-height:74px;resize:vertical}}
.btn{{border:0;border-radius:10px;padding:10px 14px;background:#243b59;color:white;cursor:pointer;font:inherit}} .btn.primary{{background:var(--accent);color:#04111f;font-weight:bold}} .btn.danger{{background:var(--red);color:white}} .btn.small{{padding:7px 10px;font-size:12px}}
table{{width:100%;border-collapse:collapse;min-width:900px}} th,td{{padding:12px;border-bottom:1px solid var(--line);text-align:right;vertical-align:top}} th{{color:var(--muted);font-size:13px}} small{{display:block;color:var(--muted);margin-top:5px;max-width:350px}}
.inline{{display:inline-flex;gap:7px;align-items:center;margin:2px}} .price{{width:135px}} .actions{{min-width:250px}} details{{display:inline-block}} summary{{list-style:none}} .editbox{{position:absolute;z-index:5;background:#0c192b;border:1px solid var(--line);padding:14px;border-radius:14px;width:360px;box-shadow:0 20px 70px #000;display:grid;gap:8px}}
.badge{{display:inline-block;padding:5px 9px;border-radius:99px;background:#33455e;font-size:12px}} .success{{background:rgba(37,197,138,.18);color:#69e8b9}} .danger{{background:rgba(255,100,124,.18);color:#ff91a3}} .warning{{background:rgba(243,184,75,.18);color:#ffd47c}} .info{{background:rgba(86,168,255,.18);color:#8ec4ff}}
code{{color:#8ec4ff}} @media(max-width:900px){{.shell{{display:block}} aside{{height:auto;position:static}} nav{{display:flex;overflow:auto}} nav a{{white-space:nowrap}} .cards{{grid-template-columns:repeat(2,1fr)}} .grid{{grid-template-columns:1fr}} main{{padding:15px}}}}
</style></head><body>
<div class="shell"><aside><div class="brand">ai-shop</div><div class="version">نسخه {APP_VERSION}</div>
<nav><a href="#dashboard">داشبورد</a><a href="#products">محصولات و قیمت</a><a href="#orders">سفارش‌ها</a><a href="#tickets">تیکت‌ها</a><a href="#coupons">کد تخفیف</a></nav>
</aside><main>
<div class="top"><div><h1>پنل مدیریت حرفه‌ای</h1><div class="subtitle">مدیریت کامل فروشگاه تلگرام از یک صفحه</div></div><code>{esc(DOMAIN)}</code></div>
<section id="dashboard" class="cards">
<div class="card">کاربران<b>{user_count}</b></div><div class="card">محصولات<b>{product_count}</b></div>
<div class="card">سفارش‌ها<b>{order_count}</b></div><div class="card">فروش موفق<b>{money(sales)}</b></div>
</section>
<section class="section"><h2>افزودن محصول</h2>
<form method="post" action="/admin/products/create"><div class="grid">
<input name="title" placeholder="عنوان محصول" required><input name="price" type="number" min="0" placeholder="قیمت به ریال" required>
<textarea name="description" placeholder="توضیحات محصول"></textarea><textarea name="delivery_text" placeholder="متن تحویل پس از پرداخت"></textarea>
</div><br><button class="btn primary">ثبت محصول</button></form></section>
<section id="products" class="section"><h2>محصولات و ویرایش سریع قیمت</h2>
<table><thead><tr><th>شناسه</th><th>محصول</th><th>قیمت</th><th>وضعیت</th><th>عملیات</th></tr></thead><tbody>{product_rows}</tbody></table></section>
<section id="orders" class="section"><h2>سفارش‌ها</h2>
<table><thead><tr><th>شناسه</th><th>محصول</th><th>کاربر</th><th>مبلغ</th><th>روش</th><th>وضعیت</th><th>تغییر</th></tr></thead><tbody>{order_rows}</tbody></table></section>
<section id="tickets" class="section"><h2>تیکت‌ها</h2>
<table><thead><tr><th>شناسه</th><th>کاربر</th><th>پیام</th><th>وضعیت</th><th>پاسخ</th></tr></thead><tbody>{ticket_rows}</tbody></table></section>
<section id="coupons" class="section"><h2>کدهای تخفیف</h2><form method="post" action="/admin/coupons/create"><div class="grid"><input name="code" placeholder="کد مثل OFF20" required><input name="percent" type="number" min="0" max="100" placeholder="درصد"><input name="amount" type="number" min="0" placeholder="مبلغ ثابت ریال"><input name="usage_limit" type="number" min="0" placeholder="محدودیت استفاده؛ صفر نامحدود"></div><br><button class="btn primary">ساخت کد تخفیف</button></form><br><table><thead><tr><th>کد</th><th>درصد</th><th>مبلغ</th><th>مصرف</th><th>وضعیت</th></tr></thead><tbody>{coupon_rows}</tbody></table></section>

<section id="inventory" class="section"><h2>موجودی و اطلاعات آماده تحویل</h2>
<form method="post" action="/admin/inventory/create"><div class="grid">
<select name="product_id" required><option value="">انتخاب محصول</option>{''.join(f"<option value='{p['id']}'>{esc(p['title'])}</option>" for p in products)}</select>
<textarea name="payload" placeholder="ایمیل، رمز، لینک فعال‌سازی، لایسنس یا اطلاعات سرویس" required></textarea>
</div><br><button class="btn primary">افزودن به موجودی</button></form>
<table><thead><tr><th>ID</th><th>محصول</th><th>وضعیت</th><th>اطلاعات</th></tr></thead><tbody>
{''.join(f"<tr><td>#{i['id']}</td><td>{esc(i['title'])}</td><td>{esc(i['status'])}</td><td><small>{esc(i['payload'])}</small></td></tr>" for i in inventory)}
</tbody></table></section>
<section id="settings" class="section"><h2>تنظیمات فروشگاه و ایموجی سفارشی</h2>
<form method="post" action="/admin/settings/save"><div class="grid">
<input name="shop_title" value="{esc(settings.get('shop_title','ai-shop'))}" placeholder="عنوان فروشگاه">
<input name="premium_emoji_welcome_id" value="{esc(settings.get('premium_emoji_welcome_id',''))}" placeholder="Custom Emoji ID پیام خوش‌آمد">
<textarea name="support_text" placeholder="متن پشتیبانی">{esc(settings.get('support_text',''))}</textarea>
</div><br><button class="btn primary">ذخیره تنظیمات</button></form>
<p class="subtitle">ایموجی سفارشی تلگرام در متن پیام‌ها با Custom Emoji ID قابل استفاده است؛ دکمه‌ها از ایموجی استاندارد استفاده می‌کنند.</p></section>

</main></div></body></html>"""
        self.send_text(200,page,"text/html; charset=utf-8")

if __name__=="__main__":
    init_db()
    print(f"ai-shop v{APP_VERSION} listening on {HOST}:{PORT}")
    ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
