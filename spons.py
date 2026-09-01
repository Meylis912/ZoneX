import os
import asyncio
import logging
import requests
import json
import re
import time
import datetime
import threading
import random
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    CallbackQuery,
    Message
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Botuň sazlamalary
BOT_TOKEN = os.getenv("BOT_TOKEN", "7941701421:AAH3LDPxDHcEuugStk1DQgRpMAAQEIsCJp0")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "7523674506,8407003010").split(",") if x.strip()]

# Super Admin bilen habarlaşmak üçin ulanylýan username (Bakiye doldurmak/VPN link talaplary üçin)
SUPER_ADMIN_USERNAME = "zonex015"

# MongoDB
MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://mergenowlyagulyyew41_db_user:ZvZhOKOAF6ZMRbHX@cluster1.l8z8gll.mongodb.net/?appName=Cluster1")

# TGRASS
TGRASS_API_KEY = os.getenv("TGRASS_API_KEY", "02f064af71be4a1d915ddefb098d92fc")
TGRASS_API_URL = "https://tgrass.space/offers"

# PIARFLOW
PIARFLOW_API_KEY = os.getenv("PIARFLOW_API_KEY", "clyXF-oion-1bXrrjqXiKd3Xjhc4cQ3D")
PIARFLOW_API_URL = "https://piarflow.com/v1"

# SUBGRAM
SUBGRAM_API_KEY = os.getenv("SUBGRAM_API_KEY", "1f2f8f5bf86ad03529d5cd118adbb170069e781173793fe51e67e97f2f3feb7d")
SUBGRAM_API_URL = "https://api.subgram.org/get-sponsors"

# Railway PORT
PORT = int(os.environ.get("PORT", 8080))

# bot
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# MongoDB bağlantısı
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["Emin"]
col_users = db["users"]
col_sponsors = db["sponsors"]
col_addlists = db["addlists"]
col_settings = db["settings"]
col_post_channels = db["post_channels"]
col_sent_ads = db["sent_ads"]
col_admins = db["admins"]          # {"user_id": int, "role": "admin" | "adminlo"}
col_bans = db["bans"]              # {"user_id": int, "banned_at": str}
col_purchases = db["purchases"]    # VPN satyn alnan paketler

# Indexler
async def init_db():
    try:
        await col_users.create_index("user_id", unique=True)
        await col_sponsors.create_index("position")
        await col_addlists.create_index("position")
        await col_post_channels.create_index("username", unique=True)
        await col_settings.create_index("key", unique=True)
        await col_admins.create_index("user_id", unique=True)
        await col_bans.create_index("user_id", unique=True)
        await col_purchases.create_index("user_id")
        
        # Default settings
        if not await col_settings.find_one({"key": "start_text"}):
            await col_settings.insert_one({
                "key": "start_text",
                "value": ""
            })
        if not await col_settings.find_one({"key": "vpn_code"}):
            await col_settings.insert_one({
                "key": "vpn_code",
                "value": ""
            })
        if not await col_settings.find_one({"key": "tgrass_enabled"}):
            await col_settings.insert_one({
                "key": "tgrass_enabled",
                "value": "1"
            })
        if not await col_settings.find_one({"key": "piarflow_enabled"}):
            await col_settings.insert_one({
                "key": "piarflow_enabled",
                "value": "1"
            })
        if not await col_settings.find_one({"key": "subgram_enabled"}):
            await col_settings.insert_one({
                "key": "subgram_enabled",
                # Subgram entegrasyon kodu henüz eklenmedi, varsayılan kapalı
                "value": "0"
            })
        
        print("✅ MongoDB bağlantısı başarılı!")
    except Exception as e:
        print(f"❌ MongoDB hatası: {e}")

# FSM States
class AdminStates(StatesGroup):
    waiting_for_sponsor_channel_id = State()
    waiting_for_sponsor_link = State()
    waiting_for_remove_sponsor_id = State()
    waiting_for_start_text = State()
    waiting_for_vpn_code = State()
    waiting_for_addlist_name = State()
    waiting_for_addlist_link = State()
    waiting_for_remove_addlist_id = State()
    waiting_for_broadcast = State()
    waiting_for_sponsor_position = State()
    waiting_for_addlist_position = State()
    # Post kanalları
    waiting_for_post_channel_name = State()
    waiting_for_post_channel_username = State()
    waiting_for_post_content = State()       # post mesajı bekleniyor
    # Çat sponsor goşmak
    waiting_for_chat_sponsor_id = State()
    waiting_for_chat_sponsor_link = State()
    # Balans doldurmak (diňe Super Admin)
    waiting_for_topup_user_id = State()
    waiting_for_topup_amount = State()
    # Admin / AdminLo dolandyrmak (diňe Super Admin)
    waiting_for_new_admin_id = State()
    waiting_for_new_adminlo_id = State()
    # Ban
    waiting_for_ban_id = State()
    # VPN satyn almak üçin link ibermek (diňe Super Admin)
    waiting_for_vpn_link_send = State()

# Custom emoji ID'leri (icon olarak kullanılacak)
EMOJI_IDS = {
    "check": "5206607081334906820",      # ✔️
    "lock": "5463200466391298413",        # 🔐
    "stats": "5936143551854285132",       # 📊
    "refresh": "6030657343744644592",     # 🔄
    "broadcast": "6021418126061605425",   # 📢
    "edit": "5359488727158634349",        # ✏️
    "add": "5359651386160068849",         # ➕
    "remove": "5359651386160068849",      # ➖
    "vpn": "5206607081334906820",         # ✔️
    "sponsor": "5463200466391298413",     # 🔐
    "addlist": "5206607081334906820",     # ✔️
    "users": "5936143551854285132",       # 📊
    "warning": "5463200466391298413",     # 🔐
    "success": "5206607081334906820",     # ✔️
    "star": "5206607081334906820",        # ⭐
    "money": "5936143551854285132",       # 💰
    "phone": "6021418126061605425",       # 📱
    "people": "5463200466391298413",      # 👥
    "history": "6030657343744644592",     # 📋
    "info": "5359488727158634349",        # ℹ️
    "telegram": "5359651386160068849",    # 🇺🇸
    "thailand": "5206607081334906820",    # 🇹🇭
    "austria": "5463200466391298413",     # 🇦🇹
    "usa": "5359651386160068849",         # 🇺🇸
    "message": "6021418126061605425",     # 📨
    "time": "6030657343744644592",        # ⏰
    "link": "5359488727158634349",        # 🔗
    "tgrass": "5936143551854285132",      # 🌟
    "back": "5359488727158634349",        # ◀️
    "admin": "5463200466391298413",       # 👑
    "settings": "6030657343744644592",    # ⚙️
    "chanel": "5260268501515377807",      # 📣
    "chik": "5427009714745517609",        # ✅
    "del": "5841541824803509441",         # 🗑️
    "tekst": "5879841310902324730",       # ✏️
    "tgrassn": "6032742198179532882",     # ⚙️
    "post": "6021418126061605425",        # 📡
}

# Loglamagy sazlamak
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='bot.log'
)

logging.info(f"Admin ID: {ADMIN_IDS[0]}")

# ================= ROLLAR WE RUHSATLAR (Super Admin / Admin / AdminLo) =================
# Super Admin -> ADMIN_IDS içindäkiler (hardcoded/env). Ähli zada erişimi bar.
# Admin      -> "admin" roly bilen goşulan ulanyjylar. Diňe pul ibermek we VPN link
#               ibermek rugsady ýok, galan ähli zada erişimi bar.
# AdminLo    -> "adminlo" roly bilen goşulan ulanyjylar. Admin bilen aýny rugsatlar,
#               emma admin/adminlo goşup-aýryp bilenok (diňe Super Admin edip biler).

def is_super_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def get_staff_role(user_id: int):
    """Gaýtarýar: 'super' | 'admin' | 'adminlo' | None"""
    if is_super_admin(user_id):
        return "super"
    doc = await col_admins.find_one({"user_id": user_id})
    if doc:
        return doc.get("role")
    return None

async def is_staff(user_id: int) -> bool:
    role = await get_staff_role(user_id)
    return role is not None

async def can_manage_admins(user_id: int) -> bool:
    return is_super_admin(user_id)

async def can_send_balance(user_id: int) -> bool:
    return is_super_admin(user_id)

async def can_send_vpn_link(user_id: int) -> bool:
    return is_super_admin(user_id)

async def add_admin_role(user_id: int, role: str):
    await col_admins.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id, "role": role}},
        upsert=True
    )

async def remove_admin_role(user_id: int):
    await col_admins.delete_one({"user_id": user_id})

async def get_admins_by_role(role: str):
    cursor = col_admins.find({"role": role})
    return await cursor.to_list(length=None)

# ================= BAN ULGAMY =================

async def is_banned(user_id: int) -> bool:
    doc = await col_bans.find_one({"user_id": user_id})
    return doc is not None

async def ban_user(user_id: int):
    await col_bans.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id, "banned_at": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}},
        upsert=True
    )

async def unban_user(user_id: int):
    await col_bans.delete_one({"user_id": user_id})

async def get_banned_users():
    cursor = col_bans.find()
    return await cursor.to_list(length=None)

# ================= TMT BALANS FUNKSIÝALARY =================

async def get_balance_tmt(user_id):
    doc = await col_users.find_one({"user_id": user_id}, {"balance_tmt": 1})
    return round(doc.get("balance_tmt", 0.0), 2) if doc else 0.0

async def add_balance_tmt(user_id, amount):
    await col_users.update_one(
        {"user_id": user_id},
        {"$inc": {"balance_tmt": round(amount, 2)}}
    )

# ================= BONUS ULGAMY (/bonus) =================

BONUS_AMOUNT = 0.5
BONUS_COOLDOWN_HOURS = 24

async def get_last_bonus(user_id):
    doc = await col_users.find_one({"user_id": user_id}, {"last_bonus": 1})
    return doc.get("last_bonus") if doc else None

async def set_last_bonus(user_id):
    await col_users.update_one(
        {"user_id": user_id},
        {"$set": {"last_bonus": datetime.datetime.utcnow().isoformat()}}
    )

# ================= VPN TARIFLER (/buy) =================
# currency: "vgram" | "tmt" | "both" (diňe 1-nji tarif hem Vgram hem TMT bilen alnyp bilner)
VPN_PACKAGES = [
    {"key": "p1", "title": "1 День | 5GB", "days": 1, "gb": 5, "price_vgram": 10, "price_tmt": 5, "currency": "both"},
    {"key": "p2", "title": "1 Неделя | 25GB", "days": 7, "gb": 25, "price_vgram": None, "price_tmt": 25, "currency": "tmt"},
    {"key": "p3", "title": "1 Неделя VIP | 35GB", "days": 7, "gb": 35, "price_vgram": None, "price_tmt": 35, "currency": "tmt"},
    {"key": "p4", "title": "1 Месяц | 80GB", "days": 30, "gb": 80, "price_vgram": None, "price_tmt": 80, "currency": "tmt"},
    {"key": "p5", "title": "1 Год | 100GB", "days": 365, "gb": 100, "price_vgram": None, "price_tmt": 100, "currency": "tmt"},
]

def get_vpn_package(key):
    return next((p for p in VPN_PACKAGES if p["key"] == key), None)

def generate_check_number():
    return str(random.randint(1000000000, 9999999999))

async def create_purchase(user_id, package_key, currency, price):
    check_number = generate_check_number()
    doc = {
        "user_id": user_id,
        "package_key": package_key,
        "currency": currency,
        "price": price,
        "check_number": check_number,
        "status": "pending",   # pending -> link_sent
        "vpn_link": None,
        "created_at": datetime.datetime.utcnow().isoformat(),
        "expires_at": None,
    }
    result = await col_purchases.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc

async def get_pending_purchase_for_user(user_id):
    return await col_purchases.find_one({"user_id": user_id, "status": "pending"}, sort=[("created_at", -1)])

async def fulfill_purchase(purchase_id, vpn_link):
    purchase = await col_purchases.find_one({"_id": purchase_id})
    if not purchase:
        return None
    package = get_vpn_package(purchase["package_key"])
    days = package["days"] if package else 1
    expires_at = (datetime.datetime.utcnow() + datetime.timedelta(days=days)).isoformat()
    await col_purchases.update_one(
        {"_id": purchase_id},
        {"$set": {"status": "link_sent", "vpn_link": vpn_link, "expires_at": expires_at}}
    )
    purchase["vpn_link"] = vpn_link
    purchase["expires_at"] = expires_at
    purchase["status"] = "link_sent"
    return purchase

async def get_user_vpn_packages(user_id):
    cursor = col_purchases.find({"user_id": user_id, "status": "link_sent"}).sort("created_at", -1)
    return await cursor.to_list(length=None)

def format_remaining_time(expires_at_iso):
    try:
        expires_at = datetime.datetime.fromisoformat(expires_at_iso)
    except Exception:
        return "Неизвестно"
    now = datetime.datetime.utcnow()
    if expires_at <= now:
        return "Истёк"
    delta = expires_at - now
    days = delta.days
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60
    if days > 0:
        return f"{days} д. {hours} ч."
    if hours > 0:
        return f"{hours} ч. {minutes} мин."
    return f"{minutes} мин."

# ================= TGRASS FUNKSIÝALARY =================
def get_user_language(user_id):
    return 'ru'

async def check_tgrass_subscriptions(user_id, username=None, is_premium=False):
    try:
        import httpx
        payload = {
            "tg_user_id": int(user_id),
            "tg_login": username or "",
            "lang": get_user_language(user_id),
            "is_premium": bool(is_premium),
        }
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "Auth": TGRASS_API_KEY,
        }
        
        logging.info(f"TGrass API istek: {payload}")
        async with httpx.AsyncClient(verify=False, timeout=60) as client:
            response = await client.post(TGRASS_API_URL, json=payload, headers=headers)
        
        if response.status_code == 200:
            resp_json = response.json()
            logging.info(f"TGrass API cevap: {resp_json}")
            
            if resp_json.get("status") == "not_ok":
                offers = resp_json.get("offers", [])
                formatted_offers = []
                for offer in offers:
                    channel_name = None
                    if "title" in offer and offer["title"]:
                        channel_name = offer["title"]
                    elif "name" in offer and offer["name"]:
                        channel_name = offer["name"]
                    elif "channel_name" in offer and offer["channel_name"]:
                        channel_name = offer["channel_name"]
                    elif "description" in offer and offer["description"]:
                        channel_name = offer["description"][:30]
                    else:
                        channel_name = "Спонсор канал"
                    
                    channel_link = None
                    if "link" in offer and offer["link"]:
                        channel_link = offer["link"]
                    elif "url" in offer and offer["url"]:
                        channel_link = offer["url"]
                    elif "channel_link" in offer and offer["channel_link"]:
                        channel_link = offer["channel_link"]
                    else:
                        channel_link = "#"
                    
                    formatted_offers.append({
                        "title": channel_name,
                        "link": channel_link,
                        "id": offer.get("id", 0)
                    })
                
                return formatted_offers
        return []
    except Exception as e:
        logging.error(f"TGrass error: {e}")
        return []

# ================= PIARFLOW FUNKSIÝALARY =================
async def check_piarflow_subscriptions(user_id, username=None, is_premium=False):
    """PiarFlow API'sinden kullanıcının henüz tamamlamadığı sponsor görevlerini döner."""
    if not PIARFLOW_API_KEY:
        return []
    try:
        import httpx
        headers = {
            "Authorization": f"Bearer {PIARFLOW_API_KEY}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(verify=False, timeout=60) as client:
            resp = await client.post(
                f"{PIARFLOW_API_URL}/sponsors",
                json={
                    "user_id": int(user_id),
                    "chat_id": int(user_id),
                    "max_sponsors": 5,
                },
                headers=headers,
            )

        if resp.status_code >= 400:
            logging.error(f"PiarFlow /sponsors hata: {resp.status_code} {resp.text}")
            return []

        data = resp.json()
        sponsors = data.get("sponsors") or []
        if not sponsors:
            return []

        links = [s.get("link") for s in sponsors if s.get("link")]

        statuses = {}
        if links:
            async with httpx.AsyncClient(verify=False, timeout=60) as client:
                check_resp = await client.post(
                    f"{PIARFLOW_API_URL}/sponsors/check",
                    json={"user_id": int(user_id), "links": links},
                    headers=headers,
                )
            if check_resp.status_code < 400:
                check_data = check_resp.json()
                for item in check_data.get("sponsors") or []:
                    statuses[item.get("link")] = item.get("status")
            else:
                logging.error(f"PiarFlow /sponsors/check hata: {check_resp.status_code} {check_resp.text}")

        pending = []
        for s in sponsors:
            link = s.get("link")
            if statuses.get(link) == "subscribed":
                continue
            pending.append({
                "title": s.get("title") or s.get("name") or "Спонсор канал",
                "link": link or "#",
                "id": s.get("id", 0),
            })
        return pending
    except Exception as e:
        logging.error(f"PiarFlow error: {e}")
        return []

async def get_piarflow_enabled():
    doc = await col_settings.find_one({"key": "piarflow_enabled"})
    return doc["value"] == "1" if doc else True

async def set_piarflow_enabled(enabled):
    await col_settings.update_one(
        {"key": "piarflow_enabled"},
        {"$set": {"value": "1" if enabled else "0"}},
        upsert=True
    )

async def get_subgram_enabled():
    doc = await col_settings.find_one({"key": "subgram_enabled"})
    return doc["value"] == "1" if doc else False

async def set_subgram_enabled(enabled):
    await col_settings.update_one(
        {"key": "subgram_enabled"},
        {"$set": {"value": "1" if enabled else "0"}},
        upsert=True
    )

# ================= SUBGRAM FUNKSIÝALARY =================
async def check_subgram_subscriptions(user_id, username=None, is_premium=False):
    """Subgram API-den ulanyjynyň entäk ýerine ýetirmedik sponsor tabşyryklaryny gaýtarýar.

    Bot ähli sponsorlary (TGrass/PiarFlow/Subgram) bir ýerde birleşdirip görkezýär,
    şonuň üçin bu funksiýa diňe "Получать ссылки в API" (API arkaly link almak)
    режimi Subgram.org sazlamalarynda AÇYK bolanda doly işleýär. Ol режim ÖÇÜRILEN
    bolsa, Subgram jogabynda "additional" bolmaýar we ol ýagdaýda bot hiç bir
    sponsor kanaly görkezip bilmeýär (aşakdaky log ýazgysyny serediň).
    """
    if not SUBGRAM_API_KEY:
        return []
    try:
        import httpx
        headers = {"Auth": SUBGRAM_API_KEY}
        payload = {
            "user_id": int(user_id),
            "chat_id": int(user_id),
            "username": username,
            "is_premium": bool(is_premium),
        }

        async with httpx.AsyncClient(verify=False, timeout=15) as client:
            resp = await client.post(SUBGRAM_API_URL, headers=headers, json=payload)

        if resp.status_code >= 400:
            logging.error(f"Subgram API hata: {resp.status_code} {resp.text}")
            return []

        data = resp.json()
        status = data.get("status")

        # "ok" -> hemme tabşyryk ýerine ýetirilen, "error" -> geçirilýär (bloklanmaýar)
        if status != "warning":
            return []

        additional = data.get("additional") or {}
        sponsors = additional.get("sponsors") or []

        if not sponsors:
            if "additional" not in data:
                logging.warning(
                    "Subgram: 'Получать ссылки в API' режimi öçürilen. "
                    "subgram.org bot sazlamalaryndan ony açyň, ýogsam bu bot "
                    "sponsor kanallaryny özi görkezip bilmeýär."
                )
            return []

        # links -> entäk ýerine ýetirilmedik sponsorlaryň linkleri
        pending = set(data.get("links") or [])

        offers = []
        for i, sponsor in enumerate(sponsors):
            link = sponsor.get("link")
            if not link:
                continue
            if pending:
                if link not in pending:
                    continue  # eýýäm ýerine ýetirilen
            elif not (sponsor.get("available_now") and sponsor.get("status") == "unsubscribed"):
                continue

            offers.append({
                "title": sponsor.get("button_text") or sponsor.get("title") or sponsor.get("name") or "Спонсор канал",
                "link": link,
                "id": sponsor.get("id", i),
            })

        return offers
    except Exception as e:
        logging.error(f"Subgram error: {e}")
        return []

def parse_premium_emoji(text):
    pattern = r'<tg-emoji emoji-id="([^"]+)">([^<]+)</tg-emoji>'
    
    def replace_emoji(match):
        emoji_id = match.group(1)
        emoji_char = match.group(2)
        return f'<tg-emoji emoji-id="{emoji_id}">{emoji_char}</tg-emoji>'
    
    return re.sub(pattern, replace_emoji, text)

# ================= MongoDB VERİTABANI FONKSİYONLARI =================

async def get_setting(key):
    doc = await col_settings.find_one({"key": key})
    return doc["value"] if doc else ""

async def set_setting(key, value):
    await col_settings.update_one(
        {"key": key},
        {"$set": {"value": value}},
        upsert=True
    )

async def get_sponsors():
    cursor = col_sponsors.find().sort("position", 1)
    return await cursor.to_list(length=None)

async def add_sponsor(channel_id, link, position):
    await col_sponsors.insert_one({
        "channel_id": channel_id,
        "link": link,
        "position": position
    })

async def delete_sponsor(doc_id):
    await col_sponsors.delete_one({"_id": ObjectId(doc_id)})

async def get_addlists():
    cursor = col_addlists.find().sort("position", 1)
    return await cursor.to_list(length=None)

async def add_addlist(name, link, position):
    await col_addlists.insert_one({
        "name": name,
        "link": link,
        "position": position
    })

async def delete_addlist(doc_id):
    await col_addlists.delete_one({"_id": ObjectId(doc_id)})

async def get_all_users():
    cursor = col_users.find({}, {"user_id": 1})
    return [doc["user_id"] async for doc in cursor]

async def add_user(user_id, username, referred_by=None):
    existing = await col_users.find_one({"user_id": user_id})
    if existing:
        return False
    await col_users.insert_one({
        "user_id": user_id,
        "username": username or "",
        "join_date": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "balance": 0.0,
        "balance_tmt": 0.0,
        "last_bonus": None,
        "referred_by": referred_by,
        "referral_rewarded": False
    })
    return True

async def get_user(user_id):
    return await col_users.find_one({"user_id": user_id})

async def get_balance(user_id):
    doc = await col_users.find_one({"user_id": user_id}, {"balance": 1})
    return round(doc["balance"], 2) if doc else 0.0

async def add_balance(user_id, amount):
    await col_users.update_one(
        {"user_id": user_id},
        {"$inc": {"balance": round(amount, 2)}}
    )

async def get_ref_count(user_id):
    return await col_users.count_documents({"referred_by": user_id})

async def set_rewarded(user_id):
    await col_users.update_one(
        {"user_id": user_id},
        {"$set": {"referral_rewarded": True}}
    )

async def get_post_channels():
    cursor = col_post_channels.find().sort("_id", 1)
    return await cursor.to_list(length=None)

async def add_post_channel(name, username):
    uname = username.strip().lstrip("@")
    await col_post_channels.update_one(
        {"username": uname},
        {"$set": {"name": name, "username": uname}},
        upsert=True
    )
    return True

async def delete_post_channel(channel_id):
    await col_post_channels.delete_one({"_id": ObjectId(channel_id)})
    return True

async def save_sent_ad(chat_id, message_id):
    await col_sent_ads.insert_one({
        "chat_id": str(chat_id),
        "message_id": message_id
    })

async def get_sent_ads():
    cursor = col_sent_ads.find()
    return [(doc["chat_id"], doc["message_id"]) async for doc in cursor]

async def clear_sent_ads():
    await col_sent_ads.delete_many({})

async def get_tgrass_enabled():
    doc = await col_settings.find_one({"key": "tgrass_enabled"})
    return doc["value"] == "1" if doc else True

async def set_tgrass_enabled(enabled):
    await col_settings.update_one(
        {"key": "tgrass_enabled"},
        {"$set": {"value": "1" if enabled else "0"}},
        upsert=True
    )

async def get_stats():
    total = await col_users.count_documents({})
    return total, 0, 0

async def get_new_users_today():
    today_start = datetime.datetime.utcnow().strftime("%Y-%m-%d 00:00:00")
    return await col_users.count_documents({"join_date": {"$gte": today_start}})

async def get_vpn_stats():
    now = datetime.datetime.utcnow()
    today_start = now.strftime("%Y-%m-%d 00:00:00")
    week_start = (now - datetime.timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    month_start = (now - datetime.timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

    today_count = await col_users.count_documents({"vpn_taken_date": {"$gte": today_start}})
    week_count = await col_users.count_documents({"vpn_taken_date": {"$gte": week_start}})
    month_count = await col_users.count_documents({"vpn_taken_date": {"$gte": month_start}})

    return today_count, week_count, month_count

# ================= TGRASS FUNKSIÝALARY (Async) =================

async def check_tgrass_subscriptions_async(user_id, username=None, is_premium=False):
    return await check_tgrass_subscriptions(user_id, username, is_premium)

async def get_channel_name(channel_id=None, link=None):
    try:
        if channel_id:
            chat = await bot.get_chat(channel_id)
            return chat.title or f"Канал {channel_id}"
        elif link and link.startswith('https://t.me/'):
            username = link.replace('https://t.me/', '@')
            chat = await bot.get_chat(username)
            return chat.title or username
        else:
            return link.split('/')[-1] if link else "Неизвестный канал"
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return link.split('/')[-1] if link else "Неизвестный канал"

async def get_all_channels(user_id, username=None, is_premium=False):
    sponsors = await get_sponsors()
    addlists = await get_addlists()
    used_urls = set()
    all_channels = []

    for sponsor in sponsors:
        link = sponsor.get("link", "")
        channel_id = sponsor.get("channel_id")
        if link in used_urls or sponsor.get("position") is None:
            continue
        # Zaten abone olunan sponsor kanalları listeye eklenmez
        if channel_id and await is_user_subscribed(user_id, channel_id):
            continue
        used_urls.add(link)
        all_channels.append({
            'id': str(sponsor["_id"]),
            'link': link,
            'position': sponsor.get("position", 0),
            'channel_id': channel_id,
            'type': 'sponsor',
            'name': await get_channel_name(channel_id=channel_id),
            'is_tgrass': False
        })

    for addlist in addlists:
        link = addlist.get("link", "")
        if link not in used_urls and addlist.get("position") is not None:
            used_urls.add(link)
            all_channels.append({
                'id': str(addlist["_id"]),
                'link': link,
                'position': addlist.get("position", 0),
                'channel_id': None,
                'type': 'addlist',
                'name': addlist.get("name", ""),
                'is_tgrass': False
            })

    tgrass_enabled = await get_tgrass_enabled()
    if tgrass_enabled:
        tgrass_offers = await check_tgrass_subscriptions_async(user_id, username, is_premium)
        if tgrass_offers:
            max_position = len(all_channels) + 1
            for i, offer in enumerate(tgrass_offers):
                channel_name = offer.get('title', 'Спонсор канал')
                if not channel_name or channel_name == 'Bilinmeýän':
                    channel_name = f"Канал {i+1}"
                
                all_channels.append({
                    'id': f"tgrass_{i}",
                    'link': offer.get('link', '#'),
                    'position': max_position + i,
                    'channel_id': None,
                    'type': 'tgrass',
                    'name': channel_name,
                    'is_tgrass': True,
                    'offer_id': offer.get('id', i)
                })

    piarflow_enabled = await get_piarflow_enabled()
    if piarflow_enabled:
        piarflow_offers = await check_piarflow_subscriptions(user_id, username, is_premium)
        if piarflow_offers:
            max_position = len(all_channels) + 1
            for i, offer in enumerate(piarflow_offers):
                channel_name = offer.get('title', 'Спонсор канал')
                if not channel_name:
                    channel_name = f"Канал {i+1}"

                all_channels.append({
                    'id': f"piarflow_{i}",
                    'link': offer.get('link', '#'),
                    'position': max_position + i,
                    'channel_id': None,
                    'type': 'piarflow',
                    'name': channel_name,
                    'is_tgrass': False,
                    'offer_id': offer.get('id', i)
                })
    
    subgram_enabled = await get_subgram_enabled()
    if subgram_enabled:
        subgram_offers = await check_subgram_subscriptions(user_id, username, is_premium)
        if subgram_offers:
            max_position = len(all_channels) + 1
            for i, offer in enumerate(subgram_offers):
                channel_name = offer.get('title', 'Спонсор канал')
                if not channel_name:
                    channel_name = f"Канал {i+1}"

                all_channels.append({
                    'id': f"subgram_{i}",
                    'link': offer.get('link', '#'),
                    'position': max_position + i,
                    'channel_id': None,
                    'type': 'subgram',
                    'name': channel_name,
                    'is_tgrass': False,
                    'offer_id': offer.get('id', i)
                })

    all_channels.sort(key=lambda x: x['position'])
    return all_channels

async def check_all_subscriptions(user_id, username=None, is_premium=False):
    not_subscribed = []
    
    sponsors = await get_sponsors()
    for sponsor in sponsors:
        channel_id = sponsor.get("channel_id")
        if channel_id and not await is_user_subscribed(user_id, channel_id):
            not_subscribed.append({
                'name': await get_channel_name(channel_id=channel_id),
                'link': sponsor.get("link", ""),
                'type': 'sponsor'
            })
    
    tgrass_enabled = await get_tgrass_enabled()
    if tgrass_enabled:
        tgrass_offers = await check_tgrass_subscriptions_async(user_id, username, is_premium)
        if tgrass_offers:
            for offer in tgrass_offers:
                channel_name = offer.get('title', 'Спонсор канал')
                if not channel_name or channel_name == 'Bilinmeýän':
                    channel_name = "Спонсор канал"
                not_subscribed.append({
                    'name': channel_name,
                    'link': offer.get('link', '#'),
                    'type': 'tgrass'
                })

    piarflow_enabled = await get_piarflow_enabled()
    if piarflow_enabled:
        piarflow_offers = await check_piarflow_subscriptions(user_id, username, is_premium)
        if piarflow_offers:
            for offer in piarflow_offers:
                channel_name = offer.get('title', 'Спонсор канал')
                not_subscribed.append({
                    'name': channel_name,
                    'link': offer.get('link', '#'),
                    'type': 'piarflow'
                })

    subgram_enabled = await get_subgram_enabled()
    if subgram_enabled:
        subgram_offers = await check_subgram_subscriptions(user_id, username, is_premium)
        if subgram_offers:
            for offer in subgram_offers:
                channel_name = offer.get('title', 'Спонсор канал')
                not_subscribed.append({
                    'name': channel_name,
                    'link': offer.get('link', '#'),
                    'type': 'subgram'
                })
    
    return len(not_subscribed) == 0, not_subscribed

async def is_user_subscribed(user_id, channel_id):
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return False

# ── Post kanalları menüsünü göster ────────────────────────────────────────────
async def show_post_channels_menu(chat_id: int, message_id: int):
    channels = await get_post_channels()
    builder = InlineKeyboardBuilder()

    if channels:
        for ch in channels:
            ch_id = str(ch["_id"])
            name = ch.get("name", "")
            uname = ch.get("username", "")
            builder.row(
                InlineKeyboardButton(
                    text=f"📺 {name} @{uname}",
                    callback_data=f"pch_send_{ch_id}"
                ),
                InlineKeyboardButton(
                    text="🗑",
                    callback_data=f"pch_del_{ch_id}"
                )
            )
    
    builder.row(
        InlineKeyboardButton(
            text="🚀 Отправить во все",
            callback_data="pch_send_all"
        ),
        InlineKeyboardButton(
            text="➕ Добавить канал",
            callback_data="pch_add"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="back_to_admin"
        )
    )

    total = len(channels)
    await bot.edit_message_text(
        f"📡 <b>Пост-каналы</b>\n\n"
        f"Каналов в списке: <b>{total}</b>\n\n"
        f"📤 <b>Синий</b> — отправить пост\n"
        f"🗑 <b>Красный</b> — удалить канал\n\n"
        f"Выберите канал или добавьте новый:",
        chat_id=chat_id,
        message_id=message_id,
        reply_markup=builder.as_markup()
    )

# ── Addlist menüsünü göster ────────────────────────────────────────────────────
async def show_addlists_menu(call: CallbackQuery):
    addlists = await get_addlists()
    if not addlists:
        await call.message.edit_text("❌ Список Addlist пуст.")
        await call.answer()
        return
    
    text = f"<tg-emoji emoji-id=\"{EMOJI_IDS['remove']}\">➖</tg-emoji> <b>Выберите Addlist для удаления:</b>\n\n"
    builder = InlineKeyboardBuilder()
    
    for addlist in addlists:
        addlist_id = str(addlist["_id"])
        builder.row(
            InlineKeyboardButton(
                text=f"🗑 {addlist.get('name', '')}",
                callback_data=f"del_al_{addlist_id}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="back_to_admin"
        )
    )
    
    await call.message.edit_text(text, reply_markup=builder.as_markup())
    await call.answer()

# ── Addlist silme handler ──────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("del_al_"))
async def process_delete_addlist(call: CallbackQuery):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    try:
        al_id = call.data.split("_")[2]
        # MongoDB'den asenkron sil
        await delete_addlist(al_id)
        await call.answer("✅ Addlist удален!", show_alert=True)
        # Menüyü yenile
        await show_addlists_menu(call)
    except Exception as e:
        logging.error(f"Addlist silme hatası: {e}")
        await call.answer("❌ Ошибка при удалении!", show_alert=True)

# /start komut - AYNEN KALDI, HİÇBİR DEĞİŞİKLİK YOK
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    is_premium = getattr(message.from_user, 'is_premium', False)

    if await is_banned(user_id):
        await message.answer("🚫 Вы заблокированы и не можете пользоваться ботом.")
        return

    await add_user(user_id, username or message.from_user.first_name)

    # Kanallar çekilýänçä görkezilýän garaşma habary
    wait_msg = await message.answer("⏳ Kanallar çekilýär, garaşyň✅")

    start_text = await get_setting('start_text')
    if not start_text:
        start_text = (
            f"<tg-emoji emoji-id=\"{EMOJI_IDS['lock']}\">🔐</tg-emoji> <b>Добро пожаловать!</b>\n\n"
            f"Для получения VPN кода необходимо подписаться на каналы ниже.\n\n"
            f"После подписки нажмите кнопку «Подписался»"
        )
    else:
        start_text = parse_premium_emoji(start_text)

    all_channels = await get_all_channels(user_id, username, is_premium)
    
    if not all_channels:
        await wait_msg.edit_text(
            f"<tg-emoji emoji-id=\"{EMOJI_IDS['warning']}\">🔐</tg-emoji> Каналы не найдены. Свяжитесь с администратором."
        )
        return

    builder = InlineKeyboardBuilder()
    for channel in all_channels:
        if channel['type'] == 'tgrass':
            builder.button(text=f"{channel['name']}", url=channel['link'],
            style="primary",
            icon_custom_emoji_id=EMOJI_IDS["chanel"]
        )
        else:
            builder.button(text=channel['name'], url=channel['link'],
            style="primary",
            icon_custom_emoji_id=EMOJI_IDS["chanel"]
        )
    
    builder.button(
        text="Подписался",
        callback_data="check_sub",
        style="success",
        icon_custom_emoji_id=EMOJI_IDS["chik"]
    )
    
    builder.adjust(2)
    
    try:
        await wait_msg.edit_text(start_text, reply_markup=builder.as_markup())
    except Exception:
        # edit_text HTML/markup sebäpli säwlik berse, täze habar iberilýär
        await wait_msg.delete()
        await message.answer(start_text, reply_markup=builder.as_markup())

# Check subscription callback
@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(call: CallbackQuery):
    user_id = call.from_user.id
    username = call.from_user.username
    is_premium = getattr(call.from_user, 'is_premium', False)

    is_subscribed, not_subscribed = await check_all_subscriptions(user_id, username, is_premium)

    if not is_subscribed:
        text = f"<tg-emoji emoji-id=\"{EMOJI_IDS['warning']}\">🔐</tg-emoji> <b>Вы не подписались на следующие каналы:</b>\n\n"
        for channel in not_subscribed:
            text += f"• {channel['name']}\n"
        text += "\nПодпишитесь и нажмите кнопку снова."
        await call.answer(text=text, show_alert=True)
    else:
        await call.answer(text="✅ Вы подписались на все каналы!", show_alert=True)
        vpn_code = await get_setting('vpn_code')
        if vpn_code:
            await col_users.update_one(
                {"user_id": user_id},
                {"$set": {"vpn_taken_date": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}}
            )
            await call.message.answer(
                f"<tg-emoji emoji-id=\"{EMOJI_IDS['vpn']}\">✔️</tg-emoji> <b>Ваш VPN код:</b> <code>{vpn_code}</code>"
            )
        else:
            await call.message.answer(
                f"<tg-emoji emoji-id=\"{EMOJI_IDS['warning']}\">🔐</tg-emoji> VPN код еще не настроен администратором."
            )

# ── Admin panel klawiaturasyny gurmak (rola görä) ─────────────────────────────
async def build_admin_panel_keyboard(user_id: int) -> InlineKeyboardMarkup:
    role = await get_staff_role(user_id)
    is_super = (role == "super")

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="Добавить спонсора",
            callback_data="add_sponsor",
            icon_custom_emoji_id=EMOJI_IDS["add"]
        ),
        InlineKeyboardButton(
            text="Удалить спонсора",
            callback_data="remove_sponsor",
            icon_custom_emoji_id=EMOJI_IDS["del"]
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="Добавить чат-спонсора",
            callback_data="add_chat_sponsor",
            icon_custom_emoji_id=EMOJI_IDS["add"]
        ),
        InlineKeyboardButton(
            text="🔀 Порядок спонсоров",
            callback_data="sponsor_order"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="Изменить start текст",
            callback_data="edit_start",
            icon_custom_emoji_id=EMOJI_IDS["tekst"]
        ),
        InlineKeyboardButton(
            text="Изменить VPN код",
            callback_data="edit_code",
            icon_custom_emoji_id=EMOJI_IDS["lock"]
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="Добавить Addlist",
            callback_data="add_addlist",
            icon_custom_emoji_id=EMOJI_IDS["add"]
        ),
        InlineKeyboardButton(
            text="Удалить Addlist",
            callback_data="remove_addlist",
            icon_custom_emoji_id=EMOJI_IDS["del"]
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="Рассылка",
            callback_data="broadcast",
            icon_custom_emoji_id=EMOJI_IDS["broadcast"]
        ),
        InlineKeyboardButton(
            text="Статистика",
            callback_data="stats",
            icon_custom_emoji_id=EMOJI_IDS["stats"]
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="Пост в каналы",
            callback_data="post_channels_menu",
            icon_custom_emoji_id=EMOJI_IDS["post"]
        ),
        InlineKeyboardButton(
            text="Удалить посты",
            callback_data="delete_posts",
            icon_custom_emoji_id=EMOJI_IDS["del"]
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="TGrass настройки",
            callback_data="tgrass_settings",
            icon_custom_emoji_id=EMOJI_IDS["tgrassn"]
        )
    )

    builder.row(
        InlineKeyboardButton(text="🚫 Бан", callback_data="ban_user_start"),
        InlineKeyboardButton(text="✅ Убрать бан", callback_data="unban_list")
    )

    # Diňe Super Admin görýän düwmeler
    if is_super:
        builder.row(
            InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="topup_start")
        )
        builder.row(
            InlineKeyboardButton(text="➕ Добавить админа", callback_data="add_admin_start"),
            InlineKeyboardButton(text="➖ Удалить админа", callback_data="remove_admin_list")
        )
        builder.row(
            InlineKeyboardButton(text="➕ Добавить AdminLo", callback_data="add_adminlo_start"),
            InlineKeyboardButton(text="➖ Удалить AdminLo", callback_data="remove_adminlo_list")
        )

    return builder.as_markup()

# Admin panel - style parametreleri kaldırıldı, premium emojiler korundu
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if not await is_staff(message.from_user.id):
        await message.answer(
            f"<tg-emoji emoji-id=\"{EMOJI_IDS['warning']}\">🔐</tg-emoji> Вы не администратор!"
        )
        return

    markup = await build_admin_panel_keyboard(message.from_user.id)
    await message.answer(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['admin']}\">👑</tg-emoji> <b>Админ панель</b>",
        reply_markup=markup
    )

# ================= ADMIN CALLBACK HANDLERS =================

@dp.callback_query(F.data == "add_sponsor")
async def add_sponsor_start(call: CallbackQuery, state: FSMContext):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    await call.message.edit_text(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['add']}\">➕</tg-emoji> <b>Добавление спонсора</b>\n\n"
        f"Отправьте ID канала (например: -1001234567890)\n"
        f"Или отправьте /cancel для отмены."
    )
    await state.set_state(AdminStates.waiting_for_sponsor_channel_id)
    await call.answer()

@dp.message(AdminStates.waiting_for_sponsor_channel_id)
async def process_sponsor_channel_id(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Операция отменена.")
        return
    
    channel_id = message.text.strip()
    await state.update_data(channel_id=channel_id)
    
    await message.answer(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['link']}\">🔗</tg-emoji> Теперь отправьте ссылку на канал (например: https://t.me/channelname)"
    )
    await state.set_state(AdminStates.waiting_for_sponsor_link)

@dp.message(AdminStates.waiting_for_sponsor_link)
async def process_sponsor_link(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Операция отменена.")
        return
    
    link = message.text.strip()
    data = await state.get_data()
    channel_id = data.get('channel_id')
    
    sponsors = await get_sponsors()
    max_pos = max([s.get("position", 0) for s in sponsors]) if sponsors else 0
    new_position = max_pos + 1
    
    await add_sponsor(channel_id, link, new_position)
    
    await message.answer(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['success']}\">✅</tg-emoji> Спонсор успешно добавлен!\n"
        f"ID: {channel_id}\nСсылка: {link}"
    )
    
    await state.clear()

# ── Sponsor Silme Menüsü ────────────────────────────────────────────────────────
@dp.callback_query(F.data == "remove_sponsor")
async def remove_sponsor_start(call: CallbackQuery):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    sponsors = await get_sponsors()
    if not sponsors:
        await call.message.edit_text("❌ Список спонсоров пуст.")
        await call.answer()
        return
    
    text = f"<tg-emoji emoji-id=\"{EMOJI_IDS['remove']}\">➖</tg-emoji> <b>Выберите спонсора для удаления:</b>\n\n"
    builder = InlineKeyboardBuilder()
    
    for sponsor in sponsors:
        sponsor_id = str(sponsor["_id"])
        name = await get_channel_name(channel_id=sponsor.get("channel_id"))
        builder.row(
            InlineKeyboardButton(
                text=f" {name}",
                callback_data=f"del_sponsor_{sponsor_id}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="back_to_admin"
        )
    )
    
    await call.message.edit_text(text, reply_markup=builder.as_markup())
    await call.answer()

# ── Sponsor Silme Handler ──────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("del_sponsor_"))
async def delete_sponsor_callback(call: CallbackQuery):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    # callback_data'dan ID'yi al
    doc_id = call.data.replace("del_sponsor_", "")
    
    try:
        # MongoDB'den sil
        await delete_sponsor(doc_id)
        await call.answer("✅ Спонсор удален!", show_alert=True)
        
        # Menüyü yenile
        await remove_sponsor_start(call)
    except Exception as e:
        logging.error(f"Sponsor silme hatası: {e}")
        await call.answer("❌ Ошибка при удалении!", show_alert=True)

@dp.callback_query(F.data == "edit_start")
async def edit_start_text(call: CallbackQuery, state: FSMContext):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    current_text = await get_setting('start_text')
    
    await call.message.edit_text(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['edit']}\">✏️</tg-emoji> <b>Изменение стартового сообщения</b>\n\n"
        f"<b>Текущий текст:</b>\n{current_text if current_text else 'Стандартный текст'}\n\n"
        f"<b>Отправьте новый текст:</b>\n"
        f"Вы можете использовать HTML теги:\n"
        f"• <code>&lt;b&gt;жирный&lt;/b&gt;</code> - <b>жирный</b>\n"
        f"• <code>&lt;i&gt;курсив&lt;/i&gt;</code> - <i>курсив</i>\n"
        f"• <code>&lt;u&gt;подчеркнутый&lt;/u&gt;</code> - <u>подчеркнутый</u>\n"
        f"• <code>&lt;s&gt;зачеркнутый&lt;/s&gt;</code> - <s>зачеркнутый</s>\n"
        f"• <code>&lt;code&gt;моноширинный&lt;/code&gt;</code> - <code>моноширинный</code>\n"
        f"• <code>&lt;a href='url'&gt;ссылка&lt;/a&gt;</code> - ссылка\n\n"
        f"<b>Premium эмодзи:</b>\n"
        f"Отправьте любое premium эмодзи из Telegram, и бот автоматически сохранит его ID.\n\n"
        f"Отправьте /cancel для отмены."
    )
    await state.set_state(AdminStates.waiting_for_start_text)
    await call.answer()

@dp.message(AdminStates.waiting_for_start_text)
async def process_start_text(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Операция отменена.")
        return
    
    new_text = message.html_text if message.html_text else message.text
    
    if message.entities:
        for entity in message.entities:
            if entity.type == "custom_emoji":
                emoji_id = entity.custom_emoji_id
                logging.info(f"Premium emoji found: {emoji_id}")
    
    await set_setting('start_text', new_text)
    
    preview_text = parse_premium_emoji(new_text)
    await message.answer(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['success']}\">✅</tg-emoji> <b>Текст сохранен!</b>\n\n"
        f"<b>Предпросмотр:</b>\n{preview_text}",
        parse_mode=ParseMode.HTML
    )
    
    await state.clear()

@dp.callback_query(F.data == "edit_code")
async def edit_vpn_code(call: CallbackQuery, state: FSMContext):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    current_code = await get_setting('vpn_code')
    
    await call.message.edit_text(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['lock']}\">🔐</tg-emoji> <b>Изменение VPN кода</b>\n\n"
        f"Текущий код: <code>{current_code if current_code else 'Не установлен'}</code>\n\n"
        f"Отправьте новый VPN код или /cancel для отмены."
    )
    await state.set_state(AdminStates.waiting_for_vpn_code)
    await call.answer()

@dp.message(AdminStates.waiting_for_vpn_code)
async def process_vpn_code(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Операция отменена.")
        return
    
    new_code = message.text.strip()
    await set_setting('vpn_code', new_code)
    
    await message.answer(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['success']}\">✅</tg-emoji> VPN код сохранен: <code>{new_code}</code>"
    )
    await state.clear()

@dp.callback_query(F.data == "add_addlist")
async def add_addlist_start(call: CallbackQuery, state: FSMContext):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    await call.message.edit_text(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['add']}\">➕</tg-emoji> <b>Добавление Addlist</b>\n\n"
        f"Отправьте название для отображения или /cancel для отмены."
    )
    await state.set_state(AdminStates.waiting_for_addlist_name)
    await call.answer()

@dp.message(AdminStates.waiting_for_addlist_name)
async def process_addlist_name(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Операция отменена.")
        return
    
    name = message.text.strip()
    await state.update_data(name=name)
    
    await message.answer(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['link']}\">🔗</tg-emoji> Теперь отправьте ссылку:"
    )
    await state.set_state(AdminStates.waiting_for_addlist_link)

@dp.message(AdminStates.waiting_for_addlist_link)
async def process_addlist_link(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Операция отменена.")
        return
    
    link = message.text.strip()
    data = await state.get_data()
    name = data.get('name')
    
    addlists = await get_addlists()
    max_pos = max([a.get("position", 0) for a in addlists]) if addlists else 0
    new_position = max_pos + 1
    
    await add_addlist(name, link, new_position)
    
    await message.answer(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['success']}\">✅</tg-emoji> Addlist успешно добавлен!\n"
        f"Название: {name}\nСсылка: {link}"
    )
    
    await state.clear()

@dp.callback_query(F.data == "remove_addlist")
async def remove_addlist_start(call: CallbackQuery):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    await show_addlists_menu(call)

@dp.callback_query(F.data == "broadcast")
async def broadcast_start(call: CallbackQuery, state: FSMContext):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    await call.message.edit_text(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['broadcast']}\">📢</tg-emoji> <b>Рассылка</b>\n\n"
        f"Отправьте сообщение для рассылки всем пользователям.\n"
        f"Отправьте /cancel для отмены."
    )
    await state.set_state(AdminStates.waiting_for_broadcast)
    await call.answer()

@dp.message(AdminStates.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Операция отменена.")
        return
    
    users = await get_all_users()
    success = 0
    failed = 0
    
    await message.answer(f"📤 Начинаю рассылку для {len(users)} пользователей...")
    
    for user_id in users:
        try:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            success += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            failed += 1
            logging.error(f"Broadcast error for {user_id}: {e}")
    
    await message.answer(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['stats']}\">📊</tg-emoji> <b>Рассылка завершена!</b>\n\n"
        f"✅ Успешно: {success}\n"
        f"❌ Ошибок: {failed}"
    )
    await state.clear()

@dp.callback_query(F.data == "stats")
async def show_stats(call: CallbackQuery):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    users = await get_all_users()
    sponsors = await get_sponsors()
    addlists = await get_addlists()
    tgrass_enabled = await get_tgrass_enabled()
    new_today = await get_new_users_today()
    vpn_today, vpn_week, vpn_month = await get_vpn_stats()
    
    text = (
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['stats']}\">📊</tg-emoji> <b>Статистика бота</b>\n\n"
        f"👥 Пользователей: {len(users)}\n"
        f"🆕 Новых сегодня: {new_today}\n"
        f"📢 Спонсоров: {len(sponsors)}\n"
        f"📋 Addlist: {len(addlists)}\n"
        f"⚙️ TGrass: {'✅ Включен' if tgrass_enabled else '❌ Выключен'}\n\n"
        f"🔐 VPN получили сегодня: {vpn_today}\n"
        f"🔐 VPN получили за неделю: {vpn_week}\n"
        f"🔐 VPN получили за месяц: {vpn_month}\n"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="back_to_admin"
        )
    )
    
    await call.message.edit_text(text, reply_markup=builder.as_markup())
    await call.answer()

@dp.callback_query(F.data == "tgrass_settings")
async def tgrass_settings(call: CallbackQuery):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="Girdeýji Sponsorlar",
            callback_data="incoming_sponsors"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="back_to_admin"
        )
    )

    await call.message.edit_text(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['tgrassn']}\">⚙️</tg-emoji> <b>Настройки спонсорских интеграций</b>",
        reply_markup=builder.as_markup()
    )
    await call.answer()

@dp.callback_query(F.data == "incoming_sponsors")
async def incoming_sponsors_menu(call: CallbackQuery):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return

    tgrass_enabled = await get_tgrass_enabled()
    piarflow_enabled = await get_piarflow_enabled()
    subgram_enabled = await get_subgram_enabled()
    tgrass_status = "✅ Включен" if tgrass_enabled else "❌ Выключен"
    piarflow_status = "✅ Включен" if piarflow_enabled else "❌ Выключен"
    subgram_status = "✅ Включен" if subgram_enabled else "❌ Выключен"

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"TGrass: {'❌ Выключить' if tgrass_enabled else '✅ Включить'}",
            callback_data="toggle_tgrass"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"PiarFlow: {'❌ Выключить' if piarflow_enabled else '✅ Включить'}",
            callback_data="toggle_piarflow"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"Subgram: {'❌ Выключить' if subgram_enabled else '✅ Включить'}",
            callback_data="toggle_subgram"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="tgrass_settings"
        )
    )

    piarflow_key_display = f"{PIARFLOW_API_KEY[:10]}..." if PIARFLOW_API_KEY else "не задан (PIARFLOW_API_KEY)"
    subgram_key_display = f"{SUBGRAM_API_KEY[:10]}..." if SUBGRAM_API_KEY else "не задан (SUBGRAM_API_KEY)"
    await call.message.edit_text(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['tgrassn']}\">⚙️</tg-emoji> <b>Girdeýji Sponsorlar</b>\n\n"
        f"🌟 TGrass: {tgrass_status}\n"
        f"📡 PiarFlow: {piarflow_status}\n"
        f"🛰 Subgram: {subgram_status}\n\n"
        f"TGrass API Key: {TGRASS_API_KEY[:10]}...\n"
        f"PiarFlow API Key: {piarflow_key_display}\n"
        f"Subgram API Key: {subgram_key_display}",
        reply_markup=builder.as_markup()
    )
    await call.answer()

@dp.callback_query(F.data == "toggle_tgrass")
async def toggle_tgrass(call: CallbackQuery):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    current = await get_tgrass_enabled()
    await set_tgrass_enabled(not current)
    
    new_status = "✅ Включен" if not current else "❌ Выключен"
    await call.answer(f"TGrass {new_status}!", show_alert=True)
    
    await incoming_sponsors_menu(call)

@dp.callback_query(F.data == "toggle_piarflow")
async def toggle_piarflow(call: CallbackQuery):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    current = await get_piarflow_enabled()
    await set_piarflow_enabled(not current)
    
    new_status = "✅ Включен" if not current else "❌ Выключен"
    await call.answer(f"PiarFlow {new_status}!", show_alert=True)
    
    await incoming_sponsors_menu(call)

@dp.callback_query(F.data == "toggle_subgram")
async def toggle_subgram(call: CallbackQuery):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return

    current = await get_subgram_enabled()
    await set_subgram_enabled(not current)

    new_status = "✅ Включен" if not current else "❌ Выключен"
    await call.answer(f"Subgram {new_status}!", show_alert=True)

    await incoming_sponsors_menu(call)

# ================= POST KANALLAR CALLBACK HANDLERS =================

@dp.callback_query(F.data == "post_channels_menu")
async def post_channels_menu(call: CallbackQuery):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    await call.answer()
    await show_post_channels_menu(call.message.chat.id, call.message.message_id)

# ── Kanal ekle (isim bekleniyor) ──────────────────────────────────────────────
@dp.callback_query(F.data == "pch_add")
async def pch_add_start(call: CallbackQuery, state: FSMContext):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    await call.message.edit_text(
        "➕ <b>Добавить пост-канал</b>\n\n"
        "Введите в формате:\n"
        "<code>Название @username</code>\n\n"
        "Например: <code>MyChannel @mychannel</code>\n\n"
        "Отмена: /cancel"
    )
    await state.set_state(AdminStates.waiting_for_post_channel_name)
    await call.answer()

@dp.message(AdminStates.waiting_for_post_channel_name)
async def process_post_channel_name(message: Message, state: FSMContext):
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено.")
        return
    
    text = (message.text or "").strip()
    parts = text.split(maxsplit=1)
    
    if len(parts) < 2:
        await message.answer(
            "❌ Формат: <code>Название @username</code>\n\n"
            "Пример: <code>MyChannel @mychannel</code>"
        )
        return
    
    name = parts[0].strip()
    uname = parts[1].strip().lstrip("@")
    
    await add_post_channel(name, uname)
    await message.answer(
        f"✅ Канал <b>{name}</b> (@{uname}) добавлен!"
    )
    
    await state.clear()
    await show_post_channels_menu(message.chat.id, message.message_id - 1)

# ── Kanal sil ─────────────────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("pch_del_"))
async def pch_delete_channel(call: CallbackQuery):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    ch_id = call.data.replace("pch_del_", "")
    await delete_post_channel(ch_id)
    await call.answer("✅ Канал удалён!")
    await show_post_channels_menu(call.message.chat.id, call.message.message_id)

# ── Hepsine gönder ────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "pch_send_all")
async def pch_send_all(call: CallbackQuery, state: FSMContext):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    channels = await get_post_channels()
    if not channels:
        await call.answer("Список пуст! Сначала добавьте каналы.", show_alert=True)
        return
    
    names = ", ".join(f"@{c['username']}" for c in channels)
    await call.message.edit_text(
        f"🚀 <b>Отправить во все каналы</b>\n\n"
        f"Каналов: <b>{len(channels)}</b>\n"
        f"{names}\n\n"
        f"Отправьте рекламный пост (текст, фото, видео — любой тип)\n\n"
        f"Отмена: /cancel"
    )
    await state.update_data(post_target="all")
    await state.set_state(AdminStates.waiting_for_post_content)
    await call.answer()

# ── Tek kanala gönder ─────────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("pch_send_"))
async def pch_send_one(call: CallbackQuery, state: FSMContext):
    if call.data == "pch_send_all":
        return
    
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    ch_id = call.data.replace("pch_send_", "")
    
    channels = await get_post_channels()
    ch = next((c for c in channels if str(c["_id"]) == ch_id), None)
    
    if not ch:
        await call.answer("Канал не найден!", show_alert=True)
        return
    
    await call.message.edit_text(
        f"📺 <b>@{ch['username']}</b> каналына пост отправьте:\n\n"
        f"(Текст, фото, видео — любой тип)\n\n"
        f"Отмена: /cancel"
    )
    await state.update_data(post_target=str(ch_id))
    await state.set_state(AdminStates.waiting_for_post_content)
    await call.answer()

# ── Post içeriği geldikten sonra gönder ───────────────────────────────────────
@dp.message(AdminStates.waiting_for_post_content)
async def process_post_content(message: Message, state: FSMContext):
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено.")
        return
    
    data = await state.get_data()
    target = data.get("post_target", "all")
    
    if target == "all":
        channels = await get_post_channels()
    else:
        channels = await get_post_channels()
        ch = next((c for c in channels if str(c["_id"]) == target), None)
        channels = [ch] if ch else []
    
    if not channels:
        await state.clear()
        await message.answer("❌ Каналов нет.")
        return
    
    ok = 0
    fail = 0
    fail_list = []
    
    prog = await message.answer(f"📡 Отправка...\n0 / {len(channels)}")
    
    for i, ch in enumerate(channels, 1):
        tgt = "@" + ch.get("username", "").lstrip("@")
        try:
            sent = await bot.copy_message(
                chat_id=tgt,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=message.reply_markup
            )
            await save_sent_ad(tgt, sent.message_id)
            ok += 1
        except Exception as e:
            fail += 1
            error_msg = str(e).replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
            fail_list.append(f"{ch.get('name', '?')} ({tgt}): {error_msg[:60]}")
        
        try:
            await bot.edit_message_text(
                f"📡 Отправка...\n{i} / {len(channels)}",
                message.chat.id, prog.message_id
            )
        except Exception:
            pass
        
        await asyncio.sleep(0.3)
    
    if fail_list:
        fail_texts = []
        for f in fail_list:
            clean_f = f.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
            fail_texts.append(f"• {clean_f}")
        fail_txt = "\n\n❌ Ошибки:\n" + "\n".join(fail_texts)
    else:
        fail_txt = ""
    
    await state.clear()
    
    try:
        await bot.edit_message_text(
            f"✅ <b>Отправка завершена!</b>\n\n"
            f"📡 Каналов: <b>{len(channels)}</b>\n"
            f"✔️ Успешно: <b>{ok}</b>\n"
            f"❌ Ошибок: <b>{fail}</b>{fail_txt}",
            message.chat.id, prog.message_id,
            parse_mode=ParseMode.HTML
        )
    except Exception:
        await message.answer(
            f"✅ <b>Отправка завершена!</b>\n\n"
            f"📡 Каналов: <b>{len(channels)}</b>\n"
            f"✔️ Успешно: <b>{ok}</b>\n"
            f"❌ Ошибок: <b>{fail}</b>",
            parse_mode=ParseMode.HTML
        )

# ── Gönderilen postları sil ───────────────────────────────────────────────────
@dp.callback_query(F.data == "delete_posts")
async def delete_posts(call: CallbackQuery):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    ads = await get_sent_ads()
    if not ads:
        await call.answer("Нет сохранённых постов!", show_alert=True)
        return
    
    ok = 0
    fail = 0
    for chat_id, msg_id in ads:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
            ok += 1
        except Exception:
            fail += 1
    
    await clear_sent_ads()
    
    await call.message.edit_text(
        f"🗑 <b>Посты удалены!</b>\n\n"
        f"✔️ Удалено: <b>{ok}</b>\n"
        f"❌ Не найдено: <b>{fail}</b>"
    )
    await call.answer()

# ── Geri (back_to_admin) ──────────────────────────────────────────────────────
@dp.callback_query(F.data == "back_to_admin")
async def back_to_admin(call: CallbackQuery):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return

    markup = await build_admin_panel_keyboard(call.from_user.id)
    await call.message.edit_text(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['admin']}\">👑</tg-emoji> <b>Админ панель</b>",
        reply_markup=markup
    )
    await call.answer()

# ================= /bonus KOMUTY =================

async def claim_bonus(user_id: int):
    """Gaýtarýar (success: bool, text: str)"""
    last = await get_last_bonus(user_id)
    now = datetime.datetime.utcnow()
    if last:
        try:
            last_dt = datetime.datetime.fromisoformat(last)
        except Exception:
            last_dt = None
        if last_dt:
            diff = now - last_dt
            cooldown = datetime.timedelta(hours=BONUS_COOLDOWN_HOURS)
            if diff < cooldown:
                remaining = cooldown - diff
                hours = remaining.seconds // 3600
                minutes = (remaining.seconds % 3600) // 60
                return False, f"⏳ Бонус уже получен. Следующий бонус через {hours} ч. {minutes} мин."

    await add_balance(user_id, BONUS_AMOUNT)
    await set_last_bonus(user_id)
    return True, f"🎁 Вам начислено <b>{BONUS_AMOUNT}</b> Vgram! Следующий бонус через {BONUS_COOLDOWN_HOURS} часа."

@dp.message(Command("bonus"))
async def cmd_bonus(message: Message):
    if await is_banned(message.from_user.id):
        await message.answer("🚫 Вы заблокированы и не можете пользоваться ботом.")
        return
    await add_user(message.from_user.id, message.from_user.username or message.from_user.first_name)
    ok, text = await claim_bonus(message.from_user.id)
    await message.answer(text)

@dp.callback_query(F.data == "bonus_claim")
async def bonus_claim_callback(call: CallbackQuery):
    if await is_banned(call.from_user.id):
        await call.answer("🚫 Вы заблокированы!", show_alert=True)
        return
    ok, text = await claim_bonus(call.from_user.id)
    plain = re.sub(r"<[^>]+>", "", text)
    await call.answer(plain, show_alert=True)

# ================= /profil KOMUTY =================

@dp.message(Command("profil"))
async def cmd_profil(message: Message):
    user_id = message.from_user.id
    if await is_banned(user_id):
        await message.answer("🚫 Вы заблокированы и не можете пользоваться ботом.")
        return

    await add_user(user_id, message.from_user.username or message.from_user.first_name)
    balance_vgram = await get_balance(user_id)
    balance_tmt = await get_balance_tmt(user_id)
    full_name = message.from_user.full_name or message.from_user.first_name or "—"

    text = (
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['info']}\">ℹ️</tg-emoji> <b>Ваш профиль</b>\n\n"
        f"👤 Имя: <b>{full_name}</b>\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"💰 Баланс Vgram: <b>{balance_vgram}</b>\n"
        f"💵 Баланс TMT: <b>{balance_tmt}</b>"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎁 Бонус", callback_data="bonus_claim"),
        InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="user_topup_request")
    )
    await message.answer(text, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "user_topup_request")
async def user_topup_request(call: CallbackQuery):
    await call.answer(
        f"Свяжитесь с администратором @{SUPER_ADMIN_USERNAME} для пополнения баланса.",
        show_alert=True
    )

# ── Balans doldurmak (diňe Super Admin) ────────────────────────────────────────
@dp.callback_query(F.data == "topup_start")
async def topup_start(call: CallbackQuery, state: FSMContext):
    if not await can_send_balance(call.from_user.id):
        await call.answer("❌ Доступ запрещен! Только Super Admin.", show_alert=True)
        return

    await call.message.edit_text(
        "💳 <b>Пополнение баланса</b>\n\n"
        "Отправьте ID пользователя, которому нужно пополнить баланс.\n"
        "Отмена: /cancel"
    )
    await state.set_state(AdminStates.waiting_for_topup_user_id)
    await call.answer()

@dp.message(AdminStates.waiting_for_topup_user_id)
async def process_topup_user_id(message: Message, state: FSMContext):
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено.")
        return

    try:
        target_id = int(message.text.strip())
    except (ValueError, TypeError):
        await message.answer("❌ Неверный ID! Отправьте числовой ID пользователя.")
        return

    await state.update_data(target_id=target_id)

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💰 Vgram", callback_data="topup_cur_vgram"),
        InlineKeyboardButton(text="💵 TMT", callback_data="topup_cur_tmt")
    )
    await message.answer(
        f"Пользователь: <code>{target_id}</code>\n\nВыберите валюту для пополнения:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data.in_(["topup_cur_vgram", "topup_cur_tmt"]))
async def topup_choose_currency(call: CallbackQuery, state: FSMContext):
    if not await can_send_balance(call.from_user.id):
        await call.answer("❌ Доступ запрещен! Только Super Admin.", show_alert=True)
        return

    data = await state.get_data()
    target_id = data.get("target_id")
    if not target_id:
        await call.answer("❌ Сначала отправьте ID пользователя (/admin → Пополнить баланс).", show_alert=True)
        return

    currency = "vgram" if call.data == "topup_cur_vgram" else "tmt"
    await state.update_data(currency=currency)
    await state.set_state(AdminStates.waiting_for_topup_amount)

    label = "Vgram" if currency == "vgram" else "TMT"
    await call.message.edit_text(
        f"Пользователь: <code>{target_id}</code>\nВалюта: <b>{label}</b>\n\n"
        f"Отправьте сумму для пополнения (число). Отмена: /cancel"
    )
    await call.answer()

@dp.message(AdminStates.waiting_for_topup_amount)
async def process_topup_amount(message: Message, state: FSMContext):
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено.")
        return

    try:
        amount = float(message.text.strip().replace(",", "."))
    except (ValueError, TypeError):
        await message.answer("❌ Неверная сумма! Отправьте число.")
        return

    data = await state.get_data()
    target_id = data.get("target_id")
    currency = data.get("currency")

    if not target_id or not currency:
        await state.clear()
        await message.answer("❌ Ошибка. Начните заново через /admin → Пополнить баланс.")
        return

    if currency == "vgram":
        await add_balance(target_id, amount)
        label = "Vgram"
    else:
        await add_balance_tmt(target_id, amount)
        label = "TMT"

    await message.answer(
        f"✅ Баланс пользователя <code>{target_id}</code> пополнен на <b>{amount} {label}</b>!"
    )

    try:
        await bot.send_message(
            target_id,
            f"💳 Ваш баланс пополнен администратором на <b>{amount} {label}</b>!"
        )
    except Exception:
        pass

    await state.clear()

# ================= /buy KOMUTY (VPN SATYN ALMAK) =================

def build_buy_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🛒 Купить VPN", callback_data="buy_tariffs")
    )
    builder.row(
        InlineKeyboardButton(text="📦 Мои VPN пакеты", callback_data="my_vpn_packages")
    )
    return builder.as_markup()

@dp.message(Command("buy"))
async def cmd_buy(message: Message):
    if await is_banned(message.from_user.id):
        await message.answer("🚫 Вы заблокированы и не можете пользоваться ботом.")
        return
    await add_user(message.from_user.id, message.from_user.username or message.from_user.first_name)
    await message.answer(
        "🛍 <b>VPN магазин</b>\n\nВыберите действие:",
        reply_markup=build_buy_menu_keyboard()
    )

@dp.callback_query(F.data == "buy_menu")
async def buy_menu_callback(call: CallbackQuery):
    await call.message.edit_text(
        "🛍 <b>VPN магазин</b>\n\nВыберите действие:",
        reply_markup=build_buy_menu_keyboard()
    )
    await call.answer()

@dp.callback_query(F.data == "buy_tariffs")
async def buy_tariffs(call: CallbackQuery):
    if await is_banned(call.from_user.id):
        await call.answer("🚫 Вы заблокированы!", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for pkg in VPN_PACKAGES:
        if pkg["currency"] == "both":
            price_text = f"{pkg['price_vgram']} Vgram / {pkg['price_tmt']} TMT"
        else:
            price_text = f"{pkg['price_tmt']} TMT"
        builder.row(
            InlineKeyboardButton(
                text=f"{pkg['title']} — {price_text}",
                callback_data=f"buy_pkg_{pkg['key']}"
            )
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="buy_menu"))

    await call.message.edit_text(
        "🛒 <b>Выберите тариф VPN:</b>",
        reply_markup=builder.as_markup()
    )
    await call.answer()

@dp.callback_query(F.data.startswith("buy_pkg_"))
async def buy_pkg_selected(call: CallbackQuery):
    if await is_banned(call.from_user.id):
        await call.answer("🚫 Вы заблокированы!", show_alert=True)
        return

    key = call.data.replace("buy_pkg_", "")
    pkg = get_vpn_package(key)
    if not pkg:
        await call.answer("❌ Тариф не найден!", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    if pkg["currency"] == "both":
        builder.row(
            InlineKeyboardButton(text=f"💰 {pkg['price_vgram']} Vgram", callback_data=f"buy_final_{key}_vgram"),
            InlineKeyboardButton(text=f"💵 {pkg['price_tmt']} TMT", callback_data=f"buy_final_{key}_tmt")
        )
    else:
        builder.row(
            InlineKeyboardButton(text=f"✅ Купить за {pkg['price_tmt']} TMT", callback_data=f"buy_final_{key}_tmt")
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="buy_tariffs"))

    await call.message.edit_text(
        f"📦 <b>{pkg['title']}</b>\n\nВыберите способ оплаты:",
        reply_markup=builder.as_markup()
    )
    await call.answer()

@dp.callback_query(F.data.startswith("buy_final_"))
async def buy_final(call: CallbackQuery):
    if await is_banned(call.from_user.id):
        await call.answer("🚫 Вы заблокированы!", show_alert=True)
        return

    parts = call.data.replace("buy_final_", "").rsplit("_", 1)
    if len(parts) != 2:
        await call.answer("❌ Ошибка!", show_alert=True)
        return
    key, currency = parts
    pkg = get_vpn_package(key)
    if not pkg:
        await call.answer("❌ Тариф не найден!", show_alert=True)
        return

    user_id = call.from_user.id

    if currency == "vgram":
        if pkg.get("price_vgram") is None:
            await call.answer("❌ Этот тариф нельзя купить за Vgram!", show_alert=True)
            return
        price = pkg["price_vgram"]
        balance = await get_balance(user_id)
        if balance < price:
            await call.answer(f"❌ Недостаточно Vgram! Ваш баланс: {balance}", show_alert=True)
            return
        await add_balance(user_id, -price)
    else:
        price = pkg["price_tmt"]
        balance = await get_balance_tmt(user_id)
        if balance < price:
            await call.answer(f"❌ Недостаточно TMT! Ваш баланс: {balance}", show_alert=True)
            return
        await add_balance_tmt(user_id, -price)

    purchase = await create_purchase(user_id, key, currency, price)

    await call.message.edit_text(
        f"✅ <b>Покупка оформлена!</b>\n\n"
        f"📦 Тариф: <b>{pkg['title']}</b>\n"
        f"🧾 Чек: <code>{purchase['check_number']}</code>\n\n"
        f"⏳ Ожидайте, администратор отправит вам VPN ссылку в ближайшее время."
    )
    await call.answer()

    currency_label = "Vgram" if currency == "vgram" else "TMT"
    uname = f"@{call.from_user.username}" if call.from_user.username else call.from_user.full_name
    notify_text = (
        f"🛒 <b>Новая покупка VPN!</b>\n\n"
        f"👤 Пользователь: {uname}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"📦 Пакет: <b>{pkg['title']}</b>\n"
        f"💳 Оплачено: <b>{price} {currency_label}</b>\n"
        f"🧾 Чек: <code>{purchase['check_number']}</code>\n\n"
        f"Чтобы отправить VPN ссылку, нажмите кнопку ниже и отправьте ссылку,\n"
        f"или напишите в формате: <code>{user_id} | ссылка</code>"
    )
    notify_builder = InlineKeyboardBuilder()
    notify_builder.row(
        InlineKeyboardButton(text="📨 Отправить ссылку", callback_data=f"send_vpnlink_{purchase['_id']}")
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, notify_text, reply_markup=notify_builder.as_markup())
        except Exception as e:
            logging.error(f"VPN satyn alma habary iberilmedi ({admin_id}): {e}")

@dp.callback_query(F.data.startswith("send_vpnlink_"))
async def send_vpnlink_start(call: CallbackQuery, state: FSMContext):
    if not await can_send_vpn_link(call.from_user.id):
        await call.answer("❌ Доступ запрещен! Только Super Admin.", show_alert=True)
        return

    purchase_id_str = call.data.replace("send_vpnlink_", "")
    try:
        purchase_id = ObjectId(purchase_id_str)
    except Exception:
        await call.answer("❌ Ошибка ID покупки!", show_alert=True)
        return

    purchase = await col_purchases.find_one({"_id": purchase_id})
    if not purchase:
        await call.answer("❌ Покупка не найдена!", show_alert=True)
        return

    await state.update_data(purchase_id=purchase_id, target_user_id=purchase["user_id"])
    await state.set_state(AdminStates.waiting_for_vpn_link_send)
    await call.message.answer(
        f"📨 Отправьте VPN ссылку для пользователя <code>{purchase['user_id']}</code>.\n"
        f"Отмена: /cancel"
    )
    await call.answer()

@dp.message(AdminStates.waiting_for_vpn_link_send)
async def process_send_vpnlink(message: Message, state: FSMContext):
    if not await can_send_vpn_link(message.from_user.id):
        await state.clear()
        return

    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено.")
        return

    text = (message.text or "").strip()
    data = await state.get_data()
    purchase_id = data.get("purchase_id")

    target_id = None
    link = text
    if "|" in text:
        left, right = text.split("|", 1)
        left = left.strip()
        if left.isdigit():
            target_id = int(left)
            link = right.strip()

    purchase = None
    if purchase_id:
        purchase = await col_purchases.find_one({"_id": purchase_id, "status": "pending"})
    if not purchase and target_id:
        purchase = await get_pending_purchase_for_user(target_id)

    if not purchase:
        await message.answer("❌ Ожидающая покупка не найдена. Проверьте ID и попробуйте снова, или /cancel.")
        return

    fulfilled = await fulfill_purchase(purchase["_id"], link)
    pkg = get_vpn_package(fulfilled["package_key"])
    pkg_title = pkg["title"] if pkg else fulfilled["package_key"]

    try:
        await bot.send_message(
            fulfilled["user_id"],
            f"✅ <b>Ваша VPN ссылка готова!</b>\n\n"
            f"📦 Пакет: <b>{pkg_title}</b>\n"
            f"🔗 Ссылка: <code>{link}</code>\n\n"
            f"Посмотреть свои пакеты можно в разделе «📦 Мои VPN пакеты»."
        )
    except Exception as e:
        logging.error(f"VPN linki ulanyja iberilmedi: {e}")

    await message.answer(f"✅ Ссылка отправлена пользователю <code>{fulfilled['user_id']}</code>!")
    await state.clear()

@dp.callback_query(F.data == "my_vpn_packages")
async def my_vpn_packages(call: CallbackQuery):
    packages = await get_user_vpn_packages(call.from_user.id)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="buy_menu"))

    if not packages:
        await call.message.edit_text(
            "📦 <b>Мои VPN пакеты</b>\n\nУ вас пока нет купленных пакетов.",
            reply_markup=builder.as_markup()
        )
        await call.answer()
        return

    text = "📦 <b>Мои VPN пакеты</b>\n\n"
    for p in packages:
        pkg = get_vpn_package(p["package_key"])
        title = pkg["title"] if pkg else p["package_key"]
        remaining = format_remaining_time(p.get("expires_at"))
        text += (
            f"• <b>{title}</b>\n"
            f"  🔗 <code>{p.get('vpn_link', '—')}</code>\n"
            f"  ⏳ Осталось: <b>{remaining}</b>\n\n"
        )

    await call.message.edit_text(text, reply_markup=builder.as_markup())
    await call.answer()

# ================= ÇAT SPONSOR GOŞMAK =================

def _parse_chat_ref(text: str):
    text = text.strip()
    stripped = text.lstrip("-")
    if stripped.isdigit():
        return int(text)
    return text if text.startswith("@") else "@" + text

@dp.callback_query(F.data == "add_chat_sponsor")
async def add_chat_sponsor_start(call: CallbackQuery, state: FSMContext):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return

    await call.message.edit_text(
        "➕ <b>Добавление чат-спонсора</b>\n\n"
        "Отправьте ID чата (например: -1001234567890) или @username чата.\n"
        "Бот должен быть администратором в этом чате!\n\n"
        "Отмена: /cancel"
    )
    await state.set_state(AdminStates.waiting_for_chat_sponsor_id)
    await call.answer()

@dp.message(AdminStates.waiting_for_chat_sponsor_id)
async def process_chat_sponsor_id(message: Message, state: FSMContext):
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено.")
        return

    chat_ref = _parse_chat_ref(message.text or "")

    try:
        chat = await bot.get_chat(chat_ref)
    except Exception as e:
        await message.answer(f"❌ Чат не найден: {e}")
        return

    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(chat.id, me.id)
    except Exception as e:
        await message.answer(f"❌ Не удалось проверить права бота: {e}")
        return

    if member.status not in ("administrator", "creator"):
        await message.answer("❌ Бот не администратор в этом чате! Сделайте бота админом и попробуйте снова.")
        return

    await state.update_data(chat_id=chat.id, chat_title=chat.title or str(chat.id))
    await message.answer(
        f"✅ Бот является администратором чата <b>{chat.title}</b>.\n\n"
        f"Теперь отправьте ссылку на чат (например: https://t.me/chatusername)"
    )
    await state.set_state(AdminStates.waiting_for_chat_sponsor_link)

@dp.message(AdminStates.waiting_for_chat_sponsor_link)
async def process_chat_sponsor_link(message: Message, state: FSMContext):
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено.")
        return

    link = message.text.strip()
    data = await state.get_data()
    chat_id = data.get("chat_id")
    chat_title = data.get("chat_title", "")

    sponsors = await get_sponsors()
    max_pos = max([s.get("position", 0) for s in sponsors]) if sponsors else 0
    new_position = max_pos + 1

    await add_sponsor(chat_id, link, new_position)

    await message.answer(
        f"✅ Чат-спонсор <b>{chat_title}</b> успешно добавлен!\n"
        f"ID: {chat_id}\nСсылка: {link}"
    )
    await state.clear()

# ================= SPONSORLARYŇ TERTIBINI ÜÝTGETMEK (Yukarı/Aşağı) =================

async def move_sponsor(doc_id: str, direction: str) -> bool:
    sponsors = await get_sponsors()
    idx = next((i for i, s in enumerate(sponsors) if str(s["_id"]) == doc_id), None)
    if idx is None:
        return False

    if direction == "up" and idx > 0:
        other = sponsors[idx - 1]
    elif direction == "down" and idx < len(sponsors) - 1:
        other = sponsors[idx + 1]
    else:
        return False

    cur = sponsors[idx]
    pos_cur = cur.get("position", 0)
    pos_other = other.get("position", 0)
    await col_sponsors.update_one({"_id": cur["_id"]}, {"$set": {"position": pos_other}})
    await col_sponsors.update_one({"_id": other["_id"]}, {"$set": {"position": pos_cur}})
    return True

async def show_sponsor_order_menu(chat_id: int, message_id: int):
    sponsors = await get_sponsors()
    builder = InlineKeyboardBuilder()

    if not sponsors:
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_admin"))
        await bot.edit_message_text(
            "🔀 <b>Порядок спонсоров</b>\n\nСписок спонсоров пуст.",
            chat_id=chat_id, message_id=message_id, reply_markup=builder.as_markup()
        )
        return

    for s in sponsors:
        sid = str(s["_id"])
        name = await get_channel_name(channel_id=s.get("channel_id"))
        builder.row(
            InlineKeyboardButton(text=f"{name}", callback_data="noop"),
            InlineKeyboardButton(text="⬆️", callback_data=f"sp_up_{sid}"),
            InlineKeyboardButton(text="⬇️", callback_data=f"sp_down_{sid}")
        )

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_admin"))

    await bot.edit_message_text(
        "🔀 <b>Порядок спонсоров</b>\n\nИспользуйте ⬆️/⬇️ чтобы изменить порядок показа.",
        chat_id=chat_id, message_id=message_id, reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "sponsor_order")
async def sponsor_order_callback(call: CallbackQuery):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    await call.answer()
    await show_sponsor_order_menu(call.message.chat.id, call.message.message_id)

@dp.callback_query(F.data == "noop")
async def noop_callback(call: CallbackQuery):
    await call.answer()

@dp.callback_query(F.data.startswith("sp_up_") | F.data.startswith("sp_down_"))
async def sponsor_move_callback(call: CallbackQuery):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return

    if call.data.startswith("sp_up_"):
        doc_id = call.data.replace("sp_up_", "")
        direction = "up"
    else:
        doc_id = call.data.replace("sp_down_", "")
        direction = "down"

    await move_sponsor(doc_id, direction)
    await call.answer()
    await show_sponsor_order_menu(call.message.chat.id, call.message.message_id)

# ================= BAN / UNBAN ULGAMY =================

@dp.callback_query(F.data == "ban_user_start")
async def ban_user_start(call: CallbackQuery, state: FSMContext):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return

    await call.message.edit_text(
        "🚫 <b>Бан пользователя</b>\n\nОтправьте ID пользователя для блокировки.\nОтмена: /cancel"
    )
    await state.set_state(AdminStates.waiting_for_ban_id)
    await call.answer()

@dp.message(AdminStates.waiting_for_ban_id)
async def process_ban_id(message: Message, state: FSMContext):
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено.")
        return

    try:
        target_id = int(message.text.strip())
    except (ValueError, TypeError):
        await message.answer("❌ Неверный ID! Отправьте числовой ID пользователя.")
        return

    await ban_user(target_id)
    await message.answer(f"✅ Пользователь <code>{target_id}</code> заблокирован!")
    await state.clear()

async def show_unban_list(chat_id: int, message_id: int):
    banned = await get_banned_users()
    builder = InlineKeyboardBuilder()

    if not banned:
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_admin"))
        await bot.edit_message_text(
            "✅ <b>Заблокированные пользователи</b>\n\nСписок пуст.",
            chat_id=chat_id, message_id=message_id, reply_markup=builder.as_markup()
        )
        return

    for b in banned:
        uid = b["user_id"]
        builder.row(
            InlineKeyboardButton(text=f"🔓 Разблокировать {uid}", callback_data=f"unban_{uid}")
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_admin"))

    await bot.edit_message_text(
        "✅ <b>Заблокированные пользователи</b>\n\nНажмите, чтобы снять бан:",
        chat_id=chat_id, message_id=message_id, reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "unban_list")
async def unban_list_callback(call: CallbackQuery):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    await call.answer()
    await show_unban_list(call.message.chat.id, call.message.message_id)

@dp.callback_query(F.data.startswith("unban_"))
async def unban_callback(call: CallbackQuery):
    if not await is_staff(call.from_user.id):
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return

    uid = int(call.data.replace("unban_", ""))
    await unban_user(uid)
    await call.answer(f"✅ Пользователь {uid} разблокирован!", show_alert=True)
    await show_unban_list(call.message.chat.id, call.message.message_id)

# ================= ADMIN / ADMINLO DOLANDYRMAK (diňe Super Admin) =================

@dp.callback_query(F.data == "add_admin_start")
async def add_admin_start(call: CallbackQuery, state: FSMContext):
    if not await can_manage_admins(call.from_user.id):
        await call.answer("❌ Доступ запрещен! Только Super Admin.", show_alert=True)
        return

    await call.message.edit_text(
        "➕ <b>Добавить админа</b>\n\nОтправьте ID пользователя.\nОтмена: /cancel"
    )
    await state.set_state(AdminStates.waiting_for_new_admin_id)
    await call.answer()

@dp.message(AdminStates.waiting_for_new_admin_id)
async def process_new_admin_id(message: Message, state: FSMContext):
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено.")
        return

    try:
        target_id = int(message.text.strip())
    except (ValueError, TypeError):
        await message.answer("❌ Неверный ID! Отправьте числовой ID пользователя.")
        return

    await add_admin_role(target_id, "admin")
    await message.answer(f"✅ Пользователь <code>{target_id}</code> назначен админом!")
    await state.clear()

@dp.callback_query(F.data == "add_adminlo_start")
async def add_adminlo_start(call: CallbackQuery, state: FSMContext):
    if not await can_manage_admins(call.from_user.id):
        await call.answer("❌ Доступ запрещен! Только Super Admin.", show_alert=True)
        return

    await call.message.edit_text(
        "➕ <b>Добавить AdminLo</b>\n\nОтправьте ID пользователя.\nОтмена: /cancel"
    )
    await state.set_state(AdminStates.waiting_for_new_adminlo_id)
    await call.answer()

@dp.message(AdminStates.waiting_for_new_adminlo_id)
async def process_new_adminlo_id(message: Message, state: FSMContext):
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено.")
        return

    try:
        target_id = int(message.text.strip())
    except (ValueError, TypeError):
        await message.answer("❌ Неверный ID! Отправьте числовой ID пользователя.")
        return

    await add_admin_role(target_id, "adminlo")
    await message.answer(f"✅ Пользователь <code>{target_id}</code> назначен AdminLo!")
    await state.clear()

async def show_remove_admin_list(chat_id: int, message_id: int, role: str):
    admins = await get_admins_by_role(role)
    label = "админов" if role == "admin" else "AdminLo"
    builder = InlineKeyboardBuilder()

    if not admins:
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_admin"))
        await bot.edit_message_text(
            f"➖ <b>Удаление {label}</b>\n\nСписок пуст.",
            chat_id=chat_id, message_id=message_id, reply_markup=builder.as_markup()
        )
        return

    prefix = "rm_admin_" if role == "admin" else "rm_adminlo_"
    for a in admins:
        uid = a["user_id"]
        builder.row(InlineKeyboardButton(text=f"🗑 {uid}", callback_data=f"{prefix}{uid}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_admin"))

    await bot.edit_message_text(
        f"➖ <b>Удаление {label}</b>\n\nВыберите, кого удалить:",
        chat_id=chat_id, message_id=message_id, reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "remove_admin_list")
async def remove_admin_list_callback(call: CallbackQuery):
    if not await can_manage_admins(call.from_user.id):
        await call.answer("❌ Доступ запрещен! Только Super Admin.", show_alert=True)
        return
    await call.answer()
    await show_remove_admin_list(call.message.chat.id, call.message.message_id, "admin")

@dp.callback_query(F.data == "remove_adminlo_list")
async def remove_adminlo_list_callback(call: CallbackQuery):
    if not await can_manage_admins(call.from_user.id):
        await call.answer("❌ Доступ запрещен! Только Super Admin.", show_alert=True)
        return
    await call.answer()
    await show_remove_admin_list(call.message.chat.id, call.message.message_id, "adminlo")

@dp.callback_query(F.data.startswith("rm_admin_"))
async def rm_admin_callback(call: CallbackQuery):
    if not await can_manage_admins(call.from_user.id):
        await call.answer("❌ Доступ запрещен! Только Super Admin.", show_alert=True)
        return
    uid = int(call.data.replace("rm_admin_", ""))
    await remove_admin_role(uid)
    await call.answer(f"✅ {uid} удалён из админов!", show_alert=True)
    await show_remove_admin_list(call.message.chat.id, call.message.message_id, "admin")

@dp.callback_query(F.data.startswith("rm_adminlo_"))
async def rm_adminlo_callback(call: CallbackQuery):
    if not await can_manage_admins(call.from_user.id):
        await call.answer("❌ Доступ запрещен! Только Super Admin.", show_alert=True)
        return
    uid = int(call.data.replace("rm_adminlo_", ""))
    await remove_admin_role(uid)
    await call.answer(f"✅ {uid} удалён из AdminLo!", show_alert=True)
    await show_remove_admin_list(call.message.chat.id, call.message.message_id, "adminlo")

# ================= FLASK WEB SUNUCUSU (RENDER İÇİN) =================

from flask import Flask

flask_app = Flask(__name__)

# Kendi Render URL'inizi buraya yazın (self-ping için)
RENDER_URL = "https://zonex-j85z.onrender.com"

@flask_app.route("/")
def home():
    return "Bot is Alive!", 200

@flask_app.route("/health")
def health():
    return "OK", 200

def self_ping():
    while True:
        try:
            requests.get(RENDER_URL, timeout=10)
        except Exception:
            pass
        time.sleep(300)  # 5 dakika

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT, use_reloader=False)

# ================= ANA FONKSİYON =================

async def main():
    await init_db()
    logging.info("Bot started")
    print("🤖 Бот работает...")
    print(f"👑 Admin ID: {ADMIN_IDS[0]}")
    print("🌟 TGrass integration active")
    print(f"🌐 Render Health Check: http://0.0.0.0:{PORT}")

    try:
        # Fonksiyon async olduğu için başına 'await' eklendi:
        test_offers = await check_tgrass_subscriptions(123456789, "test_user", False)
        print(f"📡 TGrass API test: {len(test_offers)} channel(s) received")
    except Exception as e:
        print(f"❌ TGrass API test failed: {e}")

    if PIARFLOW_API_KEY:
        try:
            test_offers = await check_piarflow_subscriptions(123456789, "test_user", False)
            print(f"📡 PiarFlow API test: {len(test_offers)} channel(s) received")
        except Exception as e:
            print(f"❌ PiarFlow API test failed: {e}")
    else:
        print("⚠️ PIARFLOW_API_KEY tanımlı değil, PiarFlow testi atlandı.")

    # Bot polling (Flask ayrı thread'lerde çalışıyor)
    await dp.start_polling(bot)

if __name__ == "__main__":
    # Flask ve self-ping ayrı thread'lerde başlatılıyor
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=self_ping, daemon=True).start()

    # Bot asyncio ile ana thread'de çalışıyor
    asyncio.run(main())
