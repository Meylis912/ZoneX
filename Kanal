#!/usr/bin/env python3
import telebot
import threading
import time
import os
import string
import random
import requests
import datetime
import certifi
from flask import Flask
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson import ObjectId
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ╔══════════════════════════════════════════════════════════╗
#                     SAZLAMALAR & KESH (CACHE)
# ╚══════════════════════════════════════════════════════════╝
BOT_TOKEN    = "8734846571:AAFMwOErDqt046ccrQ9EGqvzC8Xu5ZtILi0"
ADMIN_ID     = 7523674506
RENDER_URL    = "https://kanal-bot.onrender.com"

# Boty çaltlaşdyrmak üçin Multithreading (4 potok) işe girizilýär
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", num_threads=4)

MONGO_URI = (
    "mongodb+srv://mergenowlyagulyyew41_db_user:ZvZhOKOAF6ZMRbHX@cluster1.l8z8gll.mongodb.net/?appName=Cluster1"
)

# Botuň doňmazlygy üçin operatiw ýatda kesh saklaýarys (Global Cache)
_CACHE = {
    "settings": {},
    "sponsors": [],
    "addlist": [],
    "post_channels": [],
    "last_update": 0
}
CACHE_TTL = 30  # Kesh maglumatlary her 30 sekuntdan täzelenýär

# ╔══════════════════════════════════════════════════════════╗
#                   MONGODB BIRIKDIRME
# ╚══════════════════════════════════════════════════════════╝
_client = MongoClient(
    MONGO_URI,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=5000  # Doňup durmazlygy üçin garaşma wagtyny azaltdyk
)
try:
    _client.admin.command("ping")
    print("✅ MongoDB-ä üstünlikli birikdi!")
except ConnectionFailure:
    print("❌ MongoDB birikme ýalňyşlygy!")

_db          = _client["bot_data"]

col_users           = _db["col1"]
col_sponsors        = _db["col2"]
col_addlist         = _db["col3"]
col_settings        = _db["col4"]
col_reklam          = _db["col5"]
col_promo           = _db["col6"]
col_tgrass_channels = _db["col7"]
col_post_channels   = _db["col8"]

col_users.create_index("user_id", unique=True)

# ╔══════════════════════════════════════════════════════════╗
#              KESH DOLANDYRYŞ FUNKSIÝALARY (ÇALT OKAMAK)
# ╚══════════════════════════════════════════════════════════╝
def update_local_cache(force=False):
    """DB-den maglumatlary diňe wagt dolanda ýa-da mejburlap okap RAM-a ýazýar"""
    now = time.time()
    if not force and (now - _CACHE["last_update"] < CACHE_TTL):
        return

    # Sazlamalary keshle
    for doc in col_settings.find():
        _CACHE["settings"][doc["key"]] = doc["value"]
    
    # Kanallary keshle
    _CACHE["sponsors"] = [(str(d["_id"]), d.get("link",""), d.get("name",""), d.get("username","")) for d in col_sponsors.find()]
    _CACHE["addlist"] = [(str(d["_id"]), d.get("link",""), d.get("name",""), d.get("username","")) for d in col_addlist.find()]
    _CACHE["post_channels"] = list(col_post_channels.find())
    
    _CACHE["last_update"] = now

def get_setting(key, default=""):
    update_local_cache()
    return _CACHE["settings"].get(key, default)

def set_setting(key, value):
    col_settings.update_one({"key": key}, {"$set": {"value": value}}, upsert=True)
    _CACHE["settings"][key] = value  # Keshi göni täzele

# Sazlamalaryň asyl bahalary
update_local_cache(force=True)
if not get_setting("vpn_code"): set_setting("vpn_code", "SHADOWVIP-2024")
if not get_setting("tgrass"): set_setting("tgrass", "on")
if not get_setting("welcome_text"):
    set_setting("welcome_text", "👋 <b>Hojageldiniz!</b>\n\nMugt VPN koduny almak üçin aşakdaky kanallarymyza agza boluň 👇")

# ╔══════════════════════════════════════════════════════════╗
#                   MAZMUN FUNKSIÝALARY (RAM-dan okaýar)
# ╚══════════════════════════════════════════════════════════╝
def get_sponsors():
    update_local_cache()
    return _CACHE["sponsors"]

def get_addlist():
    update_local_cache()
    return _CACHE["addlist"]

def get_post_channels():
    update_local_cache()
    return _CACHE["post_channels"]

def _add_channel(col, link, name, username):
    uname = username.lstrip("@")
    col.update_one({"username": uname}, {"$set": {"link": link, "name": name, "username": uname}}, upsert=True)
    update_local_cache(force=True)

def _del_channel(col, doc_id):
    try:
        col.delete_one({"_id": ObjectId(doc_id)})
        update_local_cache(force=True)
    except Exception: pass

def add_sponsor(link, name, username):  _add_channel(col_sponsors, link, name, username)
def add_addlist(link, name, username):  _add_channel(col_addlist,  link, name, username)
def del_sponsor(doc_id): _del_channel(col_sponsors, doc_id)
def del_addlist(doc_id): _del_channel(col_addlist,  doc_id)

def add_post_channel(name, username):
    uname = username.strip().lstrip("@")
    col_post_channels.update_one({"username": uname}, {"$set": {"name": name, "username": uname}}, upsert=True)
    update_local_cache(force=True)

def del_post_channel(doc_id):
    try:
        col_post_channels.delete_one({"_id": ObjectId(doc_id)})
        update_local_cache(force=True)
    except Exception: pass

def parse_channel_args(text):
    parts = text.strip().split(maxsplit=2)
    if len(parts) < 3: return None, None, None
    name = parts[1]
    raw  = parts[2].strip()
    if raw.startswith("@"):
        username = raw
        link     = "https://t.me/" + raw.lstrip("@")
    elif "t.me/" in raw:
        link     = raw
        username = "@" + raw.split("t.me/")[-1].split("/")[0]
    else:
        username = "@" + raw
        link     = "https://t.me/" + raw
    return name, link, username

# ╔══════════════════════════════════════════════════════════╗
#                   FUNKSIÝALAR — ULANYJYLAR
# ╚══════════════════════════════════════════════════════════╝
def db_add_user(user_id, username, referred_by=None):
    if col_users.find_one({"user_id": user_id}): return False
    col_users.insert_one({
        "user_id":    user_id,
        "username":   username or "",
        "join_date":  datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "referred_by":       referred_by,
    })
    return True

def db_get_user(user_id):
    return col_users.find_one({"user_id": user_id})

def db_get_all_users():
    return [d["user_id"] for d in col_users.find({}, {"user_id": 1})]

def db_get_stats():
    now      = datetime.datetime.utcnow()
    day_ago  = (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    week_ago = (now - datetime.timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    total    = col_users.count_documents({})
    today    = col_users.count_documents({"join_date": {"$gte": day_ago}})
    week     = col_users.count_documents({"join_date": {"$gte": week_ago}})
    return total, today, week

def db_get_growth():
    now    = datetime.datetime.utcnow()
    result = []
    for i in range(6, -1, -1):
        ds = (now - datetime.timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        de = ds + datetime.timedelta(days=1)
        c  = col_users.count_documents({
            "join_date": {"$gte": ds.strftime("%Y-%m-%d %H:%M:%S"), "$lt":  de.strftime("%Y-%m-%d %H:%M:%S")}
        })
        result.append((ds.strftime("%d.%m"), c))
    return result

def save_reklam(chat_id, message_id):
    col_reklam.insert_one({"chat_id": str(chat_id), "message_id": message_id})

def get_reklamlar():
    return [(d["chat_id"], d["message_id"]) for d in col_reklam.find()]

def clear_reklamlar():
    col_reklam.delete_many({})

# ╔══════════════════════════════════════════════════════════╗
#                   TGRASS INTEGRASYONY (TIMEOUT AZALDYLDY)
# ╚══════════════════════════════════════════════════════════╝
TGRASS_ENDPOINT = "https://tgrass.space/offers"
TGRASS_HEADERS  = {
    "Content-Type": "application/json",
    "Auth":         "e5e1e1401d9e4515a211288a5a22bb48",
}

def tgrass_fetch_channels():
    if get_setting("tgrass", "on") != "on": return 0, "TGrass ýapyk"
    try:
        resp = requests.post(
            TGRASS_ENDPOINT,
            json={"tg_user_id": 0, "is_premium": False, "lang": "tk"},
            headers=TGRASS_HEADERS,
            timeout=3  # Botuň doňup durmazlygy üçin garaşma wagty 3 sekunt bellenildi
        )
        if resp.status_code != 200: return 0, f"HTTP {resp.status_code}"
        data = resp.json()
        offers = data if isinstance(data, list) else data.get("offers", data.get("channels", []))
        count = 0
        for offer in offers:
            username = offer.get("username") or offer.get("login") or offer.get("channel_username") or ""
            name     = offer.get("name") or offer.get("title") or username
            link     = offer.get("link") or offer.get("url") or (f"https://t.me/{username.lstrip('@')}" if username else "")
            if username and link:
                _add_channel(col_tgrass_channels, link, name, username)
                count += 1
        return count, "ok"
    except Exception as e: return 0, str(e)[:80]

def tgrass_get_offers(user):
    if get_setting("tgrass", "on") != "on": return []
    try:
        resp = requests.post(
            TGRASS_ENDPOINT,
            json={"tg_user_id": user.id, "is_premium": bool(getattr(user, "is_premium", False)), "lang": "tk"},
            headers=TGRASS_HEADERS,
            timeout=3  # Garaşma wagty 3 sekunt
        )
        if resp.status_code != 200: return []
        data = resp.json()
        return data if isinstance(data, list) else data.get("offers", data.get("channels", []))
    except Exception: return []

def check_tgrass_subscription(user):
    if get_setting("tgrass", "on") != "on": return []
    not_sub = []
    offers = tgrass_get_offers(user)
    if offers:
        for offer in offers:
            if offer.get("type") not in ("channel", None): continue
            if not offer.get("subscribed", True):
                name = offer.get("name") or offer.get("title") or "Sponsor"
                link = offer.get("link") or offer.get("url") or ""
                if link: not_sub.append((f"tg_{offer.get('offer_id', '')}", link, name))
    return not_sub

# ╔══════════════════════════════════════════════════════════╗
#                   AGZALYK BARLAGY WE KLAVIATURA
# ╚══════════════════════════════════════════════════════════╝
def check_subs(user_id):
    not_sub = []
    for ch_id, ch_link, ch_name, username in list(get_sponsors()) + list(get_addlist()):
        if not username: continue
        try:
            m = bot.get_chat_member("@" + username.lstrip("@"), user_id)
            if m.status in ("left", "kicked", "banned"): not_sub.append((ch_id, ch_link, ch_name))
        except Exception: not_sub.append((ch_id, ch_link, ch_name))
    return not_sub

def build_main_keyboard(user_id=None, _tgrass_user=None):
    me       = bot.get_me()
    ref_link = f"https://t.me/{me.username}?start={user_id}" if user_id else f"https://t.me/{me.username}"
    share_url = f"https://t.me/share/url?url={ref_link}&text=🔥%20Mugt%20VPN%20koduny%20al!"

    kb = InlineKeyboardMarkup(row_width=2)

    sponsor_btns = [InlineKeyboardButton(text=f"🌟 {name}", url=link) for _, link, name, _ in get_sponsors()]
    addlist_btns = [InlineKeyboardButton(text=f"✨ {name}", url=link) for _, link, name, _ in get_addlist()]
    
    all_btns = sponsor_btns + addlist_btns
    if all_btns: kb.add(*all_btns)

    kb.row(
        InlineKeyboardButton(text="✅ Agza boldum", callback_data="check_sub"),
        InlineKeyboardButton(text="📢 Paýlaş",   url=share_url),
    )
    return kb

def build_admin_keyboard():
    total, today, _ = db_get_stats()
    tgrass  = get_setting("tgrass", "on")
    tg_icon = "✅" if tgrass == "on" else "❌"

    kb = InlineKeyboardMarkup(row_width=2)
    kb.row(InlineKeyboardButton(text=f"🏁 Ulanyjylar: {total} (Şügün +{today})", callback_data="adm_stats"))
    kb.row(InlineKeyboardButton(text="📢 Reklama ugrat", callback_data="adm_broadcast"), InlineKeyboardButton(text="📡 Kanallara post", callback_data="adm_send_channel"))
    kb.row(InlineKeyboardButton(text="🔑 VPN Kody üýtget", callback_data="adm_code"), InlineKeyboardButton(text="🗑 Reklama öçür", callback_data="adm_del_reklam"))
    kb.row(InlineKeyboardButton(text="📈 Ösüş grafigi", callback_data="adm_growth"), InlineKeyboardButton(text="➕ Sponsor goş", callback_data="adm_add_sponsor"))
    kb.row(InlineKeyboardButton(text="🗑 Sponsor aýyr", callback_data="adm_del_sponsor"), InlineKeyboardButton(text="➕ Addlist goş", callback_data="adm_add_addlist"))
    kb.row(InlineKeyboardButton(text="🗑 Addlist aýyr", callback_data="adm_del_addlist"), InlineKeyboardButton(text=f"⚙️ TGrass {tg_icon}", callback_data="adm_tgrass"))
    kb.row(InlineKeyboardButton(text="🔄 TGrass Täzele", callback_data="adm_update_tg"))
    return kb

if __name__ == "__main__":
    print("🚀 Çaltlaşdyrylan Türkmençe bot işläp başlady...")
    # bot.infinity_polling()
