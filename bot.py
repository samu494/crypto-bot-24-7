import os
import asyncio
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from crypto_fetcher import (
    fetch_all_news,
    fetch_whale_news,
    fetch_economy_news,
    fetch_trump_crypto,
    fetch_new_coins,
    fetch_top_gainers,
    fetch_trending,
    format_news,
    format_news_with_images,
    format_whale_news,
    format_economy_news,
    format_trump_news,
    format_verify,
    format_new_coins,
    format_top_gainers,
    format_trending,
    format_airdrops,
    format_promising,
    format_daily_summary,
)

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running!")

    def log_message(self, format, *args):
        pass


def start_health_server(port=8000):
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Health server started on port {port}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "*Crypto Bot Complet!*\n\n"
        "\U0001f514 News auto + Whales + Economie + Trump + Verification\n\n"
        "*Commandes:*\n\n"
        "/news - \U0001f4f0 News crypto temps reel avec resume detaille\n"
        "/whales - \U0001f40b News des gros detenteurs (whales)\n"
        "/economy - \U0001f3e2 Economie crypto (regulations, adoptions, bans)\n"
        "/trump - \U0001f1fa\U0001f1f8 Annonces Trump + crypto\n"
        "/verify - \U0001f50d Verifier si une news est vraie ou fausse\n"
        "/newcoins - \U0001f195 Nouvelles cryptomonnaies\n"
        "/gainers - \U0001f4c8 Top gainers 24h\n"
        "/trending - \U0001f525 Crypto en tendance\n"
        "/airdrops - \U0001f381 Airdrops serieux avec liens\n"
        "/promising - \U0001f680 Projets prometteurs avec liens\n"
        "/summary - \U0001f4ca Resume complet\n\n"
        "*Fonctionnalites:*\n"
        "\u2022 Chaque news a un resume detaille en francais\n"
        "\u2022 Analyse de fiabilite (VRAI / FAUX / A VERIFIER)\n"
        "\u2022 Images explicatives quand disponibles\n"
        "\u2022 9 sources: Bloomberg, Reuters, CoinDesk, CoinTelegraph...\n\n"
        "_Alertes auto: News 15min | Whales 10min | Economy 15min | Trump 10min_"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")


async def cmd_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("\U0001f50d Recherche des news crypto...")
    news = await fetch_all_news(10)
    img_url, msg = format_news_with_images(news)
    if img_url:
        try:
            await update.message.reply_photo(photo=img_url, caption=msg, parse_mode="Markdown")
            return
        except Exception:
            pass
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_whales(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("\U0001f40b Recherche des news whales...")
    news = await fetch_whale_news(10)
    img_url, msg = format_whale_news(news)
    if img_url:
        try:
            await update.message.reply_photo(photo=img_url, caption=msg, parse_mode="Markdown")
            return
        except Exception:
            pass
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_economy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("\U0001f3e2 Recherche de l'economie crypto...")
    news = await fetch_economy_news(10)
    img_url, msg = format_economy_news(news)
    if img_url:
        try:
            await update.message.reply_photo(photo=img_url, caption=msg, parse_mode="Markdown")
            return
        except Exception:
            pass
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_trump(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("\U0001f1fa\U0001f1f8 Recherche des annonces Trump crypto...")
    news = await fetch_trump_crypto(10)
    img_url, msg = format_trump_news(news)
    if img_url:
        try:
            await update.message.reply_photo(photo=img_url, caption=msg, parse_mode="Markdown")
            return
        except Exception:
            pass
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        msg = (
            "*\U0001f50d Verifier une news:*\n\n"
            "Utilise: `/verify Titre de la news a verifier`\n\n"
            "Exemple:\n"
            "/verify Bitcoin atteint 100k USD\n\n"
            "_Le bot analysera la fiabilite de l'information._"
        )
    else:
        title = parts[1]
        msg = format_verify(title, "", "")
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_newcoins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("\U0001f50d Recherche des nouvelles cryptomonnaies...")
    coins = await fetch_new_coins(10)
    msg = format_new_coins(coins)
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_gainers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("\U0001f4c8 Chargement des top gainers...")
    coins = await fetch_top_gainers(10)
    msg = format_top_gainers(coins)
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("\U0001f525 Recherche des trending...")
    coins = await fetch_trending()
    msg = format_trending(coins)
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_airdrops(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = format_airdrops()
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_promising(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = format_promising()
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = format_daily_summary()
    await update.message.reply_text(msg, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if any(w in text for w in ["whale", "whales", "gros", "baleine"]):
        news = await fetch_whale_news(10)
        img_url, msg = format_whale_news(news)
        if img_url:
            try:
                await update.message.reply_photo(photo=img_url, caption=msg, parse_mode="Markdown")
                return
            except Exception:
                pass
        await update.message.reply_text(msg, parse_mode="Markdown")
    elif any(w in text for w in ["economie", "economy", "regulation", "ban", "adoption", "sec", "etf"]):
        news = await fetch_economy_news(10)
        img_url, msg = format_economy_news(news)
        if img_url:
            try:
                await update.message.reply_photo(photo=img_url, caption=msg, parse_mode="Markdown")
                return
            except Exception:
                pass
        await update.message.reply_text(msg, parse_mode="Markdown")
    elif any(w in text for w in ["trump", "donald", "president usa", "white house"]):
        news = await fetch_trump_crypto(10)
        img_url, msg = format_trump_news(news)
        if img_url:
            try:
                await update.message.reply_photo(photo=img_url, caption=msg, parse_mode="Markdown")
                return
            except Exception:
                pass
        await update.message.reply_text(msg, parse_mode="Markdown")
    elif any(w in text for w in ["verify", "verifier", "fake", "faux", "vrai", "true", "scam"]):
        title = text
        for prefix in ["verify", "verifier", "is this real", "is it fake", "scam"]:
            title = title.replace(prefix, "").strip()
        msg = format_verify(title, "", "")
        await update.message.reply_text(msg, parse_mode="Markdown")
    elif any(w in text for w in ["news", "info", "actualit", "nouvelle"]):
        news = await fetch_all_news(10)
        img_url, msg = format_news_with_images(news)
        if img_url:
            try:
                await update.message.reply_photo(photo=img_url, caption=msg, parse_mode="Markdown")
                return
            except Exception:
                pass
        await update.message.reply_text(msg, parse_mode="Markdown")
    elif any(w in text for w in ["airdrop", "air drops", "gratuit"]):
        msg = format_airdrops()
        await update.message.reply_text(msg, parse_mode="Markdown")
    elif any(w in text for w in ["prometteur", "projet", "project"]):
        msg = format_promising()
        await update.message.reply_text(msg, parse_mode="Markdown")
    elif any(w in text for w in ["nouveau", "new coin", "latest"]):
        coins = await fetch_new_coins(10)
        msg = format_new_coins(coins)
        await update.message.reply_text(msg, parse_mode="Markdown")
    elif any(w in text for w in ["tendance", "trending", "popular"]):
        coins = await fetch_trending()
        msg = format_trending(coins)
        await update.message.reply_text(msg, parse_mode="Markdown")
    elif any(w in text for w in ["gagner", "gain", "hausse", "pump"]):
        coins = await fetch_top_gainers(10)
        msg = format_top_gainers(coins)
        await update.message.reply_text(msg, parse_mode="Markdown")
    else:
        msg = (
            "*Commandes:*\n\n"
            "/news - \U0001f4f0 News crypto\n"
            "/whales - \U0001f40b News whales\n"
            "/economy - \U0001f3e2 Economie crypto\n"
            "/trump - \U0001f1fa\U0001f1f8 Annonces Trump crypto\n"
            "/verify - \U0001f50d Verifier une news\n"
            "/newcoins - \U0001f195 Nouvelles cryptos\n"
            "/gainers - \U0001f4c8 Top gainers\n"
            "/trending - \U0001f525 Tendances\n"
            "/airdrops - \U0001f381 Airdrops\n"
            "/promising - \U0001f680 Projets prometteurs\n"
            "/summary - \U0001f4ca Resume"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")


async def auto_news_check(app):
    if not CHAT_ID:
        return
    try:
        news = await fetch_all_news(8)
        if news:
            img_url, msg = format_news_with_images(news)
            if img_url:
                try:
                    await app.bot.send_photo(chat_id=int(CHAT_ID), photo=img_url, caption=msg, parse_mode="Markdown")
                    logger.info(f"Auto-news avec image envoyee: {len(news)} articles.")
                    return
                except Exception:
                    pass
            msg = "*\U0001f514 Alerte News Crypto!*\n\n" + msg
            await app.bot.send_message(chat_id=int(CHAT_ID), text=msg, parse_mode="Markdown")
            logger.info(f"Auto-news envoyee: {len(news)} articles.")
    except Exception as e:
        logger.error(f"Erreur auto-news: {e}")


async def auto_whale_check(app):
    if not CHAT_ID:
        return
    try:
        news = await fetch_whale_news(5)
        if news:
            img_url, msg = format_whale_news(news)
            if img_url:
                try:
                    await app.bot.send_photo(chat_id=int(CHAT_ID), photo=img_url, caption=msg, parse_mode="Markdown")
                    logger.info(f"Whale alert avec image envoyee: {len(news)} articles.")
                    return
                except Exception:
                    pass
            msg = "*\U0001f40b\U0001f514 ALERTE WHALES!*\n\n" + "_Les gros detenteurs bougent des millions._\n\n" + msg
            await app.bot.send_message(chat_id=int(CHAT_ID), text=msg, parse_mode="Markdown")
            logger.info(f"Whale alert envoyee: {len(news)} articles.")
    except Exception as e:
        logger.error(f"Erreur whale check: {e}")


async def auto_economy_check(app):
    if not CHAT_ID:
        return
    try:
        news = await fetch_economy_news(5)
        if news:
            img_url, msg = format_economy_news(news)
            if img_url:
                try:
                    await app.bot.send_photo(chat_id=int(CHAT_ID), photo=img_url, caption=msg, parse_mode="Markdown")
                    logger.info(f"Economy alert avec image envoyee: {len(news)} articles.")
                    return
                except Exception:
                    pass
            msg = "*\U0001f3e2\U0001f514 ALERTE ECONOMIE CRYPTO!*\n\n" + "_Regulations, adoptions, decisions importantes._\n\n" + msg
            await app.bot.send_message(chat_id=int(CHAT_ID), text=msg, parse_mode="Markdown")
            logger.info(f"Economy alert envoyee: {len(news)} articles.")
    except Exception as e:
        logger.error(f"Erreur economy check: {e}")


async def auto_trump_check(app):
    if not CHAT_ID:
        return
    try:
        news = await fetch_trump_crypto(5)
        if news:
            img_url, msg = format_trump_news(news)
            if img_url:
                try:
                    await app.bot.send_photo(chat_id=int(CHAT_ID), photo=img_url, caption=msg, parse_mode="Markdown")
                    logger.info(f"Trump alert avec image envoyee: {len(news)} articles.")
                    return
                except Exception:
                    pass
            msg = "*\U0001f1fa\U0001f1f8\U0001f514 ALERTE TRUMP CRYPTO!*\n\n" + "_Tout ce que fait Trump sur les crypto._\n\n" + msg
            await app.bot.send_message(chat_id=int(CHAT_ID), text=msg, parse_mode="Markdown")
            logger.info(f"Trump alert envoyee: {len(news)} articles.")
    except Exception as e:
        logger.error(f"Erreur trump check: {e}")


async def daily_notification(app):
    if not CHAT_ID:
        return
    try:
        news = await fetch_all_news(5)
        whale = await fetch_whale_news(3)
        economy = await fetch_economy_news(3)
        trump_news = await fetch_trump_crypto(3)
        trending = await fetch_trending()

        from datetime import datetime
        now_str = datetime.now().strftime("%d/%m/%Y")
        msg = f"*\U0001f4ca Resume Quotidien - {now_str}*\n\n"

        if trump_news:
            msg += "\U0001f1fa\U0001f1f8 *Annonces Trump Crypto:*\n"
            for i, n in enumerate(trump_news[:3], 1):
                msg += f"{i}. {n['title']}\n"
                if n.get("url"):
                    msg += f"   \U0001f517 {n['url']}\n"
            msg += "\n"

        if whale:
            msg += "\U0001f40b *Whales:*\n"
            for i, n in enumerate(whale[:3], 1):
                msg += f"{i}. {n['title']}\n"
            msg += "\n"

        if economy:
            msg += "\U0001f3e2 *Economie:*\n"
            for i, n in enumerate(economy[:3], 1):
                msg += f"{i}. {n['title']}\n"
            msg += "\n"

        if news:
            msg += "\U0001f4f0 *News:*\n"
            for i, n in enumerate(news[:3], 1):
                msg += f"{i}. {n['title']}\n"
                if n.get("url"):
                    msg += f"   \U0001f517 {n['url']}\n"
            msg += "\n"

        if trending:
            msg += "\U0001f525 *Trending:*\n"
            for i, c in enumerate(trending[:5], 1):
                msg += f"{i}. {c['name']} ({c['symbol']})\n"
            msg += "\n"

        msg += format_airdrops() + "\n\n"
        msg += format_promising()

        await app.bot.send_message(chat_id=int(CHAT_ID), text=msg, parse_mode="Markdown")
        logger.info("Resume quotidien envoye.")
    except Exception as e:
        logger.error(f"Erreur resume: {e}")


async def post_init(app):
    commands = [
        BotCommand("start", "\U0001f7e2 Demarrer le bot"),
        BotCommand("news", "\U0001f4f0 News crypto temps reel"),
        BotCommand("whales", "\U0001f40b News whales"),
        BotCommand("economy", "\U0001f3e2 Economie crypto"),
        BotCommand("trump", "\U0001f1fa\U0001f1f8 Annonces Trump crypto"),
        BotCommand("verify", "\U0001f50d Verifier une news"),
        BotCommand("newcoins", "\U0001f195 Nouvelles cryptomonnaies"),
        BotCommand("gainers", "\U0001f4c8 Top gainers 24h"),
        BotCommand("trending", "\U0001f525 Crypto en tendance"),
        BotCommand("airdrops", "\U0001f381 Airdrops serieux"),
        BotCommand("promising", "\U0001f680 Projets prometteurs"),
        BotCommand("summary", "\U0001f4ca Resume complet"),
    ]
    await app.bot.set_my_commands(commands)


def main():
    if not BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN non defini dans .env")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", cmd_news))
    app.add_handler(CommandHandler("whales", cmd_whales))
    app.add_handler(CommandHandler("economy", cmd_economy))
    app.add_handler(CommandHandler("trump", cmd_trump))
    app.add_handler(CommandHandler("verify", cmd_verify))
    app.add_handler(CommandHandler("newcoins", cmd_newcoins))
    app.add_handler(CommandHandler("gainers", cmd_gainers))
    app.add_handler(CommandHandler("trending", cmd_trending))
    app.add_handler(CommandHandler("airdrops", cmd_airdrops))
    app.add_handler(CommandHandler("promising", cmd_promising))
    app.add_handler(CommandHandler("summary", cmd_summary))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.post_init = post_init

    scheduler = AsyncIOScheduler()

    scheduler.add_job(auto_news_check, "interval", minutes=15, args=[app])
    scheduler.add_job(auto_whale_check, "interval", minutes=10, args=[app])
    scheduler.add_job(auto_economy_check, "interval", minutes=15, args=[app])
    scheduler.add_job(auto_trump_check, "interval", minutes=10, args=[app])
    scheduler.add_job(daily_notification, "cron", hour=9, minute=0, args=[app])

    scheduler.start()

    port = int(os.environ.get("PORT", 8000))
    render_url = os.environ.get("RENDER_EXTERNAL_URL")

    if render_url:
        print(f"Bot demarre sur Render! URL: {render_url}")
        print("- Mode webhook pour production 24/7")
        start_health_server(port)
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=BOT_TOKEN,
            webhook_url=f"{render_url}/{BOT_TOKEN}",
        )
    else:
        print("Bot demarre en local!")
        print("- News auto toutes les 15 min (9 sources)")
        print("- Whale alertes toutes les 10 min")
        print("- Economy alertes toutes les 15 min")
        print("- Trump alertes toutes les 10 min")
        print("- Resume quotidien a 9h00")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
