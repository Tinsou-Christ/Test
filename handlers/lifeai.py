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

LOWERCASE_MAP = {
    'a': '𝖺', 'b': '𝖻', 'c': '𝖼', 'd': '𝖽', 'e': '𝖾', 'f': '𝖿', 'g': '𝗀', 'h': '𝗁', 'i': '𝗂',
    'j': '𝗃', 'k': '𝗄', 'l': '𝗅', 'm': '𝗆', 'n': '𝗇', 'o': '𝗈', 'p': '𝗉', 'q': '𝗊', 'r': '𝗋',
    's': '𝗌', 't': '𝗍', 'u': '𝗎', 'v': '𝗏', 'w': '𝗐', 'x': '𝗑', 'y': '𝗒', 'z': '𝗓'
}

UPPERCASE_MAP = {
    'A': '𝗔', 'B': '𝗕', 'C': '𝗖', 'D': '𝗗', 'E': '𝗘', 'F': '𝗙', 'G': '𝗚', 'H': '𝗛', 'I': '𝗜',
    'J': '𝗝', 'K': '𝗞', 'L': '𝗟', 'M': '𝗠', 'N': '𝗡', 'O': '𝗢', 'P': '𝗣', 'Q': '𝗤', 'R': '𝗥',
    'S': '𝗦', 'T': '𝗧', 'U': '𝗨', 'V': '𝗩', 'W': '𝗪', 'X': '𝗫', 'Y': '𝗬', 'Z': '𝗭'
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

def _to_styled_text(text: str) -> str:
    result = []
    for ch in text:
        if ch in LOWERCASE_MAP:
            result.append(LOWERCASE_MAP[ch])
        elif ch in UPPERCASE_MAP:
            result.append(UPPERCASE_MAP[ch])
        else:
            result.append(ch)
    return ''.join(result)

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
    text = re.sub(r'\*\*(.+?)\*\*', lambda m: _to_styled_text(m.group(1)), text)
    text = re.sub(r'#+\s*', '', text)
    text = text.replace('*', '')
    text = _to_styled_text(text)
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
        await update.message.reply_text("❌ 𝖴𝗇𝖾 𝖾𝗋𝗋𝖾𝗎𝗋 𝖾𝗌𝗍 𝗌𝗎𝗋𝗏𝖾𝗇𝗎𝖾 𝖾𝗇 𝖼𝗈𝗇𝗍𝖺𝖼𝗍𝖺𝗇𝗍 𝖫𝗂𝖿𝖾𝖨𝖠, 𝗋é𝖾𝗌𝗌𝖺𝗂𝖾 𝗉𝗅𝗎𝗌 𝗍𝖺𝗋𝖽.")
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
        await update.message.reply_text('♻️ 𝖢𝗈𝗇𝗏𝖾𝗋𝗌𝖺𝗍𝗂𝗈𝗇 ré𝗂𝗇𝗂𝗍𝗂𝖺𝗅𝗂𝗌é𝖾.')
        return

    if not user_message:
        await update.message.reply_text(
            "💬 𝖫𝗂𝖿𝖾𝖨𝖠 - 𝖠𝗌𝗌𝗂𝗌𝗍𝖺𝗇𝗍 𝖵𝗂𝗋𝗍𝗎𝖾𝗅\n\n"
            "𝖴𝗍𝗂𝗅𝗂𝗌𝖺𝗍𝗂𝗈𝗇 :\n"
            "/lifeai 𝗍𝖺 𝗊𝗎𝖾𝗌𝗍𝗂𝗈𝗇\n"
            "/lifeai 𝗋𝖾𝗌𝖾𝗍 𝗉𝗈𝗎𝗋 𝖾𝖿𝖿𝖺𝖼𝖾𝗋 l'𝗁𝗂𝗌𝗍𝗈𝗋𝗂𝗊𝗎𝖾\n\n"
            "✨ 𝖠𝗌𝗍𝗎𝖼𝖾 : Ré𝗉𝗈𝗇𝖽𝗌 𝖽𝗂𝗋𝖾𝖼𝗍𝖾𝗆𝖾𝗇𝗍 à 𝗎𝗇 𝗆𝖾𝗌𝗌𝖺𝗀𝖾 𝖽𝖾 𝖫𝗂𝖿𝖾𝖨𝖠 𝗉𝗈𝗎𝗋 𝖼𝗈𝗇𝗍𝗂𝗇𝗎𝖾𝗋 "
            "𝗅𝖺 𝖼𝗈𝗇𝗏𝖾𝗋𝗌𝖺𝗍𝗂𝗈𝗇 𝗌𝖺𝗇𝗌 𝗋𝖾𝗍𝖺𝗉𝖾𝗋 𝗅𝖺 𝖼𝗈𝗆𝗆𝖺𝗇𝖽𝖾."
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
