import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from handlers.start import start_command
from handlers.alldl import alldl_command
from handlers.gem import gem_command
from handlers.pinterest import pinterest_command, pinterest_next_callback
from handlers.lifeai import lifeai_command, lifeai_reply_handler
from handlers.lyrics import lyrics_command
from handlers.sing import sing_command, sing_callback
from handlers.youtube import youtube_command, youtube_callback

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8881559887:AAFTu4O8dsdBn1Ov1KbKi8SJbrdDRxciN8k"


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')

    def log_message(self, format, *args):
        pass


def run_health_check_server():
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()


def main():
    threading.Thread(target=run_health_check_server, daemon=True).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler(['lifeai', 'ia'], lifeai_command))
    app.add_handler(CommandHandler(['alldl', 'dl'], alldl_command))
    app.add_handler(CommandHandler('gem', gem_command))
    app.add_handler(CommandHandler(['pinterest', 'pin'], pinterest_command))
    app.add_handler(CommandHandler(['lyrics', 'songlyrics'], lyrics_command))
    app.add_handler(CallbackQueryHandler(pinterest_next_callback, pattern=r'^pin_next:'))
    app.add_handler(CommandHandler(['sing', 'music'], sing_command))
    app.add_handler(CallbackQueryHandler(sing_callback, pattern=r'^sing:'))
    app.add_handler(CommandHandler(['youtube', 'ytb'], youtube_command))
    app.add_handler(CallbackQueryHandler(youtube_callback, pattern=r'^ytb:'))
    app.add_handler(MessageHandler(filters.TEXT & filters.REPLY & ~filters.COMMAND, lifeai_reply_handler))
    
    logger.info('Bot demarre, polling en cours...')
    app.run_polling(allowed_updates=['message', 'callback_query'])


if __name__ == '__main__':
    main()
