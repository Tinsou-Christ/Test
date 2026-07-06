import asyncio
import logging
import uuid

import requests
from telegram import Update, InputMediaPhoto, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

PIN_API = "https://egret-driving-cattle.ngrok-free.app/api/pin"
IMAGES_PER_PAGE = 9

# sessions de recherche en memoire (token -> resultats), perdues au redemarrage du bot
_sessions = {}


def _search_pinterest(query: str):
    response = requests.get(PIN_API, params={'query': query, 'num': 90}, timeout=20)
    response.raise_for_status()
    return response.json().get('results', [])


async def pinterest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)

    query = ' '.join(context.args).strip()
    if not query:
        await update.message.reply_text(
            "📌 Pinterest Search\n\n"
            "Utilisation :\n/pinterest <recherche>\n\n"
            "Exemple : /pinterest naruto wallpaper"
        )
        return

    wait_msg = await update.message.reply_text('🔍 Recherche Pinterest pour "{}"...'.format(query))

    try:
        urls = await asyncio.to_thread(_search_pinterest, query)
    except Exception as e:
        logger.error('pinterest api error: %s', str(e))
        await context.bot.edit_message_text(
            '❌ Pinterest API injoignable.',
            chat_id=update.effective_chat.id,
            message_id=wait_msg.message_id
        )
        return

    if not urls:
        await context.bot.edit_message_text(
            '❌ Aucune image trouvée pour "{}".'.format(query),
            chat_id=update.effective_chat.id,
            message_id=wait_msg.message_id
        )
        return

    await context.bot.delete_message(update.effective_chat.id, wait_msg.message_id)

    token = uuid.uuid4().hex[:12]
    _sessions[token] = {'urls': urls, 'query': query, 'page': 0}

    await _send_page(update.effective_chat.id, context, token)


async def _send_page(chat_id: int, context: ContextTypes.DEFAULT_TYPE, token: str):
    session = _sessions.get(token)
    if not session:
        return

    urls = session['urls']
    query = session['query']
    page = session['page']

    start = page * IMAGES_PER_PAGE
    slice_urls = urls[start:start + IMAGES_PER_PAGE]
    total_pages = (len(urls) - 1) // IMAGES_PER_PAGE + 1

    media = [InputMediaPhoto(url) for url in slice_urls]
    await context.bot.send_media_group(chat_id, media)

    keyboard = []
    if start + IMAGES_PER_PAGE < len(urls):
        keyboard.append([InlineKeyboardButton("➡️ Page suivante", callback_data='pin_next:{}'.format(token))])

    text = '📌 "{}" — page {}/{}'.format(query, page + 1, total_pages)
    if keyboard:
        await context.bot.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await context.bot.send_message(chat_id, text)


async def pinterest_next_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    token = query.data.split(':', 1)[1]

    session = _sessions.get(token)
    if not session:
        await query.answer('Session expirée, relance une recherche.')
        return

    session['page'] += 1
    await query.answer()
    await _send_page(update.effective_chat.id, context, token)
