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
import urllib.request
import urllib.parse
import re
import json as pyjson

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


def infer_category(name: str) -> str:
    n = (name or '').lower()
    if any(x in n for x in ['serum', 'skincare', 'cream', 'facial', 'masker wajah', 'toner', 'sunscreen']):
        return 'beauty'
    if any(x in n for x in ['baju', 'celana', 'kaos', 'kemeja', 'hoodie', 'fashion', 'dress', 'hijab']):
        return 'fashion'
    if any(x in n for x in ['lampu', 'rak', 'organizer', 'sprei', 'kursi', 'meja', 'home', 'dapur']):
        return 'home'
    if any(x in n for x in ['vitamin', 'supplement', 'health', 'kapsul']):
        return 'health'
    if any(x in n for x in ['earphone', 'charger', 'kabel', 'mouse', 'keyboard', 'power bank', 'gadget']):
        return 'gadget'
    return 'general'


def generate_reason(name: str, category: str, rating: str, sold_count: str, price_current: str) -> str:
    category = category or infer_category(name)
    if category == 'beauty':
        return f'Cocok buat yang lagi cari {name.lower()} dengan rating bagus dan harga lagi menarik.'
    if category == 'fashion':
        return f'Menarik buat yang lagi cari item fashion dengan harga lebih hemat dari biasanya.'
    if category == 'home':
        return f'Worth it dicek kalau kamu lagi cari kebutuhan rumah dengan harga promo.'
    if category == 'health':
        return f'Cocok buat yang lagi cari produk health dengan reputasi bagus dan harga lagi turun.'
    if category == 'gadget':
        return f'Menarik buat yang lagi cari aksesoris gadget dengan harga promo dan demand bagus.'
    return f'Cek promo produk ini sekarang, apalagi kalau kamu lagi butuh barang seperti ini.'


def generate_cta(category: str) -> str:
    cta_map = {
        'beauty': 'Kalau memang lagi cari skincare yang cocok, langsung cek detail dan checkout dari link ini.',
        'fashion': 'Kalau modelnya masuk dan harganya pas, langsung cek dan amankan dari link ini.',
        'home': 'Kalau lagi butuh buat rumah, langsung cek promo dan pertimbangkan checkout sekarang.',
        'health': 'Kalau produk ini memang kamu butuhkan, langsung cek detailnya dari link berikut.',
        'gadget': 'Kalau lagi cari aksesoris gadget yang worth it, langsung cek dan beli dari link ini.',
        'general': 'Kalau produknya cocok buat kamu, langsung cek promo dan beli dari link ini.',
    }
    return cta_map.get(category, cta_map['general'])


def format_price(value: int) -> str:
    return 'Rp{:,.0f}'.format(value).replace(',', '.')


def parse_sold_count(v) -> str:
    try:
        n = int(v)
        if n >= 1000:
            ribu = round(n / 1000)
            return f'{ribu}RB+'
        return str(n)
    except Exception:
        return '-'


def resolve_short_link(short_link: str) -> str:
    req = urllib.request.Request(short_link, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.geturl()


def extract_shop_item_ids(url: str):
    m = re.search(r'i\.(\d+)\.(\d+)', url)
    if not m:
        m = re.search(r'/product/(\d+)/(\d+)', url)
    if not m:
        return None, None
    return m.group(1), m.group(2)


def fetch_product_metadata(short_link: str) -> dict:
    final_url = resolve_short_link(short_link)
    shop_id, item_id = extract_shop_item_ids(final_url)
    slug = final_url.split('/')[-1]
    slug_name = re.sub(r'-i\.\d+\.\d+.*$', '', slug).replace('-', ' ').strip()
    if not shop_id or not item_id:
        return {
            'label': slug_name.title() or 'Produk Shopee',
            'category': infer_category(slug_name),
            'reason': generate_reason(slug_name, infer_category(slug_name), '-', '-', ''),
            'price_previous': '',
            'price_current': '',
            'rating': '-',
            'sold_count': '-',
            'drop_amount': '',
            'drop_percent': '',
            'final_url': final_url,
        }
    api = f'https://shopee.co.id/api/v4/item/get?itemid={item_id}&shopid={shop_id}'
    req = urllib.request.Request(api, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = pyjson.loads(resp.read().decode())
    item = (data or {}).get('data') or {}
    name = item.get('name') or slug_name.title() or 'Produk Shopee'
    price = item.get('price') or 0
    price_before = item.get('price_before_discount') or 0
    rating = str(round(((item.get('item_rating') or {}).get('rating_star') or 0), 1)) if (item.get('item_rating') or {}).get('rating_star') else '-'
    sold_count = parse_sold_count(item.get('historical_sold') or 0)
    price_current = format_price(price / 100000) if price else ''
    price_previous = format_price(price_before / 100000) if price_before else ''
    drop_amount = ''
    drop_percent = ''
    if price_before and price and price_before > price:
        amount = int((price_before - price) / 100000)
        pct = round((price_before - price) / price_before * 100)
        drop_amount = format_price(amount)
        drop_percent = f'{pct}%'
    category = infer_category(name)
    reason = generate_reason(name, category, rating, sold_count, price_current)
    return {
        'label': name,
        'category': category,
        'reason': reason,
        'price_previous': price_previous,
        'price_current': price_current,
        'rating': rating,
        'sold_count': sold_count,
        'drop_amount': drop_amount,
        'drop_percent': drop_percent,
        'final_url': final_url,
    }


def build_post_text(label: str, short_link: str, category: str = 'general', reason: str = '', price_previous: str = '', price_current: str = '', rating: str = '', sold_count: str = '', drop_amount: str = '', drop_percent: str = '') -> str:
    lines = ['🔥 *Harga Turun*', f'*{label or "Produk Pilihan"}*', '']
    if price_previous:
        lines.append(f'💸 Harga normal: *{price_previous}*')
    if price_current:
        lines.append(f'🛒 Harga sekarang: *{price_current}*')
    if drop_amount or drop_percent:
        drop_text = drop_amount or '-'
        if drop_percent:
            drop_text += f' ({drop_percent})' if '%' in drop_percent else f' ({drop_percent}%)'
        lines.append(f'📉 Hemat: *{drop_text}*')
    if rating or sold_count:
        rating_text = rating or '-'
        sold_text = sold_count or '-'
        lines.append(f'⭐ Rating: *{rating_text}* | Terjual: *{sold_text}*')
    lines.append('')
    lines.append(reason or 'Cek promo produk pilihan ini sekarang sebelum harganya berubah lagi.')
    lines.append('')
    lines.append('👉 Cek promonya di sini:')
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
        '/post <short_affiliate_link> - bot generate caption otomatis lalu post ke channel\n'
        '/preview <short_affiliate_link> - bot generate preview caption otomatis\n'
        '/add_watch <short_link> | <label> | <category> | <reason> | <harga_lama> | <harga_sekarang>\n'
        '/list_watch - lihat watchlist aktif\n\n'
        'Mode otomatis V1:\n'
        '/auto_on - aktifkan auto post dari watchlist\n'
        '/auto_off - matikan auto post\n'
        '/auto_status - status auto mode\n'
        '/run_once - jalankan 1 siklus auto sekarang\n\n'
        f'Status auto saat ini: {auto_mode.upper()}\n'
        'Catatan V1: manual mode cukup short affiliate link s.shopee.co.id dan bot akan generate caption otomatis; auto mode masih berbasis watchlist, belum full scraping harga live.'
    )
    await update.message.reply_text(text)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start_cmd(update, context)


def parse_manual_payload(raw: str) -> Optional[dict]:
    parts = [x.strip() for x in raw.split('|')]
    if len(parts) < 8:
        return None
    while len(parts) < 9:
        parts.append('')
    short_link, label, category, reason, price_previous, price_current, rating, sold_count, drop_text = parts[:9]
    if not validate_affiliate_link(short_link):
        return None
    drop_amount = ''
    drop_percent = ''
    if drop_text:
        if '/' in drop_text:
            a, b = [x.strip() for x in drop_text.split('/', 1)]
            drop_amount, drop_percent = a, b
        else:
            drop_amount = drop_text
    return {
        'short_link': short_link,
        'label': label,
        'category': category or 'general',
        'reason': reason,
        'price_previous': price_previous,
        'price_current': price_current,
        'rating': rating,
        'sold_count': sold_count,
        'drop_amount': drop_amount,
        'drop_percent': drop_percent,
    }


async def preview_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update):
        return
    if not context.args:
        await update.message.reply_text('Format: /preview <short_affiliate_link>')
        return
    link = context.args[0].strip()
    if not validate_affiliate_link(link):
        await update.message.reply_text('Link tidak valid. Gunakan short affiliate link seperti https://s.shopee.co.id/...')
        return
    await update.message.reply_chat_action(ChatAction.TYPING)
    try:
        meta = await asyncio.to_thread(fetch_product_metadata, link)
        text = build_post_text(short_link=link, **meta)
        await update.message.reply_text(text, parse_mode='Markdown', disable_web_page_preview=False)
    except Exception as e:
        logger.exception('preview failed')
        await update.message.reply_text(f'Preview gagal: {e}')


async def post_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update):
        return
    if not context.args:
        await update.message.reply_text('Format: /post <short_affiliate_link>')
        return
    link = context.args[0].strip()
    if not validate_affiliate_link(link):
        await update.message.reply_text('Link tidak valid. Gunakan short affiliate link seperti https://s.shopee.co.id/...')
        return
    await update.message.reply_chat_action(ChatAction.TYPING)
    try:
        meta = await asyncio.to_thread(fetch_product_metadata, link)
        text = build_post_text(short_link=link, **meta)
        msg_id = await send_channel_post(context.application, text)
        log_post('manual', meta['label'], link, meta['category'], meta['reason'], msg_id)
        await update.message.reply_text(f'Berhasil dipost ke channel. message_id={msg_id}')
    except Exception as e:
        logger.exception('post failed')
        await update.message.reply_text(f'Post gagal: {e}')


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
