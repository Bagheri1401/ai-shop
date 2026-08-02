#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import base64
import html
import urllib.request
import urllib.parse
import urllib.error
import csv
import shutil
import subprocess
import secrets
import hashlib
import time
import io
import ssl
import mimetypes
import traceback
import logging

from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from datetime import datetime, timedelta

import psycopg2
import psycopg2.extras


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s"
)

APP_VERSION = "4.2.2 Stable"


def load_env(path):
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            if line.startswith("#"):
                continue

            if "=" not in line:
                continue

            key, value = line.split("=", 1)

            os.environ[key.strip()] = value.strip()


BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

load_env(os.path.join(BASE_DIR, ".env"))

HOST = os.getenv("APP_HOST", "127.0.0.1")
PORT = int(os.getenv("APP_PORT", "3000"))

DOMAIN = os.getenv("DOMAIN", "")

PUBLIC_URL = os.getenv(
    "PUBLIC_URL",
    ""
).rstrip("/")

BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    ""
).strip()

WEBHOOK_SECRET = os.getenv(
    "TELEGRAM_WEBHOOK_SECRET",
    ""
).strip()

ADMIN_ID = os.getenv(
    "ADMIN_TELEGRAM_ID",
    ""
)

ADMIN_USER = os.getenv(
    "ADMIN_USERNAME",
    "admin"
)

ADMIN_PASS = os.getenv(
    "ADMIN_PASSWORD",
    "change-me"
)

CURRENCY = os.getenv(
    "CURRENCY",
    "IRR"
)

ADMIN_SESSION_TOKEN = secrets.token_urlsafe(48)

ADMIN_OTP_TTL_SECONDS = 300


def db():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "ai_shop"),
        user=os.getenv("DB_USER", "ai_shop"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=os.getenv("DB_PORT", "5432"),
    )


def otp_hash(value):
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def money(amount):
    return "{:,} ریال".format(int(amount))


def tg(method, payload):

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT TOKEN IS EMPTY"
        )

    req = urllib.request.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json"
        }
    )

    with urllib.request.urlopen(req, timeout=30) as r:
        result = json.loads(
            r.read().decode()
        )

    if not result.get("ok"):
        raise RuntimeError(result)

    return result["result"]


def tg_safe(method, payload):
    try:
        return tg(method, payload)

    except Exception:

        logging.exception(
            "Telegram Error"
        )

        return None


def webhook(update):

    try:

        if "callback_query" in update:
            callback = update["callback_query"]

            data = callback.get("data", "")

            if re.match(r"^adm:", data):
                return

        if "message" in update:

            message = update["message"]

            text = message.get("text", "")

            if re.match(r"^/start", text):
                pass

    except Exception:

        logging.exception(
            "Webhook Internal Error"
        )


print("AI-SHOP", APP_VERSION, "started successfully.")
