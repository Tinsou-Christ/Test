import asyncio
import logging
import os
import re
import tempfile

import requests
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

API_BASE = "https://azadx69x-alldl-cdi-bai.vercel.app/alldl"
SUPPORTED_DOMAINS = ["facebook", "fb.watch", "tiktok", "instagram", "youtu", "youtube"]


def extract_url(text):
    if not text:
        return None
    match = re.search(r'(https?://[^\s]+)', text)
    return match.group(1) if match else None


def _download_video(url: str) -> str:
    api_url = "{}?url={}&quality=sd".format(API_BASE, requests.utils.quote(url, safe=''))
    response = requests.get(api_url, stream=True, timeout=60)
    response.raise_for_status()

    fd, tmp_path = tempfile.mkstemp(suffix='.mp4')
    with os.fdopen(fd, 'wb') as f:
        for chunk in response.iter_content(chunk_size=1024 * 64):
            f.write(chunk)

    return tmp_path


async def alldl_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.UPLOAD_VIDEO)

    url = None
    if context.args:
        url = context.args[0]
    if not url and update.message.reply_to_message:
        url = extract_url(update.message.reply_to_message.text)
    if not url:
        url = extract_url(update.message.text)

    if not url:
        await update.message.reply_text(
            "❌ Aucune URL trouvée !\nExemple : /alldl <url>\nOu réponds à un message contenant un lien supporté."
        )
        return

    if not any(domain in url for domain in SUPPORTED_DOMAINS):
        await update.message.reply_text("❌ URL non supportée ! (Facebook, TikTok, Instagram, YouTube uniquement)")
        return

    wait_msg = await update.message.reply_text("📥 Téléchargement de la vidéo...\nMerci de patienter...")

    tmp_path = None
    try:
        tmp_path = await asyncio.to_thread(_download_video, url)

        await context.bot.delete_message(update.effective_chat.id, wait_msg.message_id)

        with open(tmp_path, 'rb') as f:
            await update.message.reply_video(f, caption="✅ Téléchargement terminé !")

    except Exception as e:
        logger.error('alldl error: %s', str(e))
        await context.bot.edit_message_text(
            "❌ Échec du téléchargement.\n📝 {}".format(str(e)),
            chat_id=update.effective_chat.id,
            message_id=wait_msg.message_id
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
