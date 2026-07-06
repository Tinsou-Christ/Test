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

YT_REGEX = re.compile(r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/[^\s]+', re.I)

# sessions de recherche en memoire (token -> {results, mode}), perdues au redemarrage du bot
_sessions = {}


def _search_videos(query: str):
    response = requests.get(
        "{}/ytsearch".format(BASE_URL),
        params={"q": query},
        timeout=30
    )
    response.raise_for_status()
    data = response.json()
    if not data.get("status") or not data.get("results"):
        return []
    return data["results"][:10]


def _fetch_media_data(youtube_url: str) -> dict:
    response = requests.get(
        "{}/ytdlv2".format(BASE_URL),
        params={"url": youtube_url},
        timeout=90
    )
    response.raise_for_status()
    return response.json()


def _download_file_to_tempfile(url: str, extension: str) -> str:
    response = requests.get(url, stream=True, timeout=120)
    response.raise_for_status()

    fd, tmp_path = tempfile.mkstemp(suffix='.{}'.format(extension))
    with os.fdopen(fd, 'wb') as f:
        for chunk in response.iter_content(chunk_size=1024 * 64):
            f.write(chunk)

    return tmp_path


async def _download_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, youtube_url: str, mode: str = "video"):
    action = ChatAction.UPLOAD_VIDEO if mode == "video" else ChatAction.UPLOAD_VOICE
    await context.bot.send_chat_action(chat_id, action)

    wait_msg = await context.bot.send_message(chat_id, "⏳ Téléchargement en cours...")

    tmp_path = None
    try:
        data = await asyncio.to_thread(_fetch_media_data, youtube_url)

        if not data.get("success"):
            await context.bot.delete_message(chat_id, wait_msg.message_id)
            await context.bot.send_message(chat_id, "❌ Échec du téléchargement.")
            return

        media_url = data.get("audio_url") if mode == "audio" else data.get("video_url")
        extension = "mp3" if mode == "audio" else "mp4"

        if not media_url:
            await context.bot.delete_message(chat_id, wait_msg.message_id)
            await context.bot.send_message(chat_id, "❌ Aucun lien de média renvoyé par l'API.")
            return

        tmp_path = await asyncio.to_thread(_download_file_to_tempfile, media_url, extension)

        caption = "🎵 {}\n📦 {}".format(data.get("title", "Inconnu"), mode.upper())

        await context.bot.delete_message(chat_id, wait_msg.message_id)

        with open(tmp_path, 'rb') as f:
            if mode == "audio":
                await context.bot.send_audio(chat_id, audio=f, caption=caption)
            else:
                await context.bot.send_video(chat_id, video=f, caption=caption)

    except Exception as e:
        logger.error('youtube download error: %s', str(e), exc_info=True)
        try:
            await context.bot.delete_message(chat_id, wait_msg.message_id)
        except Exception:
            pass
        await context.bot.send_message(chat_id, "⚠️ Erreur : {}".format(str(e)[:300]))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


async def youtube_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text(
            "╭──〔 YOUTUBE DOWNLOADER 〕──╮\n"
            "│\n"
            "├─ 🎥 /youtube -v believer\n"
            "├─ 🎵 /youtube -a believer\n"
            "├─ 🔗 /youtube <lien youtube>\n"
            "│\n"
            "╰──────────────────╯"
        )
        return

    input_text = ' '.join(context.args)

    # lien youtube direct -> telechargement video par defaut
    if YT_REGEX.search(input_text):
        await _download_and_send(update, context, chat_id, input_text.strip(), "video")
        return

    mode = "video"
    args = context.args
    if args[0] == '-a':
        mode = "audio"
        query = ' '.join(args[1:]).strip()
    elif args[0] == '-v':
        query = ' '.join(args[1:]).strip()
    else:
        query = input_text.strip()

    if not query:
        await update.message.reply_text("❌ Merci d'indiquer une recherche.")
        return

    await context.bot.send_chat_action(chat_id, ChatAction.TYPING)
    wait_msg = await update.message.reply_text("🔍 Recherche en cours...")

    try:
        results = await asyncio.to_thread(_search_videos, query)
    except Exception as e:
        logger.error('youtube search error: %s', str(e))
        await context.bot.edit_message_text(
            "❌ Échec de la recherche.",
            chat_id=chat_id,
            message_id=wait_msg.message_id
        )
        return

    if not results:
        await context.bot.edit_message_text(
            "❌ Aucun résultat trouvé.",
            chat_id=chat_id,
            message_id=wait_msg.message_id
        )
        return

    token = uuid.uuid4().hex[:12]
    _sessions[token] = {"results": results, "mode": mode}

    text = "╭──〔 RÉSULTATS 〕──╮\n│ 🔎 Recherche : {}\n│ 📦 Mode : {}\n╰──────────────────╯\n\n".format(
        query, mode.upper()
    )

    keyboard_row = []
    for i, video in enumerate(results):
        text += "{}. {}\n⏱ {}\n📺 {}\n\n".format(
            i + 1,
            video.get("title", "Sans titre"),
            video.get("duration", "N/A"),
            video.get("channel", "Inconnu")
        )
        keyboard_row.append(InlineKeyboardButton(str(i + 1), callback_data='ytb:{}:{}'.format(token, i)))

    # 5 boutons par ligne pour ne pas depasser la largeur de l'ecran
    keyboard = [keyboard_row[i:i + 5] for i in range(0, len(keyboard_row), 5)]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.delete_message(chat_id, wait_msg.message_id)
    await update.message.reply_text(text, reply_markup=reply_markup)


async def youtube_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, token, index_str = query.data.split(':')
    index = int(index_str)

    session = _sessions.get(token)
    if not session or index >= len(session["results"]):
        await query.answer("❌ Session expirée, relance une recherche.")
        return

    await query.answer()

    selected = session["results"][index]
    await _download_and_send(
        update, context, update.effective_chat.id,
        selected.get("url"), session["mode"]
  )
