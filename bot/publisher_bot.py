from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from telegram import BotCommand, Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes

import urllib.request

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / 'bot' / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    handlers=[logging.FileHandler(LOG_DIR / 'publisher-bot.log', encoding='utf-8')],
)
logger = logging.getLogger('pemburu_promo_simple_bot')

load_dotenv(BASE_DIR / '.env')
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
OWNER_CHAT_ID = int(os.getenv('BOT_OWNER_CHAT_ID', '5082668523').strip())
CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID', '').strip()

if not TOKEN or not CHANNEL_ID:
    raise RuntimeError('Bot token atau channel id belum terisi')


def is_owner(update: Update) -> bool:
    return bool(update.effective_chat and update.effective_chat.id == OWNER_CHAT_ID)


async def reject(update: Update) -> bool:
    if is_owner(update):
        return False
    if update.effective_message:
        await update.effective_message.reply_text('Unauthorized chat.')
    return True


def validate_affiliate_link(link: str) -> bool:
    try:
        p = urlparse(link.strip())
        return p.scheme in {'http', 'https'} and p.netloc.endswith('s.shopee.co.id')
    except Exception:
        return False


def infer_category(name: str) -> str:
    n = (name or '').lower()
    if any(x in n for x in ['serum', 'skincare', 'toner', 'sunscreen', 'facial', 'cream']):
        return 'Beauty'
    if any(x in n for x in ['baju', 'celana', 'kaos', 'dress', 'hoodie', 'fashion', 'hijab']):
        return 'Fashion'
    if any(x in n for x in ['lampu', 'rak', 'organizer', 'meja', 'kursi', 'sprei', 'dapur', 'home']):
        return 'HomeLiving'
    if any(x in n for x in ['vitamin', 'supplement', 'health', 'kapsul']):
        return 'Health'
    if any(x in n for x in ['charger', 'kabel', 'mouse', 'keyboard', 'power bank', 'earphone', 'gadget']):
        return 'Gadget'
    return 'PromoPilihan'


def category_hashtag(category: str) -> str:
    return '#' + (category or 'PromoPilihan').replace(' ', '')


def fmt_rp(v: int) -> str:
    return 'Rp{:,.0f}'.format(v).replace(',', '.')


def sold_compact(n: int) -> str:
    if not n:
        return '-'
    return f'{round(n/1000)}RB+' if n >= 1000 else str(n)


def clean_name_from_url(url: str) -> str:
    slug = url.split('/')[-1] if '/' in url else url
    slug = slug.split('?')[0]
    slug = re.sub(r'-i\.\d+\.\d+.*$', '', slug)
    slug = slug.replace('-', ' ').strip()
    if not slug or re.search(r'utm_|gads_|mobile=|mmp_pid|uls_trackid', slug, re.I):
        return 'Produk Shopee Pilihan'
    return re.sub(r'\s+', ' ', slug).title()


def resolve_short_link(short_link: str) -> str:
    req = urllib.request.Request(short_link, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.geturl()


def extract_ids(url: str):
    m = re.search(r'i\.(\d+)\.(\d+)', url) or re.search(r'/product/(\d+)/(\d+)', url)
    return (m.group(1), m.group(2)) if m else (None, None)


def generate_reason(name: str, category: str) -> str:
    if category == 'Beauty':
        return f'Cocok buat yang lagi cari {name.lower()} dengan harga promo yang lebih menarik.'
    if category == 'Fashion':
        return 'Menarik buat yang lagi cari item fashion dengan harga lebih hemat dari biasanya.'
    if category == 'HomeLiving':
        return 'Worth it dicek kalau kamu lagi cari kebutuhan rumah dengan harga promo.'
    if category == 'Health':
        return 'Cocok buat yang lagi cari produk health dengan harga promo yang lebih masuk akal.'
    if category == 'Gadget':
        return 'Menarik buat yang lagi cari aksesoris gadget dengan harga promo.'
    return 'Cek promo produk ini sekarang sebelum harganya berubah lagi.'


def generate_cta(category: str, link: str) -> str:
    if category == 'Beauty':
        text = 'Kalau lagi cari skincare yang cocok, langsung cek detail dan checkout dari link ini.'
    elif category == 'Fashion':
        text = 'Kalau modelnya masuk dan harganya pas, langsung cek dan amankan dari link ini.'
    elif category == 'HomeLiving':
        text = 'Kalau lagi butuh buat rumah, langsung cek promo dan pertimbangkan checkout sekarang.'
    elif category == 'Health':
        text = 'Kalau produk ini memang kamu butuhkan, langsung cek detailnya dari link berikut.'
    elif category == 'Gadget':
        text = 'Kalau lagi cari aksesoris gadget yang worth it, langsung cek dan beli dari link ini.'
    else:
        text = 'Kalau produknya cocok buat kamu, langsung cek promo dan beli dari link ini.'
    return f'{text}\n\n👉 Cek promonya di sini:\n{link}'


def fetch_metadata(short_link: str) -> dict:
    final_url = resolve_short_link(short_link)
    shop_id, item_id = extract_ids(final_url)
    fallback_name = clean_name_from_url(final_url)
    if not shop_id or not item_id:
        category = infer_category(fallback_name)
        return {
            'product_name': fallback_name,
            'category': category,
            'normal_price': 0,
            'promo_price': 0,
            'discount_amount': 0,
            'discount_percent': 0,
            'rating': '-',
            'sold_count': 0,
            'reason': generate_reason(fallback_name, category),
            'affiliate_link': short_link,
        }
    try:
        api = f'https://shopee.co.id/api/v4/item/get?itemid={item_id}&shopid={shop_id}'
        req = urllib.request.Request(api, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        item = (data or {}).get('data') or {}
        name = item.get('name') or fallback_name
        category = infer_category(name)
        current = int((item.get('price') or 0) / 100000)
        before = int((item.get('price_before_discount') or 0) / 100000) or current
        discount_amount = max(0, before - current)
        discount_percent = int(round(((before - current) / before) * 100)) if before > current and before else 0
        rating = str(round(((item.get('item_rating') or {}).get('rating_star') or 0), 1)) if (item.get('item_rating') or {}).get('rating_star') else '-'
        sold_count = int(item.get('historical_sold') or 0)
        return {
            'product_name': name,
            'category': category,
            'normal_price': before,
            'promo_price': current,
            'discount_amount': discount_amount,
            'discount_percent': discount_percent,
            'rating': rating,
            'sold_count': sold_count,
            'reason': generate_reason(name, category),
            'affiliate_link': short_link,
        }
    except Exception:
        category = infer_category(fallback_name)
        return {
            'product_name': fallback_name,
            'category': category,
            'normal_price': 0,
            'promo_price': 0,
            'discount_amount': 0,
            'discount_percent': 0,
            'rating': '-',
            'sold_count': 0,
            'reason': generate_reason(fallback_name, category),
            'affiliate_link': short_link,
        }


def build_caption(meta: dict) -> str:
    lines = ['🔥 *Harga Turun*', f"*{meta['product_name']}*", '']
    if meta['normal_price']:
        lines.append(f"💸 Harga normal: *{fmt_rp(meta['normal_price'])}*")
    if meta['promo_price']:
        lines.append(f"🛒 Harga sekarang: *{fmt_rp(meta['promo_price'])}*")
    if meta['discount_amount'] or meta['discount_percent']:
        lines.append(f"📉 Hemat: *{fmt_rp(meta['discount_amount'])} ({meta['discount_percent']}%)*")
    lines.append(f"⭐ Rating: *{meta['rating']}* | Terjual: *{sold_compact(meta['sold_count'])}*")
    lines.append('')
    lines.append(meta['reason'])
    lines.append('')
    lines.append(generate_cta(meta['category'], meta['affiliate_link']))
    lines.append('')
    lines.append(f"#PromoShopee {category_hashtag(meta['category'])}")
    return '\n'.join(lines)


async def send_channel_post(app: Application, text: str) -> str:
    msg = await app.bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode='Markdown', disable_web_page_preview=False)
    return str(msg.message_id)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject(update):
        return
    text = (
        'Pemburu Promo Shopee Bot siap.\n\n'
        'Command sederhana:\n'
        '/preview <short_affiliate_link> - generate caption tanpa post\n'
        '/post <short_affiliate_link> - generate caption lalu post ke channel\n\n'
        'Format link yang diterima:\n'
        'https://s.shopee.co.id/...'
    )
    await update.message.reply_text(text)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start_cmd(update, context)


async def preview_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject(update):
        return
    if not context.args:
        await update.message.reply_text('Format: /preview <short_affiliate_link>')
        return
    link = context.args[0].strip()
    if not validate_affiliate_link(link):
        await update.message.reply_text('Link tidak valid. Gunakan short affiliate link Shopee seperti https://s.shopee.co.id/...')
        return
    await update.message.reply_chat_action(ChatAction.TYPING)
    try:
        meta = await asyncio.to_thread(fetch_metadata, link)
        caption = build_caption(meta)
        await update.message.reply_text(caption, parse_mode='Markdown', disable_web_page_preview=False)
    except Exception as e:
        logger.exception('preview failed')
        await update.message.reply_text(f'Preview gagal: {e}')


async def post_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject(update):
        return
    if not context.args:
        await update.message.reply_text('Format: /post <short_affiliate_link>')
        return
    link = context.args[0].strip()
    if not validate_affiliate_link(link):
        await update.message.reply_text('Link tidak valid. Gunakan short affiliate link Shopee seperti https://s.shopee.co.id/...')
        return
    await update.message.reply_chat_action(ChatAction.TYPING)
    try:
        meta = await asyncio.to_thread(fetch_metadata, link)
        caption = build_caption(meta)
        msg_id = await send_channel_post(context.application, caption)
        await update.message.reply_text(f'Berhasil dipost ke channel. message_id={msg_id}')
    except Exception as e:
        logger.exception('post failed')
        await update.message.reply_text(f'Post gagal: {e}')


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception('Unhandled bot error', exc_info=context.error)


async def post_init(app: Application) -> None:
    await app.bot.set_my_commands([
        BotCommand('start', 'Start bot'),
        BotCommand('help', 'Bantuan'),
        BotCommand('preview', 'Preview caption dari short link'),
        BotCommand('post', 'Post ke channel dari short link'),
    ])
    logger.info('Simple publisher bot commands registered')


def build_app() -> Application:
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler('start', start_cmd))
    app.add_handler(CommandHandler('help', help_cmd))
    app.add_handler(CommandHandler('preview', preview_cmd))
    app.add_handler(CommandHandler('post', post_cmd))
    app.add_error_handler(error_handler)
    return app


if __name__ == '__main__':
    logger.info('Starting Pemburu Promo Shopee Simple bot')
    asyncio.set_event_loop(asyncio.new_event_loop())
    app = build_app()
    app.run_polling(drop_pending_updates=False)
