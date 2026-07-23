import asyncio
import logging
import re

import requests
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

API_ENDPOINT = "https://azadx69x-all-apis-top.vercel.app/api/ai"

MAX_HISTORY_MESSAGES = 12
MAX_TRACKED_MESSAGES = 2000

_conversations = {}
_lifeai_message_ids = {}

BOLD_MAP = {
    'a': '𝗮', 'b': '𝗯', 'c': '𝗰', 'd': '𝗱', 'e': '𝗲', 'f': '𝗳', 'g': '𝗴', 'h': '𝗵', 'i': '𝗶',
    'j': '𝗷', 'k': '𝗸', 'l': '𝗹', 'm': '𝗺', 'n': '𝗻', 'o': '𝗼', 'p': '𝗽', 'q': '𝗾', 'r': '𝗿',
    's': '𝘀', 't': '𝘁', 'u': '𝘂', 'v': '𝘃', 'w': '𝘄', 'x': '𝘅', 'y': '𝘆', 'z': '𝘇',
    'A': '𝗔', 'B': '𝗕', 'C': '𝗖', 'D': '𝗗', 'E': '𝗘', 'F': '𝗙', 'G': '𝗚', 'H': '𝗛', 'I': '𝗜',
    'J': '𝗝', 'K': '𝗞', 'L': '𝗟', 'M': '𝗠', 'N': '𝗡', 'O': '𝗢', 'P': '𝗣', 'Q': '𝗤', 'R': '𝗥',
    'S': '𝗦', 'T': '𝗧', 'U': '𝗨', 'V': '𝗩', 'W': '𝗪', 'X': '𝗫', 'Y': '𝗬', 'Z': '𝗭',
}

IDENTITY_REPLACEMENTS = [
    (r'copilot', 'LifeIA'),
    (r'microsoft', 'Christus'),
    (r'openai', 'Christus'),
    (r'chatgpt', 'LifeIA'),
    (r'assistant informatique', 'LifeIA, un assistant virtuel créé par Christus'),
    (r"je suis un assistant", "Je suis LifeIA, un assistant virtuel créé par Christus"),
    (r"je suis une intelligence artificielle", "Je suis LifeIA, une IA créée par Christus"),
]

CREATOR_INFO = "\n\n👨‍💻 Créé par @Christus225"

def _to_bold_unicode(text: str) -> str:
    return ''.join(BOLD_MAP.get(ch, ch) for ch in text)

def _normalize_identity(text: str) -> str:
    if not text:
        return text
    for pattern, replacement in IDENTITY_REPLACEMENTS:
        text = re.sub(pattern, replacement, text, flags=re.I)
    return text

def _format_response(text: str) -> str:
    if not text:
        return text
    text = _normalize_identity(text)
    text = re.sub(r'\*\*(.+?)\*\*', lambda m: _to_bold_unicode(m.group(1)), text)
    text = re.sub(r'#+\s*', '', text)
    text = text.replace('*', '')
    
    if "@Christus225" not in text:
        text = text.strip() + CREATOR_INFO
    
    return text.strip()

def _get_history(user_id: int):
    return _conversations.setdefault(user_id, [])

def _reset_history(user_id: int):
    _conversations[user_id] = []

def _track_message(message_id: int, user_id: int):
    if len(_lifeai_message_ids) >= MAX_TRACKED_MESSAGES:
        oldest_key = next(iter(_lifeai_message_ids))
        _lifeai_message_ids.pop(oldest_key, None)
    _lifeai_message_ids[message_id] = user_id

def is_lifeai_reply(update: Update) -> bool:
    replied = update.message.reply_to_message if update.message else None
    return bool(replied and replied.message_id in _lifeai_message_ids)

def _build_prompt(user_id: int, new_message: str) -> str:
    return new_message

def _call_api(prompt: str, user_id: int = None) -> str:
    params = {"query": prompt}
    if user_id:
        params["session"] = str(user_id)
    
    try:
        response = requests.get(
            API_ENDPOINT,
            params=params,
            timeout=45
        )
        response.raise_for_status()
        data = response.json()
        
        if not data.get("status"):
            raise RuntimeError("l'API a renvoyé une erreur")
        
        return data.get("response", "").strip()
    except requests.exceptions.Timeout:
        raise RuntimeError("L'API a mis trop de temps à répondre")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Erreur réseau: {str(e)}")

async def _process_message(update: Update, context: ContextTypes.DEFAULT_TYPE, user_message: str):
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)

    user_id = update.effective_user.id
    prompt = _build_prompt(user_id, user_message)

    try:
        raw_answer = await asyncio.to_thread(_call_api, prompt, user_id)
    except Exception as e:
        logger.error('lifeai error: %s', str(e))
        await update.message.reply_text("❌ Une erreur est survenue en contactant LifeIA, réessaie plus tard.")
        return

    answer = _format_response(raw_answer)

    history = _get_history(user_id)
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": raw_answer})
    _conversations[user_id] = history[-MAX_HISTORY_MESSAGES:]

    sent_message = await update.message.reply_text(answer)
    _track_message(sent_message.message_id, user_id)

async def lifeai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = ' '.join(context.args).strip()

    if user_message.lower() in ('reset', 'clear'):
        _reset_history(user_id)
        await update.message.reply_text('♻️ Conversation réinitialisée.')
        return

    if not user_message:
        await update.message.reply_text(
            "💬 LifeIA - Assistant Virtuel\n\n"
            "Utilisation :\n"
            "/lifeai ta question\n"
            "/lifeai reset pour effacer l'historique\n\n"
            "✨ Astuce : Réponds directement à un message de LifeIA pour continuer "
            "la conversation sans retaper la commande.\n\n"
            "👨‍💻 Créé par @Christus225"
        )
        return

    await _process_message(update, context, user_message)

async def lifeai_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_lifeai_reply(update):
        return

    user_message = (update.message.text or '').strip()
    if not user_message:
        return

    await _process_message(update, context, user_message)
