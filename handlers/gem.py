import asyncio
import base64
import logging
import os
import tempfile

import requests
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

GENERATE_ENDPOINT = "https://gem-tw6a.onrender.com/generate"
EDIT_ENDPOINT = "https://gem-tw6a.onrender.com/edit"


def _parse_args(args):
    ratio = "1:1"
    artistic_mode = False
    prompt_parts = []

    i = 0
    while i < len(args):
        if args[i] == '--r' and i + 1 < len(args):
            ratio = args[i + 1]
            i += 2
            continue
        elif args[i] == '--nw':
            artistic_mode = True
            i += 1
            continue
        else:
            prompt_parts.append(args[i])
            i += 1

    return ' '.join(prompt_parts).strip(), ratio, artistic_mode


def _generate_image(payload: dict, endpoint: str) -> str:
    response = requests.post(endpoint, json=payload, timeout=180)
    response.raise_for_status()

    fd, tmp_path = tempfile.mkstemp(suffix='.jpg')
    with os.fdopen(fd, 'wb') as f:
        f.write(response.content)

    return tmp_path


def _fetch_image_base64(file_url: str) -> str:
    img_bytes = requests.get(file_url, timeout=30).content
    return base64.b64encode(img_bytes).decode('utf-8')


async def gem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.UPLOAD_PHOTO)

    if not context.args:
        await update.message.reply_text("⚠️ Merci de fournir un prompt.\nExemple : /gem anime girl --r 9:16")
        return

    user_prompt, ratio, artistic_mode = _parse_args(context.args)

    if not user_prompt:
        await update.message.reply_text("⚠️ Merci de fournir un prompt.")
        return

    final_prompt = user_prompt
    if artistic_mode:
        final_prompt = (
            "Sophisticated fine art photography, classical figure study, "
            "artistic lighting, gallery quality: {}".format(user_prompt)
        )

    wait_msg = await update.message.reply_text("🎨 Génération de ton chef-d'œuvre...\nMerci de patienter...")

    endpoint = GENERATE_ENDPOINT
    payload = {"prompt": final_prompt, "ratio": ratio, "format": "jpg"}

    replied = update.message.reply_to_message
    if replied and replied.photo:
        try:
            file = await context.bot.get_file(replied.photo[-1].file_id)
            img_b64 = await asyncio.to_thread(_fetch_image_base64, file.file_path)
            payload = {"prompt": final_prompt, "format": "jpg", "image": img_b64}
            endpoint = EDIT_ENDPOINT
        except Exception as e:
            logger.error('failed to fetch replied photo: %s', str(e))

    tmp_path = None
    try:
        tmp_path = await asyncio.to_thread(_generate_image, payload, endpoint)

        await context.bot.delete_message(update.effective_chat.id, wait_msg.message_id)

        caption = "✅ Chef-d'œuvre créé !\n\n📝 Prompt : {}\n📐 Ratio : {}".format(user_prompt, ratio)
        if artistic_mode:
            caption += "\n✨ Mode artistique activé"

        with open(tmp_path, 'rb') as f:
            await update.message.reply_photo(f, caption=caption)

    except Exception as e:
        logger.error('gem error: %s', str(e))
        await context.bot.edit_message_text(
            "❌ Échec de la génération de l'image.\n📝 {}".format(str(e)),
            chat_id=update.effective_chat.id,
            message_id=wait_msg.message_id
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
