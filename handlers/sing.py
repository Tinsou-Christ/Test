import asyncio
import logging
import os
import re
import tempfile
import uuid

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

BASE_URL = "https://xalman-apis.vercel.app/api"

# sessions de recherche en memoire (token -> resultats), perdues au redemarrage du bot
_sessions = {}


def extract_youtube_url(text):
    if not text:
        return None
    match = re.search(r'(https?://[^\s]+)', text)
    if match and 'youtu' in match.group(1):
        return match.group(1)
    return None


def _search_songs(query: str):
    response = requests.get(
        "{}/ytsearch".format(BASE_URL),
        params={"q": query},
        timeout=30
    )
    response.raise_for_status()
    data = response.json()
    return (data.get("results") or [])[:5]


def _fetch_download_url(youtube_url: str) -> dict:
    response = requests.get(
        "{}/ytmp3".format(BASE_URL),
        params={"url": youtube_url},
        timeout=60
    )
    response.raise_for_status()
    return response.json()


def _download_file_to_tempfile(url: str, extension: str) -> str:
    response = requests.get(url, stream=True, timeout=90)
    response.raise_for_status()

    fd, tmp_path = tempfile.mkstemp(suffix='.{}'.format(extension))
    with os.fdopen(fd, 'wb') as f:
        for chunk in response.iter_content(chunk_size=1024 * 64):
            f.write(chunk)

    return tmp_path


async def _download_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, youtube_url: str, duration: str = "N/A"):
    wait_msg = await context.bot.send_message(chat_id, "⏳ Traitement de l'audio...")

    tmp_path = None
    try:
        data = await asyncio.to_thread(_fetch_download_url, youtube_url)

        if not data.get("success") or not data.get("url"):
            await context.bot.delete_message(chat_id, wait_msg.message_id)
            await context.bot.send_message(chat_id, "❌ Cette musique dépasse 25 Mo (l'API n'a pas renvoyé de lien).")
            return

        tmp_path = await asyncio.to_thread(_download_file_to_tempfile, data["url"], 'mp3')

        caption = "🎵 {}\n👤 {}\n⏱️ {}".format(
            data.get("title", "Inconnu"),
            data.get("author", "Inconnu"),
            duration
        )

        await context.bot.delete_message(chat_id, wait_msg.message_id)

        with open(tmp_path, 'rb') as f:
            await context.bot.send_audio(chat_id, audio=f, caption=caption)

    except Exception as e:
        logger.error('sing download error: %s', str(e), exc_info=True)
        try:
            await context.bot.delete_message(chat_id, wait_msg.message_id)
        except Exception:
            pass
        await context.bot.send_message(chat_id, "⚠️ Erreur : {}".format(str(e)[:300]))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


async def sing_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)

    query = ' '.join(context.args).strip()

    # lien youtube dans le message repondu
    if not query and update.message.reply_to_message:
        yt_url = extract_youtube_url(update.message.reply_to_message.text)
        if yt_url:
            await _download_and_send(update, context, update.effective_chat.id, yt_url)
            return

    # lien youtube direct dans la commande
    if query and 'youtu' in query:
        await _download_and_send(update, context, update.effective_chat.id, query)
        return

    if not query:
        await update.message.reply_text(
            "❌ Merci de fournir un nom de musique ou un lien YouTube.\nExemple : /sing Blinding Lights"
        )
        return

    wait_msg = await update.message.reply_text("🔍 Recherche en cours...")

    try:
        results = await asyncio.to_thread(_search_songs, query)
    except Exception as e:
        logger.error('sing search error: %s', str(e))
        await context.bot.edit_message_text(
            "⚠️ Échec de la recherche.",
            chat_id=update.effective_chat.id,
            message_id=wait_msg.message_id
        )
        return

    if not results:
        await context.bot.edit_message_text(
            "❌ Aucune musique trouvée.",
            chat_id=update.effective_chat.id,
            message_id=wait_msg.message_id
        )
        return

    token = uuid.uuid4().hex[:12]
    _sessions[token] = results

    text = "🎵 <b>RÉSULTATS DE RECHERCHE</b>\n━━━━━━━━━━━━━━━\n"
    keyboard = []

    for i, video in enumerate(results):
        text += "{}. {}\n⏱️ {}\n📺 {}\n\n".format(
            i + 1,
            video.get("title", "Sans titre"),
            video.get("duration", "N/A"),
            video.get("channel", "Inconnu")
        )
        keyboard.append(InlineKeyboardButton(str(i + 1), callback_data='sing:{}:{}'.format(token, i)))

    reply_markup = InlineKeyboardMarkup([keyboard])

    await context.bot.delete_message(update.effective_chat.id, wait_msg.message_id)
    await update.message.reply_html(text, reply_markup=reply_markup)


async def sing_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, token, index_str = query.data.split(':')
    index = int(index_str)

    results = _sessions.get(token)
    if not results or index >= len(results):
        await query.answer("❌ Session expirée, relance une recherche.")
        return

    await query.answer()

    selected = results[index]
    await _download_and_send(
        update, context, update.effective_chat.id,
        selected.get("url"), selected.get("duration", "N/A")
    )
