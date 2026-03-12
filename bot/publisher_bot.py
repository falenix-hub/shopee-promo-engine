from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from dotenv import load_dotenv
from telegram import BotCommand, Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes

BASE_DIR = Path(__file__).resolve().parent.parent
BOT_DIR = BASE_DIR / 'bot'
LOG_DIR = BOT_DIR / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = BASE_DIR / 'data' / 'promo_engine.db'
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    handlers=[logging.FileHandler(LOG_DIR / 'publisher-bot.log', encoding='utf-8')],
)
logger = logging.getLogger('pemburu_promo_bot')

load_dotenv(BASE_DIR / '.env')


@dataclass
class Settings:
    token: str
    owner_chat_id: int
    channel_id: str
    channel_name: str
    channel_username: str
    auto_scan_minutes: int

    @classmethod
    def from_env(cls) -> 'Settings':
        token = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
        owner = os.getenv('BOT_OWNER_CHAT_ID', '').strip()
        channel_id = os.getenv('TELEGRAM_CHANNEL_ID', '').strip()
        channel_name = os.getenv('TELEGRAM_CHANNEL_NAME', 'Pemburu Promo Shopee').strip()
        channel_username = os.getenv('TELEGRAM_CHANNEL_USERNAME', '').strip()
        auto_scan_minutes = int(os.getenv('AUTO_SCAN_MINUTES', '30').strip())
        if not token:
            raise RuntimeError('TELEGRAM_BOT_TOKEN missing')
        if not owner:
            raise RuntimeError('BOT_OWNER_CHAT_ID missing')
        if not channel_id:
            raise RuntimeError('TELEGRAM_CHANNEL_ID missing')
        return cls(token, int(owner), channel_id, channel_name, channel_username, auto_scan_minutes)


SETTINGS = Settings.from_env()


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript(
        '''
        CREATE TABLE IF NOT EXISTS state (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT,
            short_link TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            reason TEXT DEFAULT '',
            price_previous TEXT DEFAULT '',
            price_current TEXT DEFAULT '',
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT,
            label TEXT,
            short_link TEXT NOT NULL,
            category TEXT,
            reason TEXT,
            posted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            telegram_message_id TEXT
        );
        '''
    )
    conn.commit()
    conn.close()


def get_state(key: str, default: str = '') -> str:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT value FROM state WHERE key = ?', (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else default


def set_state(key: str, value: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('INSERT INTO state(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, value))
    conn.commit()
    conn.close()


def is_owner(update: Update) -> bool:
    chat = update.effective_chat
    return bool(chat and chat.id == SETTINGS.owner_chat_id)


async def reject_if_unauthorized(update: Update) -> bool:
    if is_owner(update):
        return False
    if update.effective_message:
        await update.effective_message.reply_text('Unauthorized chat.')
    return True


def validate_affiliate_link(link: str) -> bool:
    try:
        parsed = urlparse(link.strip())
        return parsed.scheme in {'http', 'https'} and parsed.netloc.endswith('s.shopee.co.id')
    except Exception:
        return False


def category_hashtag(category: str) -> str:
    mapping = {
        'beauty': '#Beauty',
        'fashion': '#Fashion',
        'home': '#HomeLiving',
        'health': '#Health',
        'gadget': '#Gadget',
        'general': '#PromoPilihan',
    }
    return mapping.get(category.lower(), '#PromoPilihan')


def build_post_text(label: str, short_link: str, category: str = 'general', reason: str = '', price_previous: str = '', price_current: str = '') -> str:
    lines = ['🔥 *Promo Shopee Pilihan*', f'*{label or "Produk Pilihan"}*', '']
    if price_previous and price_current:
        lines.append(f'💸 Harga normal: *{price_previous}*')
        lines.append(f'🛒 Harga sekarang: *{price_current}*')
    if reason:
        lines.append('')
        lines.append(reason)
    else:
        lines.append('')
        lines.append('Cek promo produk pilihan ini sekarang sebelum harganya berubah lagi.')
    lines.append('')
    lines.append('👉 Link promo:')
    lines.append(short_link)
    lines.append('')
    lines.append(f'#PromoShopee {category_hashtag(category)}')
    return '\n'.join(lines)


async def send_channel_post(app: Application, text: str) -> str:
    msg = await app.bot.send_message(chat_id=SETTINGS.channel_id, text=text, parse_mode='Markdown', disable_web_page_preview=False)
    return str(msg.message_id)


def add_watch_item(label: str, short_link: str, category: str, reason: str, price_previous: str, price_current: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO watchlist(label, short_link, category, reason, price_previous, price_current, active) VALUES(?,?,?,?,?,?,1)',
        (label, short_link, category, reason, price_previous, price_current),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def list_watch_items(limit: int = 20):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT id, label, short_link, category, active FROM watchlist ORDER BY id DESC LIMIT ?', (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_first_active_watch_item() -> Optional[dict]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT id, label, short_link, category, reason, price_previous, price_current FROM watchlist WHERE active=1 ORDER BY id ASC LIMIT 1')
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        'id': row[0],
        'label': row[1],
        'short_link': row[2],
        'category': row[3],
        'reason': row[4],
        'price_previous': row[5],
        'price_current': row[6],
    }


def log_post(source_type: str, label: str, short_link: str, category: str, reason: str, telegram_message_id: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO posts(source_type, label, short_link, category, reason, telegram_message_id) VALUES(?,?,?,?,?,?)',
        (source_type, label, short_link, category, reason, telegram_message_id),
    )
    conn.commit()
    conn.close()


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update):
        return
    auto_mode = get_state('auto_mode', 'off')
    text = (
        'Pemburu Promo Shopee Bot siap.\n\n'
        'Mode manual:\n'
        '/post <short_affiliate_link> - langsung post ke channel\n'
        '/preview <short_affiliate_link> - preview caption tanpa kirim\n'
        '/add_watch <short_link> | <label> | <category> | <reason> | <harga_lama> | <harga_sekarang>\n'
        '/list_watch - lihat watchlist aktif\n\n'
        'Mode otomatis V1:\n'
        '/auto_on - aktifkan auto post dari watchlist\n'
        '/auto_off - matikan auto post\n'
        '/auto_status - status auto mode\n'
        '/run_once - jalankan 1 siklus auto sekarang\n\n'
        f'Status auto saat ini: {auto_mode.upper()}\n'
        'Catatan V1: manual mode menerima short affiliate link s.shopee.co.id; auto mode masih berbasis watchlist, belum full scraping harga live.'
    )
    await update.message.reply_text(text)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start_cmd(update, context)


async def preview_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update):
        return
    if not context.args:
        await update.message.reply_text('Format: /preview <short_affiliate_link>')
        return
    link = context.args[0].strip()
    if not validate_affiliate_link(link):
        await update.message.reply_text('Link tidak valid. V1 hanya menerima short affiliate link seperti https://s.shopee.co.id/...')
        return
    text = build_post_text('Produk Pilihan Shopee', link, 'general')
    await update.message.reply_text(text, parse_mode='Markdown', disable_web_page_preview=False)


async def post_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update):
        return
    if not context.args:
        await update.message.reply_text('Format: /post <short_affiliate_link>')
        return
    link = context.args[0].strip()
    if not validate_affiliate_link(link):
        await update.message.reply_text('Link tidak valid. V1 hanya menerima short affiliate link seperti https://s.shopee.co.id/...')
        return
    text = build_post_text('Produk Pilihan Shopee', link, 'general')
    await update.message.reply_chat_action(ChatAction.TYPING)
    msg_id = await send_channel_post(context.application, text)
    log_post('manual', 'Produk Pilihan Shopee', link, 'general', '', msg_id)
    await update.message.reply_text(f'Berhasil dipost ke channel. message_id={msg_id}')


async def add_watch_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update):
        return
    raw = ' '.join(context.args).strip()
    if not raw or '|' not in raw:
        await update.message.reply_text('Format: /add_watch <short_link> | <label> | <category> | <reason> | <harga_lama> | <harga_sekarang>')
        return
    parts = [x.strip() for x in raw.split('|')]
    while len(parts) < 6:
        parts.append('')
    short_link, label, category, reason, price_previous, price_current = parts[:6]
    if not validate_affiliate_link(short_link):
        await update.message.reply_text('Short affiliate link tidak valid.')
        return
    row_id = add_watch_item(label or 'Produk Watchlist', short_link, category or 'general', reason, price_previous, price_current)
    await update.message.reply_text(f'Watchlist ditambahkan. id={row_id}')


async def list_watch_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update):
        return
    rows = list_watch_items()
    if not rows:
        await update.message.reply_text('Watchlist masih kosong.')
        return
    lines = ['Watchlist aktif:']
    for row in rows:
        lines.append(f'- #{row[0]} | {row[1] or "(tanpa label)"} | {row[3]} | active={row[4]}')
    await update.message.reply_text('\n'.join(lines))


async def auto_on_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update):
        return
    set_state('auto_mode', 'on')
    await update.message.reply_text('Auto mode diaktifkan.')


async def auto_off_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update):
        return
    set_state('auto_mode', 'off')
    await update.message.reply_text('Auto mode dimatikan.')


async def auto_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update):
        return
    mode = get_state('auto_mode', 'off')
    rows = list_watch_items(limit=5)
    text = f'Auto mode: {mode.upper()}\nInterval: {SETTINGS.auto_scan_minutes} menit\nWatchlist aktif: {len(rows)}\n\nBatasan V1:\n- auto mode berbasis watchlist\n- manual mode hanya short affiliate link s.shopee.co.id\n- full scraping harga live belum aktif'
    await update.message.reply_text(text)


async def run_once_core(app: Application) -> str:
    item = get_first_active_watch_item()
    if not item:
        return 'Watchlist kosong.'
    text = build_post_text(item['label'] or 'Produk Watchlist', item['short_link'], item['category'] or 'general', item['reason'] or '', item['price_previous'] or '', item['price_current'] or '')
    msg_id = await send_channel_post(app, text)
    log_post('auto', item['label'] or 'Produk Watchlist', item['short_link'], item['category'] or 'general', item['reason'] or '', msg_id)
    return f"Auto post sukses. item_id={item['id']} message_id={msg_id}"


async def run_once_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update):
        return
    result = await run_once_core(context.application)
    await update.message.reply_text(result)


async def auto_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    if get_state('auto_mode', 'off') != 'on':
        return
    try:
        result = await run_once_core(context.application)
        logger.info('auto_job result: %s', result)
    except Exception:
        logger.exception('auto_job failed')


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception('Unhandled bot error', exc_info=context.error)


async def post_init(app: Application) -> None:
    await app.bot.set_my_commands([
        BotCommand('start', 'Start bot'),
        BotCommand('help', 'Daftar command'),
        BotCommand('preview', 'Preview post dari short affiliate link'),
        BotCommand('post', 'Post manual ke channel'),
        BotCommand('add_watch', 'Tambah item watchlist auto'),
        BotCommand('list_watch', 'Lihat watchlist'),
        BotCommand('auto_on', 'Aktifkan auto mode'),
        BotCommand('auto_off', 'Matikan auto mode'),
        BotCommand('auto_status', 'Status auto mode'),
        BotCommand('run_once', 'Jalankan 1 auto post sekarang'),
    ])
    app.job_queue.run_repeating(auto_job, interval=SETTINGS.auto_scan_minutes * 60, first=SETTINGS.auto_scan_minutes * 60, name='promo-auto-job')
    logger.info('Publisher bot commands registered')


def build_app() -> Application:
    app = Application.builder().token(SETTINGS.token).post_init(post_init).build()
    app.add_handler(CommandHandler('start', start_cmd))
    app.add_handler(CommandHandler('help', help_cmd))
    app.add_handler(CommandHandler('preview', preview_cmd))
    app.add_handler(CommandHandler('post', post_cmd))
    app.add_handler(CommandHandler('add_watch', add_watch_cmd))
    app.add_handler(CommandHandler('list_watch', list_watch_cmd))
    app.add_handler(CommandHandler('auto_on', auto_on_cmd))
    app.add_handler(CommandHandler('auto_off', auto_off_cmd))
    app.add_handler(CommandHandler('auto_status', auto_status_cmd))
    app.add_handler(CommandHandler('run_once', run_once_cmd))
    app.add_error_handler(error_handler)
    return app


if __name__ == '__main__':
    init_db()
    logger.info('Starting Pemburu Promo Shopee Publisher bot')
    asyncio.set_event_loop(asyncio.new_event_loop())
    app = build_app()
    app.run_polling(drop_pending_updates=False)
