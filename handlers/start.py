from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

CHANNEL_URL = "https://t.me/lifeCitychannel"
GROUP_URL = "https://t.me/lifecity_anothergirl"
CREATOR_URL = "https://t.me/Christus225"

START_MESSAGE = (
    "Bienvenue sur LifeCity 🏙️✨\n\n"
    "📋 <b>Liste des commandes :</b>\n"
    "/alldl &lt;url&gt; - Télécharger une vidéo (Facebook/TikTok/Instagram/YouTube)\n"
    "/gem &lt;prompt&gt; - Générer ou éditer une image IA\n"
    "/pinterest &lt;recherche&gt; - Rechercher des images sur Pinterest\n"
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📢 Channel City", url=CHANNEL_URL)],
        [InlineKeyboardButton("👥 Groupe", url=GROUP_URL)],
        [InlineKeyboardButton("👤 Créateur", url=CREATOR_URL)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_html(START_MESSAGE, reply_markup=reply_markup)
