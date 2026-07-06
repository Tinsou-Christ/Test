import logging
import os

from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler

from handlers.start import start_command
from handlers.alldl import alldl_command
from handlers.gem import gem_command
from handlers.pinterest import pinterest_command, pinterest_next_callback

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')


def main():
    if not BOT_TOKEN:
        raise RuntimeError('La variable d\'environnement BOT_TOKEN n\'est pas definie')

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler(['alldl', 'dl'], alldl_command))
    app.add_handler(CommandHandler('gem', gem_command))
    app.add_handler(CommandHandler(['pinterest', 'pin'], pinterest_command))
    app.add_handler(CallbackQueryHandler(pinterest_next_callback, pattern=r'^pin_next:'))

    logger.info('Bot demarre, polling en cours...')
    app.run_polling(allowed_updates=['message', 'callback_query'])


if __name__ == '__main__':
    main()
  
