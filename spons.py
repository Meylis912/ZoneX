import asyncio
import sqlite3
import logging
import requests
import json
import re
from contextlib import closing
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

import time
import threading
import os
from flask import Flask
from pymongo import MongoClient


# ╔══════════════════════════════════════════════════════════╗
#                   MONGODB & FLASK RENDER
# ╚══════════════════════════════════════════════════════════╝
# MongoDB Connection
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb+srv://mergenowlyagulyyew41_db_user:ZvZhOKOAF6ZMRbHX@cluster1.l8z8gll.mongodb.net/?appName=Cluster1")
try:
    mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    mongo_client.admin.command("ping")
    mongo_db = mongo_client["relaxpremlisponsor_db"]
    mongo_logs = mongo_db["logs"]
    logging.info("✅ MongoDB connected")
except Exception as e:
    logging.warning(f"⚠️ MongoDB error: {e}")
    mongo_db = None

# Flask Keep-Alive for Render
app = Flask(__name__)
RENDER_URL = os.getenv("RENDER_URL", "https://relaxpremlisponsor.onrender.com")

@app.route("/")
def home():
    return "✅ Bot is running!", 200

@app.route("/health")
def health():
    return {"status": "healthy"}, 200

def keep_alive_ping():
    while True:
        try:
            requests.get(RENDER_URL, timeout=10)
            logging.debug("✅ Keep-Alive ping sent")
        except Exception as e:
            logging.debug(f"⚠️ Ping error: {e}")
        time.sleep(300)

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, use_reloader=False, debug=False)

# Botuň sazlamalary
BOT_TOKEN = '8404357846:AAGdfqP-ilKe0tkoVa15kDyH9ZkK_5YFwRI'
ADMIN_IDS = [7523674506]

# TGRASS
TGRASS_API_KEY = "e4fd3c4932ca4f75859dde74af2ca25f"
TGRASS_API_URL = "https://tgrass.space/offers"

# bot
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

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
    "settings": "6030657343744644592",     # ⚙️
    "chanel": "5260268501515377807",         # 📣
    "chik": "5427009714745517609",              # ✅
    "del": "5841541824803509441",                # 🗑️
    "tekst": "5879841310902324730",            # ✏️
    "tgrassn": "6032742198179532882",         # ⚙️
}

# Loglamagy sazlamak
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='bot.log'
)

logging.info(f"Admin ID: {ADMIN_IDS[0]}")

# ================= TGRASS FUNKSIÝALARY =================
def get_user_language(user_id):
    with closing(sqlite3.connect('Fearsponsorbot.db')) as conn:
        try:
            cur = conn.execute("SELECT value FROM settings WHERE key = ?", (f"lang_{user_id}",))
            res = cur.fetchone()
            return res[0] if res else 'ru'
        except:
            return 'ru'

def check_tgrass_subscriptions(user_id, username=None, is_premium=False):
    try:
        url = TGRASS_API_URL
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "Auth": TGRASS_API_KEY,
        }
        
        lang = get_user_language(user_id)
        
        payload = {
            "tg_user_id": int(user_id),
            "tg_login": username or "",
            "lang": lang,
            "is_premium": is_premium,
        }
        
        logging.info(f"TGrass API istek: {payload}")
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
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

def get_tgrass_enabled():
    with closing(sqlite3.connect('Fearsponsorbot.db')) as conn:
        try:
            cur = conn.execute("SELECT value FROM settings WHERE key = ?", ("tgrass_enabled",))
            res = cur.fetchone()
            return res[0] == '1' if res else True
        except:
            return True

def set_tgrass_enabled(enabled):
    with closing(sqlite3.connect('Fearsponsorbot.db')) as conn:
        try:
            with conn:
                conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", 
                            ("tgrass_enabled", "1" if enabled else "0"))
            return True
        except Exception as e:
            logging.error(f"TGrass error: {str(e)}")
            return False

def parse_premium_emoji(text):
    pattern = r'<tg-emoji emoji-id="([^"]+)">([^<]+)</tg-emoji>'
    
    def replace_emoji(match):
        emoji_id = match.group(1)
        emoji_char = match.group(2)
        return f'<tg-emoji emoji-id="{emoji_id}">{emoji_char}</tg-emoji>'
    
    return re.sub(pattern, replace_emoji, text)

def init_db():
    with closing(sqlite3.connect('Fearsponsorbot.db')) as conn:
        with conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS users (
                                user_id INTEGER PRIMARY KEY
                            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS sponsors (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                channel_id TEXT,
                                link TEXT,
                                position INTEGER
                            )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS settings (
                                key TEXT PRIMARY KEY,
                                value TEXT
                            )''')
            try:
                conn.execute('''CREATE TABLE IF NOT EXISTS addlists (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    name TEXT,
                                    link TEXT,
                                    position INTEGER
                                )''')
            except Exception as e:
                logging.error(f"Addlists error: {str(e)}")
                conn.execute('''DROP TABLE IF EXISTS addlists''')
                conn.execute('''CREATE TABLE addlists (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    name TEXT,
                                    link TEXT,
                                    position INTEGER
                                )''')

            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('start_text', '')")
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('vpn_code', '')")
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('tgrass_enabled', '1')")

            try:
                cur = conn.execute("PRAGMA table_info(sponsors)")
                columns = [info[1] for info in cur.fetchall()]
                if 'position' not in columns:
                    conn.execute("ALTER TABLE sponsors ADD COLUMN position INTEGER")
                    conn.execute("UPDATE sponsors SET position = id WHERE position IS NULL")
            except Exception as e:
                logging.error(f"Sponsor migration error: {str(e)}")

            try:
                cur = conn.execute("PRAGMA table_info(addlists)")
                columns = [info[1] for info in cur.fetchall()]
                if 'position' not in columns:
                    conn.execute("ALTER TABLE addlists ADD COLUMN position INTEGER")
                    conn.execute("UPDATE addlists SET position = id WHERE position IS NULL")
            except Exception as e:
                logging.error(f"Addlist migration error: {str(e)}")

init_db()

def get_setting(key):
    with closing(sqlite3.connect('Fearsponsorbot.db')) as conn:
        try:
            cur = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
            res = cur.fetchone()
            return res[0] if res else ''
        except Exception as e:
            logging.error(f"Error: {str(e)}")
            return ''

def set_setting(key, value):
    with closing(sqlite3.connect('Fearsponsorbot.db')) as conn:
        try:
            with conn:
                conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        except Exception as e:
            logging.error(f"Error: {str(e)}")

def get_sponsors():
    with closing(sqlite3.connect('Fearsponsorbot.db')) as conn:
        try:
            cur = conn.execute("SELECT id, channel_id, link, position FROM sponsors ORDER BY position ASC")
            return cur.fetchall()
        except Exception as e:
            logging.error(f"Error: {str(e)}")
            return []

def get_addlists():
    with closing(sqlite3.connect('Fearsponsorbot.db')) as conn:
        try:
            cur = conn.execute("SELECT id, name, link, position FROM addlists ORDER BY position ASC")
            return cur.fetchall()
        except Exception as e:
            logging.error(f"Error: {str(e)}")
            return []

def get_all_users():
    with closing(sqlite3.connect('Fearsponsorbot.db')) as conn:
        try:
            cur = conn.execute("SELECT user_id FROM users")
            return [row[0] for row in cur.fetchall()]
        except Exception as e:
            logging.error(f"Error: {str(e)}")
            return []

async def is_user_subscribed(user_id, channel_id):
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return False

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
    sponsors = get_sponsors()
    addlists = get_addlists()
    used_urls = set()
    all_channels = []

    for sponsor in sponsors:
        if sponsor[2] not in used_urls and sponsor[3] is not None:
            used_urls.add(sponsor[2])
            all_channels.append({
                'id': sponsor[0],
                'link': sponsor[2],
                'position': sponsor[3],
                'channel_id': sponsor[1],
                'type': 'sponsor',
                'name': await get_channel_name(channel_id=sponsor[1]),
                'is_tgrass': False
            })

    for addlist in addlists:
        if addlist[2] not in used_urls and addlist[3] is not None:
            used_urls.add(addlist[2])
            all_channels.append({
                'id': addlist[0],
                'link': addlist[2],
                'position': addlist[3],
                'channel_id': None,
                'type': 'addlist',
                'name': addlist[1],
                'is_tgrass': False
            })

    tgrass_enabled = get_tgrass_enabled()
    if tgrass_enabled:
        tgrass_offers = check_tgrass_subscriptions(user_id, username, is_premium)
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
    
    all_channels.sort(key=lambda x: x['position'])
    return all_channels

async def check_all_subscriptions(user_id, username=None, is_premium=False):
    not_subscribed = []
    
    sponsors = get_sponsors()
    for sponsor in sponsors:
        channel_id = sponsor[1]
        if not await is_user_subscribed(user_id, channel_id):
            not_subscribed.append({
                'name': await get_channel_name(channel_id=sponsor[1]),
                'link': sponsor[2],
                'type': 'sponsor'
            })
    
    tgrass_enabled = get_tgrass_enabled()
    if tgrass_enabled:
        tgrass_offers = check_tgrass_subscriptions(user_id, username, is_premium)
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
    
    return len(not_subscribed) == 0, not_subscribed

# /start komut
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    is_premium = getattr(message.from_user, 'is_premium', False)
    
    with closing(sqlite3.connect('Fearsponsorbot.db')) as conn:
        try:
            with conn:
                conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        except Exception as e:
            logging.error(f"Error: {str(e)}")

    start_text = get_setting('start_text').strip()
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
        await message.answer(
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
    
    # ICON CUSTOM EMOJI ile buton (sadece icon olarak custom emoji)
    builder.button(
        text="Подписался",
        callback_data="check_sub",
        style="success",
        icon_custom_emoji_id=EMOJI_IDS["chik"]
    )
    
    builder.adjust(2)
    
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
        vpn_code = get_setting('vpn_code')
        if vpn_code:
            await call.message.answer(
                f"<tg-emoji emoji-id=\"{EMOJI_IDS['vpn']}\">✔️</tg-emoji> <b>Ваш VPN код:</b> <code>{vpn_code}</code>"
            )
        else:
            await call.message.answer(
                f"<tg-emoji emoji-id=\"{EMOJI_IDS['warning']}\">🔐</tg-emoji> VPN код еще не настроен администратором."
            )

# Admin panel
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer(
            f"<tg-emoji emoji-id=\"{EMOJI_IDS['warning']}\">🔐</tg-emoji> Вы не администратор!"
        )
        return
    
    builder = InlineKeyboardBuilder()
    
    # ICON CUSTOM EMOJI ile butonlar
    builder.button(
        text="Добавить спонсора",
        callback_data="add_sponsor",
        style="primary",
        icon_custom_emoji_id=EMOJI_IDS["add"]
    )
    builder.button(
        text="Удалить спонсора",
        callback_data="remove_sponsor",
        style="danger",
        icon_custom_emoji_id=EMOJI_IDS["del"]
    )
    builder.button(
        text="Изменить start текст",
        callback_data="edit_start",
        style="primary",
        icon_custom_emoji_id=EMOJI_IDS["tekst"]
    )
    builder.button(
        text="Изменить VPN код",
        callback_data="edit_code",
        style="danger",
        icon_custom_emoji_id=EMOJI_IDS["lock"]
    )
    builder.button(
        text="Добавить Addlist",
        callback_data="add_addlist",
        style="primary",
        icon_custom_emoji_id=EMOJI_IDS["add"]
    )
    builder.button(
        text="Удалить Addlist",
        callback_data="remove_addlist",
        style="danger",
        icon_custom_emoji_id=EMOJI_IDS["del"]
    )
    builder.button(
        text="Рассылка",
        callback_data="broadcast",
        style="primary",
        icon_custom_emoji_id=EMOJI_IDS["broadcast"]
    )
    builder.button(
        text="Статистика",
        callback_data="stats",
        style="danger",
        icon_custom_emoji_id=EMOJI_IDS["stats"]
    )
    builder.button(
        text="TGrass настройки",
        callback_data="tgrass_settings",
        style="success",
        icon_custom_emoji_id=EMOJI_IDS["tgrassn"]
    )
    
    builder.adjust(2)
    
    await message.answer(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['admin']}\">👑</tg-emoji> <b>Админ панель</b>",
        reply_markup=builder.as_markup()
    )

# ================= ADMIN CALLBACK HANDLERS =================

@dp.callback_query(F.data == "add_sponsor")
async def add_sponsor_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
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
    
    with closing(sqlite3.connect('Fearsponsorbot.db')) as conn:
        try:
            with conn:
                cur = conn.execute("SELECT MAX(position) FROM sponsors")
                max_pos = cur.fetchone()[0]
                new_position = (max_pos + 1) if max_pos else 1
                
                conn.execute(
                    "INSERT INTO sponsors (channel_id, link, position) VALUES (?, ?, ?)",
                    (channel_id, link, new_position)
                )
            
            await message.answer(
                f"<tg-emoji emoji-id=\"{EMOJI_IDS['success']}\">✅</tg-emoji> Спонсор успешно добавлен!\n"
                f"ID: {channel_id}\nСсылка: {link}"
            )
        except Exception as e:
            await message.answer(f"❌ Ошибка: {str(e)}")
    
    await state.clear()

@dp.callback_query(F.data == "remove_sponsor")
async def remove_sponsor_start(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    sponsors = get_sponsors()
    if not sponsors:
        await call.message.edit_text("❌ Список спонсоров пуст.")
        await call.answer()
        return
    
    text = f"<tg-emoji emoji-id=\"{EMOJI_IDS['remove']}\">➖</tg-emoji> <b>Выберите спонсора для удаления:</b>\n\n"
    builder = InlineKeyboardBuilder()
    
    for sponsor in sponsors:
        name = await get_channel_name(channel_id=sponsor[1])
        builder.button(
            text=f"❌ {name}",
            callback_data=f"del_sponsor_{sponsor[0]}"
        )
    
    builder.button(text="◀️ Назад", callback_data="back_to_admin")
    builder.adjust(1)
    
    await call.message.edit_text(text, reply_markup=builder.as_markup())
    await call.answer()

@dp.callback_query(F.data.startswith("del_sponsor_"))
async def delete_sponsor(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    sponsor_id = int(call.data.replace("del_sponsor_", ""))
    
    with closing(sqlite3.connect('Fearsponsorbot.db')) as conn:
        try:
            with conn:
                conn.execute("DELETE FROM sponsors WHERE id = ?", (sponsor_id,))
            await call.message.edit_text(
                f"<tg-emoji emoji-id=\"{EMOJI_IDS['success']}\">✅</tg-emoji> Спонсор удален!"
            )
        except Exception as e:
            await call.answer(f"Ошибка: {str(e)}", show_alert=True)
    
    await call.answer()

@dp.callback_query(F.data == "edit_start")
async def edit_start_text(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    current_text = get_setting('start_text')
    
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
    
    set_setting('start_text', new_text)
    
    preview_text = parse_premium_emoji(new_text)
    await message.answer(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['success']}\">✅</tg-emoji> <b>Текст сохранен!</b>\n\n"
        f"<b>Предпросмотр:</b>\n{preview_text}",
        parse_mode=ParseMode.HTML
    )
    
    await state.clear()

@dp.callback_query(F.data == "edit_code")
async def edit_vpn_code(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    current_code = get_setting('vpn_code')
    
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
    set_setting('vpn_code', new_code)
    
    await message.answer(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['success']}\">✅</tg-emoji> VPN код сохранен: <code>{new_code}</code>"
    )
    await state.clear()

@dp.callback_query(F.data == "add_addlist")
async def add_addlist_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
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
    
    with closing(sqlite3.connect('Fearsponsorbot.db')) as conn:
        try:
            with conn:
                cur = conn.execute("SELECT MAX(position) FROM addlists")
                max_pos = cur.fetchone()[0]
                new_position = (max_pos + 1) if max_pos else 1
                
                conn.execute(
                    "INSERT INTO addlists (name, link, position) VALUES (?, ?, ?)",
                    (name, link, new_position)
                )
            
            await message.answer(
                f"<tg-emoji emoji-id=\"{EMOJI_IDS['success']}\">✅</tg-emoji> Addlist успешно добавлен!\n"
                f"Название: {name}\nСсылка: {link}"
            )
        except Exception as e:
            await message.answer(f"❌ Ошибка: {str(e)}")
    
    await state.clear()

@dp.callback_query(F.data == "remove_addlist")
async def remove_addlist_start(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    addlists = get_addlists()
    if not addlists:
        await call.message.edit_text("❌ Список Addlist пуст.")
        await call.answer()
        return
    
    text = f"<tg-emoji emoji-id=\"{EMOJI_IDS['remove']}\">➖</tg-emoji> <b>Выберите Addlist для удаления:</b>\n\n"
    builder = InlineKeyboardBuilder()
    
    for addlist in addlists:
        builder.button(
            text=f"❌ {addlist[1]}",
            callback_data=f"del_addlist_{addlist[0]}"
        )
    
    builder.button(text="◀️ Назад", callback_data="back_to_admin")
    builder.adjust(1)
    
    await call.message.edit_text(text, reply_markup=builder.as_markup())
    await call.answer()

@dp.callback_query(F.data.startswith("del_addlist_"))
async def delete_addlist(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    addlist_id = int(call.data.replace("del_addlist_", ""))
    
    with closing(sqlite3.connect('Fearsponsorbot.db')) as conn:
        try:
            with conn:
                conn.execute("DELETE FROM addlists WHERE id = ?", (addlist_id,))
            await call.message.edit_text(
                f"<tg-emoji emoji-id=\"{EMOJI_IDS['success']}\">✅</tg-emoji> Addlist удален!"
            )
        except Exception as e:
            await call.answer(f"Ошибка: {str(e)}", show_alert=True)
    
    await call.answer()

@dp.callback_query(F.data == "broadcast")
async def broadcast_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
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
    
    users = get_all_users()
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
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    users = get_all_users()
    sponsors = get_sponsors()
    addlists = get_addlists()
    tgrass_enabled = get_tgrass_enabled()
    
    text = (
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['stats']}\">📊</tg-emoji> <b>Статистика бота</b>\n\n"
        f"👥 Пользователей: {len(users)}\n"
        f"📢 Спонсоров: {len(sponsors)}\n"
        f"📋 Addlist: {len(addlists)}\n"
        f"⚙️ TGrass: {'✅ Включен' if tgrass_enabled else '❌ Выключен'}\n"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Назад", callback_data="back_to_admin")
    
    await call.message.edit_text(text, reply_markup=builder.as_markup())
    await call.answer()

@dp.callback_query(F.data == "tgrass_settings")
async def tgrass_settings(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    enabled = get_tgrass_enabled()
    status_text = "✅ Включен" if enabled else "❌ Выключен"
    
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Включить" if not enabled else "❌ Выключить",
        callback_data="toggle_tgrass"
    )
    builder.button(text="◀️ Назад", callback_data="back_to_admin")
    builder.adjust(1)
    
    await call.message.edit_text(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['tgrassn']}\">⚙️</tg-emoji> <b>Настройки TGrass</b>\n\n"
        f"Статус: {status_text}\n\n"
        f"API Key: {TGRASS_API_KEY[:10]}...",
        reply_markup=builder.as_markup()
    )
    await call.answer()

@dp.callback_query(F.data == "toggle_tgrass")
async def toggle_tgrass(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    current = get_tgrass_enabled()
    set_tgrass_enabled(not current)
    
    new_status = "✅ Включен" if not current else "❌ Выключен"
    await call.answer(f"TGrass {new_status}!", show_alert=True)
    
    await tgrass_settings(call)

@dp.callback_query(F.data == "back_to_admin")
async def back_to_admin(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Доступ запрещен!", show_alert=True)
        return
    
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="Добавить спонсора",
        callback_data="add_sponsor",
        style="primary",
        icon_custom_emoji_id=EMOJI_IDS["add"]
    )
    builder.button(
        text="Удалить спонсора",
        callback_data="remove_sponsor",
        style="danger",
        icon_custom_emoji_id=EMOJI_IDS["del"]
    )
    builder.button(
        text="Изменить start текст",
        callback_data="edit_start",
        style="primary",
        icon_custom_emoji_id=EMOJI_IDS["tekst"]
    )
    builder.button(
        text="Изменить VPN код",
        callback_data="edit_code",
        style="danger",
        icon_custom_emoji_id=EMOJI_IDS["lock"]
    )
    builder.button(
        text="Добавить Addlist",
        callback_data="add_addlist",
        style="primary",
        icon_custom_emoji_id=EMOJI_IDS["add"]
    )
    builder.button(
        text="Удалить Addlist",
        callback_data="remove_addlist",
        style="danger",
        icon_custom_emoji_id=EMOJI_IDS["del"]
    )
    builder.button(
        text="Рассылка",
        callback_data="broadcast",
        style="primary",
        icon_custom_emoji_id=EMOJI_IDS["broadcast"]
    )
    builder.button(
        text="Статистика",
        callback_data="stats",
        style="danger",
        icon_custom_emoji_id=EMOJI_IDS["stats"]
    )
    builder.button(
        text="TGrass настройки",
        callback_data="tgrass_settings",
        style="success",
        icon_custom_emoji_id=EMOJI_IDS["tgrassn"]
    )
    
    builder.adjust(2)
    
    await call.message.edit_text(
        f"<tg-emoji emoji-id=\"{EMOJI_IDS['admin']}\">👑</tg-emoji> <b>Админ панель</b>",
        reply_markup=builder.as_markup()
    )
    await call.answer()

async def main():
    # Start Flask and Keep-Alive threads
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    ping_thread = threading.Thread(target=keep_alive_ping, daemon=True)
    ping_thread.start()
    
    logging.info("Bot started")
    print("🤖 Бот работает...")
    print(f"👑 Admin ID: {ADMIN_IDS[0]}")
    print("🌟 TGrass integration active")
    print("✨ Custom emoji icons on buttons enabled")
    
    try:
        test_offers = check_tgrass_subscriptions(123456789, "test_user", False)
        print(f"📡 TGrass API test: {len(test_offers)} channel(s) received")
    except Exception as e:
        print(f"❌ TGrass API test failed: {e}")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
