import asyncio
import logging
import re
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
    try:
        response = requests.get(
            "{}/ytsearch".format(BASE_URL),
            params={"q": query},
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        return (data.get("results") or [])[:5]
    except requests.exceptions.RequestException as e:
        logger.error('search request error: %s', str(e))
        raise


def _fetch_download_url(youtube_url: str) -> dict:
    try:
        response = requests.get(
            "{}/ytmp3".format(BASE_URL),
            params={"url": youtube_url},
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error('download request error: %s', str(e))
        raise


async def _cleanup_wait_message(context, chat_id, wait_msg):
    """Fonction utilitaire pour nettoyer le message d'attente"""
    if wait_msg:
        try:
            await context.bot.delete_message(chat_id, wait_msg.message_id)
        except Exception:
            pass


async def _download_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, youtube_url: str, duration: str = "N/A"):
    wait_msg = None
    
    try:
        wait_msg = await context.bot.send_message(chat_id, "⏳ Traitement de l'audio...")

        # Tentative de téléchargement
        data = await asyncio.to_thread(_fetch_download_url, youtube_url)

        # Vérification de la réponse
        if not data:
            await _cleanup_wait_message(context, chat_id, wait_msg)
            await context.bot.send_message(
                chat_id,
                "❌ L'API n'a retourné aucune donnée.\n🔄 Réessayez avec un autre lien."
            )
            return

        # Gestion d'erreur détaillée
        if not data.get("success") or not data.get("url"):
            await _cleanup_wait_message(context, chat_id, wait_msg)
            
            # Analyser l'erreur retournée par l'API
            error_msg = data.get("error") or data.get("message") or ""
            error_lower = str(error_msg).lower()

            # Erreur de taille
            if "size" in error_lower or "large" in error_lower or "25" in error_lower or "limit" in error_lower:
                await context.bot.send_message(
                    chat_id,
                    "📦 Cette musique dépasse la limite de 25 Mo de Telegram.\n"
                    "💡 Essayez une version plus courte ou une autre chanson."
                )
                return

            # Vidéo privée ou restreinte
            if "private" in error_lower or "restricted" in error_lower:
                await context.bot.send_message(
                    chat_id,
                    "🔒 Cette vidéo est privée ou restreinte.\n"
                    "🔄 Essayez une autre chanson."
                )
                return

            # Vidéo introuvable
            if "not found" in error_lower or "deleted" in error_lower or "404" in error_lower:
                await context.bot.send_message(
                    chat_id,
                    "❌ Vidéo introuvable ou supprimée.\n"
                    "🔄 Essayez un autre lien ou une autre chanson."
                )
                return

            # Rate limiting
            if "429" in error_lower or "rate" in error_lower or "too many" in error_lower:
                await context.bot.send_message(
                    chat_id,
                    "⏳ Trop de requêtes. Veuillez patienter quelques instants.\n"
                    "🔄 Réessayez dans 30 secondes."
                )
                return

            # Erreur de durée
            if "duration" in error_lower or "long" in error_lower:
                await context.bot.send_message(
                    chat_id,
                    "⏱️ Cette vidéo est trop longue.\n"
                    "💡 Essayez une version plus courte (moins de 10 minutes)."
                )
                return

            # Erreur générique avec détails
            error_display = str(error_msg)[:150] if error_msg else "Erreur inconnue"
            await context.bot.send_message(
                chat_id,
                f"⚠️ Erreur: {error_display}\n"
                "🔄 Réessayez avec un autre lien ou contactez le support."
            )
            return

        # Succès - Téléchargement du fichier
        caption = "🎵 {}\n👤 {}\n⏱️ {}".format(
            data.get("title", "Inconnu"),
            data.get("author", "Inconnu"),
            duration
        )

        await _cleanup_wait_message(context, chat_id, wait_msg)

        # Envoi du fichier audio avec gestion d'erreur
        try:
            await context.bot.send_audio(chat_id, audio=data["url"], caption=caption)
        except Exception as send_error:
            error_str = str(send_error).lower()
            if "file is too large" in error_str or "413" in error_str:
                await context.bot.send_message(
                    chat_id,
                    "📦 Le fichier fait plus de 25 Mo et ne peut pas être envoyé.\n"
                    "💡 Essayez une version plus courte ou de moindre qualité."
                )
            elif "timeout" in error_str:
                await context.bot.send_message(
                    chat_id,
                    "⏰ Le téléchargement a expiré.\n"
                    "🔄 Réessayez avec une connexion plus stable."
                )
            else:
                await context.bot.send_message(
                    chat_id,
                    f"⚠️ Erreur lors de l'envoi: {str(send_error)[:100]}\n"
                    "🔄 Réessayez ou contactez le support."
                )
            return

    except requests.exceptions.Timeout:
        await _cleanup_wait_message(context, chat_id, wait_msg)
        await context.bot.send_message(
            chat_id,
            "⏰ Le serveur met trop de temps à répondre.\n"
            "🔄 Réessayez dans quelques instants.\n"
            "💡 La vidéo est peut-être trop longue."
        )
        
    except requests.exceptions.ConnectionError:
        await _cleanup_wait_message(context, chat_id, wait_msg)
        await context.bot.send_message(
            chat_id,
            "🌐 Problème de connexion au serveur.\n"
            "🔄 Vérifiez votre connexion internet et réessayez."
        )
        
    except requests.exceptions.HTTPError as e:
        await _cleanup_wait_message(context, chat_id, wait_msg)
        status_code = e.response.status_code if e.response else 0
        
        if status_code == 404:
            await context.bot.send_message(
                chat_id,
                "❌ Vidéo introuvable ou supprimée.\n"
                "🔄 Essayez un autre lien."
            )
        elif status_code == 429:
            await context.bot.send_message(
                chat_id,
                "⏳ Trop de requêtes. Veuillez patienter.\n"
                "🔄 Réessayez dans 30 secondes."
            )
        elif status_code == 500:
            await context.bot.send_message(
                chat_id,
                "⚠️ Le serveur rencontre des problèmes techniques.\n"
                "🔄 Réessayez plus tard."
            )
        else:
            await context.bot.send_message(
                chat_id,
                f"⚠️ Erreur HTTP {status_code}.\n"
                "🔄 Réessayez avec un autre lien."
            )
            
    except Exception as e:
        logger.error('sing download error: %s', str(e))
        await _cleanup_wait_message(context, chat_id, wait_msg)
        
        # Analyse détaillée de l'erreur
        error_str = str(e).lower()
        
        if "25" in error_str or "size" in error_str or "large" in error_str:
            await context.bot.send_message(
                chat_id,
                "📦 Fichier trop volumineux (>25 Mo).\n"
                "💡 Cherchez une version plus courte ou utilisez un autre lien."
            )
        elif "timeout" in error_str:
            await context.bot.send_message(
                chat_id,
                "⏰ Délai d'attente dépassé.\n"
                "🔄 Réessayez avec une connexion plus stable."
            )
        elif "404" in error_str or "not found" in error_str:
            await context.bot.send_message(
                chat_id,
                "❌ Vidéo introuvable ou supprimée.\n"
                "🔄 Essayez un autre lien."
            )
        elif "badrequest" in error_str or "not subscriptable" in error_str:
            # Gestion spécifique de l'erreur BadRequest
            await context.bot.send_message(
                chat_id,
                "⚠️ Erreur de communication avec l'API.\n"
                "🔄 Réessayez dans quelques instants.\n"
                "💡 Si le problème persiste, essayez un autre lien."
            )
        else:
            # Message d'erreur générique mais informatif
            error_detail = str(e)[:150]
            await context.bot.send_message(
                chat_id,
                f"⚠️ Une erreur est survenue: {error_detail}\n"
                "🔄 Réessayez ou contactez le support si le problème persiste."
            )


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
            "❌ Merci de fournir un nom de musique ou un lien YouTube.\n"
            "Exemple : /sing Blinding Lights"
        )
        return

    wait_msg = await update.message.reply_text("🔍 Recherche en cours...")

    try:
        results = await asyncio.to_thread(_search_songs, query)
    except requests.exceptions.Timeout:
        await context.bot.edit_message_text(
            "⏰ Le serveur ne répond pas. Réessayez dans quelques instants.",
            chat_id=update.effective_chat.id,
            message_id=wait_msg.message_id
        )
        return
    except requests.exceptions.ConnectionError:
        await context.bot.edit_message_text(
            "🌐 Problème de connexion au serveur.",
            chat_id=update.effective_chat.id,
            message_id=wait_msg.message_id
        )
        return
    except Exception as e:
        logger.error('sing search error: %s', str(e))
        await context.bot.edit_message_text(
            f"⚠️ Échec de la recherche: {str(e)[:100]}",
            chat_id=update.effective_chat.id,
            message_id=wait_msg.message_id
        )
        return

    if not results:
        await context.bot.edit_message_text(
            "❌ Aucune musique trouvée pour cette recherche.",
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

    # boutons groupes sur une seule ligne
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
