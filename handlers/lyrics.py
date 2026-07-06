import asyncio
import logging

import requests
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

API_ENDPOINT = "https://xalman-apis.vercel.app/api/lyrics"
MAX_MESSAGE_LENGTH = 4000  # marge de securite sous la limite Telegram (4096)


def _fetch_lyrics(song_name: str) -> dict:
    response = requests.get(API_ENDPOINT, params={"song": song_name}, timeout=30)
    response.raise_for_status()
    return response.json()


async def lyrics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)

    song_name = ' '.join(context.args).strip()

    if not song_name:
        await update.message.reply_text(
            "╭─❍\n│ Merci de fournir un nom de chanson !\n╰───────────⟡"
        )
        return

    wait_msg = await update.message.reply_text('🔍 | Recherche des paroles pour : {}...'.format(song_name))

    try:
        data = await asyncio.to_thread(_fetch_lyrics, song_name)

        if not data.get('status') or not data.get('data'):
            raise ValueError('lyrics not found')

        title = data['data'].get('title', 'Inconnu')
        artist = data['data'].get('artist', 'Inconnu')
        lyrics = data['data'].get('lyrics', '')

        response_text = (
            "╭───────❍\n"
            "│  『 𝗦𝗢𝗡𝗚 𝗟𝗬𝗥𝗜𝗖𝗦 』\n"
            "╰───────────⟡\n"
            "🎵 𝗧𝗶𝘁𝗹𝗲  : {}\n"
            "👤 𝗔𝗿𝘁𝗶𝘀𝘁 : {}\n\n"
            "📜 𝗟𝘆𝗿𝗶𝗰𝘀 :\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "{}\n"
            "━━━━━━━━━━━━━━━━━━"
        ).format(title, artist, lyrics)

        if len(response_text) <= MAX_MESSAGE_LENGTH:
            await context.bot.edit_message_text(
                response_text,
                chat_id=update.effective_chat.id,
                message_id=wait_msg.message_id
            )
        else:
            # message trop long pour Telegram, on coupe et on envoie le reste a la suite
            await context.bot.edit_message_text(
                response_text[:MAX_MESSAGE_LENGTH],
                chat_id=update.effective_chat.id,
                message_id=wait_msg.message_id
            )
            remaining = response_text[MAX_MESSAGE_LENGTH:]
            for i in range(0, len(remaining), MAX_MESSAGE_LENGTH):
                await update.message.reply_text(remaining[i:i + MAX_MESSAGE_LENGTH])

    except Exception as e:
        logger.error('lyrics error: %s', str(e))
        await context.bot.edit_message_text(
            '✕ Paroles introuvables pour "{}" !'.format(song_name),
            chat_id=update.effective_chat.id,
            message_id=wait_msg.message_id
            )
