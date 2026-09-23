import os
import asyncio
import logging
from aiohttp import web
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ChatJoinRequestHandler, filters

# Import functions/modules from your two bot files
# Make sure bot (8).py and bot (7).py are renamed or imported correctly as modules
import importlib.util

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

# Load both bot scripts dynamically or import them directly if named standard modules (e.g., bot8 and bot7)
# Let's assume you rename them to bot_story.py and bot_forwarder.py for clean importing:
import bot_story
import bot_forwarder

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

PORT = int(os.environ.get("PORT", 10000))

async def health_check(request):
    return web.Response(text="Both bots are alive and running!", status=200)

async def main():
    # 1. Initialize Bot 1 (Story/Web App Bot)
    token1 = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token1:
        raise ValueError("TELEGRAM_BOT_TOKEN is missing!")
    
    app1 = ApplicationBuilder().token(token1).build()
    app1.add_error_handler(bot_story.global_error_handler)
    
    # Add handlers for Bot 1
    app1.add_handler(CommandHandler("start", bot_story.start_command))
    app1.add_handler(CommandHandler("plan", bot_story.plan_command))
    app1.add_handler(CommandHandler("help", bot_story.help_command))
    app1.add_handler(CommandHandler("cancel", bot_story.cancel_command))
    app1.add_handler(CommandHandler("about", bot_story.about_command))
    app1.add_handler(CommandHandler("language", bot_story.language_command))
    app1.add_handler(CommandHandler("stats", bot_story.stats_command))
    app1.add_handler(CommandHandler("add_channel", bot_story.add_channel_command))
    app1.add_handler(CommandHandler("add_link", bot_story.add_link_command))
    app1.add_handler(CommandHandler("list_channel", bot_story.list_channel_command))
    app1.add_handler(CommandHandler("settings", bot_story.settings_command))
    app1.add_handler(CommandHandler("scan_database", bot_story.scan_database_command))
    app1.add_handler(CommandHandler("backup", bot_story.backup_command))
    app1.add_handler(CommandHandler("broadcast", bot_story.broadcast_command))
    app1.add_handler(CommandHandler("add_user", bot_story.add_user_command))
    app1.add_handler(CommandHandler("list_user", bot_story.list_user_command))
    app1.add_handler(CommandHandler("done", bot_story.done_upload_command))
    
    app1.add_handler(MessageHandler(filters.PHOTO | filters.AUDIO | filters.VIDEO | filters.Document.ALL, bot_story.handle_media_upload))
    app1.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot_story.handle_text_message))
    app1.add_handler(CallbackQueryHandler(bot_story.button_callback))
    app1.add_handler(ChatJoinRequestHandler(bot_story.chat_join_request_handler))

    if app1.job_queue:
        app1.job_queue.run_repeating(bot_story.check_access_job, interval=3600, first=30)

    # 2. Initialize Bot 2 (Forwarder Bot)
    token2 = os.getenv("BOT_TOKEN")
    if not token2:
        raise ValueError("BOT_TOKEN is missing!")

    app2 = ApplicationBuilder().token(token2).build()
    app2.add_handler(CommandHandler("start", bot_forwarder.start))
    app2.add_handler(CallbackQueryHandler(bot_forwarder.button_callback))
    app2.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), bot_forwarder.handle_message))
    app2.add_handler(MessageHandler(filters.ATTACHMENT | filters.FORWARDED, bot_forwarder.handle_message))

    # Resume background tasks for Bot 2 if any
    next_q = bot_forwarder.get_next_quest()
    if next_q and not bot_forwarder.get_active_running_quest():
        bot_forwarder.active_quest_task = asyncio.create_task(bot_forwarder.execute_forwarding_quest(app2, next_q))

    # 3. Setup Shared Web Server (Flask/Aiohttp for Render Port Binding & Web App route)
    # You can run Bot 1's Flask web app routes inside the same aiohttp server or run them concurrently.
    web_app = web.Application()
    web_app.router.add_get("/", health_check)
    web_app.router.add_get("/webapp", lambda req: web.Response(text=bot_story.render_template_string(bot_story.WEB_APP_HTML_TEMPLATE, items=list(bot_story.channels_collection.find({}, {"_id": False}))), content_type="text/html"))
    web_app.router.add_get("/v/{user_id}/{token_10}", lambda req: bot_story.arolinks_redirect(int(req.match_info['user_id']), req.match_info['token_10']))

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Unified web server running on port {PORT}")

    # 4. Start both Telegram bots using asynchronous polling
    await app1.initialize()
    await app2.initialize()

    await app1.start()
    await app2.start()

    await app1.updater.start_polling(drop_pending_updates=True)
    await app2.updater.start_polling(drop_pending_updates=True)

    logger.info("Both Telegram bots are now running concurrently on Render!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
