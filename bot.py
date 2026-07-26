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
from telegram.request import HTTPXRequest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from crypto_fetcher import (
    fetch_all_news,
    fetch_all_news_raw,
    fetch_whale_news,
    fetch_economy_news,
    fetch_trump_crypto,
    fetch_new_coins,
    fetch_top_gainers,
    fetch_trending,
    fetch_quick_price,
    is_whale_news,
    is_economy_news,
    is_trump_crypto,
    dedup_news,
    translate_news_batch,
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
    format_quick_price,
    md_escape,
)

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
MAX_MSG = 4000
IS_PYTHONANYWHERE = "PYTHONANYWHERE_DOMAIN" in os.environ

if IS_PYTHONANYWHERE:
    PA_PROXY = "http://proxy.pythonanywhere.com:8080"
    os.environ["HTTP_PROXY"] = PA_PROXY
    os.environ["HTTPS_PROXY"] = PA_PROXY
    os.environ["http_proxy"] = PA_PROXY
    os.environ["https_proxy"] = PA_PROXY
    print(f"Proxy PythonAnywhere actif: {PA_PROXY}")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def safe_send(chat_id, text, parse_mode="Markdown", app=None, photo=None):
    if not app:
        logger.error("safe_send: app est None, impossible d'envoyer")
        return
    if len(text) <= MAX_MSG:
        try:
            if photo:
                await app.bot.send_photo(chat_id=chat_id, photo=photo, caption=text, parse_mode=parse_mode)
            else:
                await app.bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
        except Exception:
            try:
                if photo:
                    await app.bot.send_photo(chat_id=chat_id, photo=photo, caption=text)
                else:
                    await app.bot.send_message(chat_id=chat_id, text=text)
            except Exception as e:
                logger.error(f"Erreur envoi: {e}")
        return
    parts = []
    while text:
        if len(text) <= MAX_MSG:
            parts.append(text)
            break
        cut = text.rfind("\n", 0, MAX_MSG)
        if cut == -1:
            cut = MAX_MSG
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    for part in parts:
        try:
            await app.bot.send_message(chat_id=chat_id, text=part, parse_mode=parse_mode)
        except Exception:
            try:
                await app.bot.send_message(chat_id=chat_id, text=part)
            except Exception as e:
                logger.error(f"Erreur envoi morceau: {e}")


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
        "/price - \U0001f4b1 Prix BTC, ETH, SOL, DOGE, ADA\n"
        "/airdrops - \U0001f381 Airdrops serieux avec liens\n"
        "/promising - \U0001f680 Projets prometteurs avec liens\n"
        "/summary - \U0001f4ca Resume complet\n"
        "/help - \u2139\ufe0f Aide detaillee\n\n"
        "*Fonctionnalites:*\n"
        "\u2022 Chaque news a un resume detaille en francais\n"
        "\u2022 Analyse de fiabilite (VRAI / FAUX / A VERIFIER)\n"
        "\u2022 Images explicatives quand disponibles\n"
        "\u2022 9 sources: Bloomberg, Reuters, CoinDesk, CoinTelegraph...\n\n"
        "_Alertes auto: News 15min | Whales 10min | Economy 15min | Trump 10min_"
    )
    await safe_send(update.message.chat_id, welcome, app=context.application)


async def cmd_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_send(update.message.chat_id, "\U0001f50d Recherche des news crypto...", app=context.application)
    news = await fetch_all_news(10)
    img_url, msg = format_news_with_images(news)
    await safe_send(update.message.chat_id, msg, app=context.application, photo=img_url)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "*\u2139\ufe0f Aide Crypto Bot*\n\n"
        "*Commandes disponibles:*\n\n"
        "/start - \U0001f7e2 Demarrer le bot\n"
        "/help - \u2139\ufe0f Afficher cette aide\n"
        "/news - \U0001f4f0 News crypto temps reel\n"
        "/whales - \U0001f40b News whales (gros detenteurs)\n"
        "/economy - \U0001f3e2 Economie crypto\n"
        "/trump - \U0001f1fa\U0001f1f8 Annonces Trump + crypto\n"
        "/verify - \U0001f50d Verifier fiabilite d'une news\n"
        "/newcoins - \U0001f195 Nouvelles cryptomonnaies\n"
        "/gainers - \U0001f4c8 Top gainers 24h\n"
        "/trending - \U0001f525 Crypto en tendance\n"
        "/price - \U0001f4b1 Prix BTC, ETH, SOL, DOGE, ADA\n"
        "/airdrops - \U0001f381 Airdrops serieux avec liens\n"
        "/promising - \U0001f680 Projets prometteurs avec liens\n"
        "/summary - \U0001f4ca Resume complet\n\n"
        "*Texte libre:*\n"
        "Ecris simplement un mot cle et le bot repond:\n"
        "whale, news, trump, economy, airdrop, trending, price...\n\n"
        "_Alertes auto: News 15min | Whales 10min | Economy 15min | Trump 10min_"
    )
    await safe_send(update.message.chat_id, msg, app=context.application)


async def cmd_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_send(update.message.chat_id, "\U0001f4b1 Chargement des prix...", app=context.application)
    prices = await fetch_quick_price()
    msg = format_quick_price(prices)
    await safe_send(update.message.chat_id, msg, app=context.application)


async def cmd_whales(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_send(update.message.chat_id, "\U0001f40b Recherche des news whales...", app=context.application)
    news = await fetch_whale_news(10)
    img_url, msg = format_whale_news(news)
    await safe_send(update.message.chat_id, msg, app=context.application, photo=img_url)


async def cmd_economy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_send(update.message.chat_id, "\U0001f3e2 Recherche de l'economie crypto...", app=context.application)
    news = await fetch_economy_news(10)
    img_url, msg = format_economy_news(news)
    await safe_send(update.message.chat_id, msg, app=context.application, photo=img_url)


async def cmd_trump(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_send(update.message.chat_id, "\U0001f1fa\U0001f1f8 Recherche des annonces Trump crypto...", app=context.application)
    news = await fetch_trump_crypto(10)
    img_url, msg = format_trump_news(news)
    await safe_send(update.message.chat_id, msg, app=context.application, photo=img_url)


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
    await safe_send(update.message.chat_id, msg, app=context.application)


async def cmd_newcoins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_send(update.message.chat_id, "\U0001f50d Recherche des nouvelles cryptomonnaies...", app=context.application)
    coins = await fetch_new_coins(10)
    msg = format_new_coins(coins)
    await safe_send(update.message.chat_id, msg, app=context.application)


async def cmd_gainers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_send(update.message.chat_id, "\U0001f4c8 Chargement des top gainers...", app=context.application)
    coins = await fetch_top_gainers(10)
    msg = format_top_gainers(coins)
    await safe_send(update.message.chat_id, msg, app=context.application)


async def cmd_trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_send(update.message.chat_id, "\U0001f525 Recherche des trending...", app=context.application)
    coins = await fetch_trending()
    msg = format_trending(coins)
    await safe_send(update.message.chat_id, msg, app=context.application)


async def cmd_airdrops(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = format_airdrops()
    await safe_send(update.message.chat_id, msg, app=context.application)


async def cmd_promising(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = format_promising()
    await safe_send(update.message.chat_id, msg, app=context.application)


async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_send(update.message.chat_id, "\U0001f4ca Chargement du resume complet...", app=context.application)
    all_news = await fetch_all_news_raw(50)
    whale = await translate_news_batch(dedup_news([n for n in all_news if is_whale_news(n.get("title", ""), n.get("body", ""))])[:3])
    economy = await translate_news_batch(dedup_news([n for n in all_news if is_economy_news(n.get("title", ""), n.get("body", ""))])[:3])
    trump_news = await translate_news_batch(dedup_news([n for n in all_news if is_trump_crypto(n.get("title", ""), n.get("body", ""))])[:3])
    news = await translate_news_batch(dedup_news(all_news)[:5])
    trending = await fetch_trending()
    msg = format_daily_summary(news, whale, economy, trump_news, trending)
    await safe_send(update.message.chat_id, msg, app=context.application)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    chat_id = update.message.chat_id
    if any(w in text for w in ["whale", "whales", "gros", "baleine"]):
        news = await fetch_whale_news(10)
        img_url, msg = format_whale_news(news)
        await safe_send(chat_id, msg, app=context.application, photo=img_url)
    elif any(w in text for w in ["economie", "economy", "regulation", "ban", "adoption", "sec", "etf"]):
        news = await fetch_economy_news(10)
        img_url, msg = format_economy_news(news)
        await safe_send(chat_id, msg, app=context.application, photo=img_url)
    elif any(w in text for w in ["trump", "donald", "president usa", "white house"]):
        news = await fetch_trump_crypto(10)
        img_url, msg = format_trump_news(news)
        await safe_send(chat_id, msg, app=context.application, photo=img_url)
    elif any(w in text for w in ["verify", "verifier", "fake", "faux", "vrai", "true", "scam"]):
        title = text
        for prefix in ["verify", "verifier", "is this real", "is it fake", "scam"]:
            title = title.replace(prefix, "").strip()
        msg = format_verify(title, "", "")
        await safe_send(chat_id, msg, app=context.application)
    elif any(w in text for w in ["airdrop", "air drops", "gratuit"]):
        msg = format_airdrops()
        await safe_send(chat_id, msg, app=context.application)
    elif any(w in text for w in ["prix", "price", "cours", "tarif", "btc", "eth", "sol"]):
        prices = await fetch_quick_price()
        msg = format_quick_price(prices)
        await safe_send(chat_id, msg, app=context.application)
    elif any(w in text for w in ["prometteur", "projet", "project"]):
        msg = format_promising()
        await safe_send(chat_id, msg, app=context.application)
    elif any(w in text for w in ["resume", "summary", "recap"]):
        await safe_send(chat_id, "\U0001f4ca Chargement du resume...", app=context.application)
        news = await fetch_all_news(5)
        whale = await fetch_whale_news(3)
        economy = await fetch_economy_news(3)
        trump_news = await fetch_trump_crypto(3)
        trending = await fetch_trending()
        msg = format_daily_summary(news, whale, economy, trump_news, trending)
        await safe_send(chat_id, msg, app=context.application)
    elif any(w in text for w in ["nouveau", "new coin", "latest"]):
        coins = await fetch_new_coins(10)
        msg = format_new_coins(coins)
        await safe_send(chat_id, msg, app=context.application)
    elif any(w in text for w in ["tendance", "trending", "popular"]):
        coins = await fetch_trending()
        msg = format_trending(coins)
        await safe_send(chat_id, msg, app=context.application)
    elif any(w in text for w in ["gagner", "gain", "hausse", "pump", "gainer"]):
        coins = await fetch_top_gainers(10)
        msg = format_top_gainers(coins)
        await safe_send(chat_id, msg, app=context.application)
    elif any(w in text for w in ["news", "info", "actualit", "nouvelle"]):
        news = await fetch_all_news(10)
        img_url, msg = format_news_with_images(news)
        await safe_send(chat_id, msg, app=context.application, photo=img_url)
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
            "/price - \U0001f4b1 Prix crypto\n"
            "/airdrops - \U0001f381 Airdrops\n"
            "/promising - \U0001f680 Projets prometteurs\n"
            "/summary - \U0001f4ca Resume\n"
            "/help - \u2139\ufe0f Aide"
        )
        await safe_send(chat_id, msg, app=context.application)


async def auto_news_check(app):
    if not CHAT_ID:
        return
    try:
        news = await fetch_all_news(8)
        if news:
            img_url, msg = format_news_with_images(news)
            msg = "*\U0001f514 Alerte News Crypto!*\n\n" + msg
            await safe_send(int(CHAT_ID), msg, app=app, photo=img_url)
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
            msg = "*\U0001f40b\U0001f514 ALERTE WHALES!*\n\n" + "_Les gros detenteurs bougent des millions._\n\n" + msg
            await safe_send(int(CHAT_ID), msg, app=app, photo=img_url)
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
            msg = "*\U0001f3e2\U0001f514 ALERTE ECONOMIE CRYPTO!*\n\n" + "_Regulations, adoptions, decisions importantes._\n\n" + msg
            await safe_send(int(CHAT_ID), msg, app=app, photo=img_url)
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
            msg = "*\U0001f1fa\U0001f1f8\U0001f514 ALERTE TRUMP CRYPTO!*\n\n" + "_Tout ce que fait Trump sur les crypto._\n\n" + msg
            await safe_send(int(CHAT_ID), msg, app=app, photo=img_url)
            logger.info(f"Trump alert envoyee: {len(news)} articles.")
    except Exception as e:
        logger.error(f"Erreur trump check: {e}")


async def daily_notification(app):
    if not CHAT_ID:
        return
    try:
        all_news = await fetch_all_news_raw(50)
        whale = await translate_news_batch(dedup_news([n for n in all_news if is_whale_news(n.get("title", ""), n.get("body", ""))])[:3])
        economy = await translate_news_batch(dedup_news([n for n in all_news if is_economy_news(n.get("title", ""), n.get("body", ""))])[:3])
        trump_news = await translate_news_batch(dedup_news([n for n in all_news if is_trump_crypto(n.get("title", ""), n.get("body", ""))])[:3])
        news = await translate_news_batch(dedup_news(all_news)[:5])
        trending = await fetch_trending()

        from datetime import datetime
        now_str = datetime.now().strftime("%d/%m/%Y")
        msg = f"*\U0001f4ca Resume Quotidien - {now_str}*\n\n"

        if trump_news:
            msg += "\U0001f1fa\U0001f1f8 *Annonces Trump Crypto:*\n"
            for i, n in enumerate(trump_news[:3], 1):
                msg += f"{i}. {md_escape(n.get('title', 'N/A'))}\n"
                if n.get("url"):
                    msg += f"   \U0001f517 {n['url']}\n"
            msg += "\n"

        if whale:
            msg += "\U0001f40b *Whales:*\n"
            for i, n in enumerate(whale[:3], 1):
                msg += f"{i}. {md_escape(n.get('title', 'N/A'))}\n"
            msg += "\n"

        if economy:
            msg += "\U0001f3e2 *Economie:*\n"
            for i, n in enumerate(economy[:3], 1):
                msg += f"{i}. {md_escape(n.get('title', 'N/A'))}\n"
            msg += "\n"

        if news:
            msg += "\U0001f4f0 *News:*\n"
            for i, n in enumerate(news[:3], 1):
                msg += f"{i}. {md_escape(n.get('title', 'N/A'))}\n"
                if n.get("url"):
                    msg += f"   \U0001f517 {n['url']}\n"
            msg += "\n"

        if trending:
            msg += "\U0001f525 *Trending:*\n"
            for i, c in enumerate(trending[:5], 1):
                msg += f"{i}. {md_escape(c.get('name', 'N/A'))} ({md_escape(c.get('symbol', ''))})\n"
            msg += "\n"

        msg += format_airdrops() + "\n\n"
        msg += format_promising()

        await safe_send(int(CHAT_ID), msg, app=app)
        logger.info("Resume quotidien envoye.")
    except Exception as e:
        logger.error(f"Erreur resume: {e}")


async def post_init(app):
    commands = [
        BotCommand("start", "\U0001f7e2 Demarrer le bot"),
        BotCommand("help", "\u2139\ufe0f Aide et liste des commandes"),
        BotCommand("news", "\U0001f4f0 News crypto temps reel"),
        BotCommand("whales", "\U0001f40b News whales"),
        BotCommand("economy", "\U0001f3e2 Economie crypto"),
        BotCommand("trump", "\U0001f1fa\U0001f1f8 Annonces Trump crypto"),
        BotCommand("verify", "\U0001f50d Verifier une news"),
        BotCommand("newcoins", "\U0001f195 Nouvelles cryptomonnaies"),
        BotCommand("gainers", "\U0001f4c8 Top gainers 24h"),
        BotCommand("trending", "\U0001f525 Crypto en tendance"),
        BotCommand("price", "\U0001f4b1 Prix BTC, ETH, SOL, DOGE, ADA"),
        BotCommand("airdrops", "\U0001f381 Airdrops serieux"),
        BotCommand("promising", "\U0001f680 Projets prometteurs"),
        BotCommand("summary", "\U0001f4ca Resume complet"),
    ]
    await app.bot.set_my_commands(commands)


def main():
    if not BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN non defini dans .env")
        return

    if IS_PYTHONANYWHERE:
        request = HTTPXRequest(
            proxy="http://proxy.pythonanywhere.com:8080",
            connect_timeout=30,
            read_timeout=30,
            write_timeout=30,
            media_write_timeout=30,
        )
        app = ApplicationBuilder().token(BOT_TOKEN).request(request).build()
    else:
        app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("news", cmd_news))
    app.add_handler(CommandHandler("whales", cmd_whales))
    app.add_handler(CommandHandler("economy", cmd_economy))
    app.add_handler(CommandHandler("trump", cmd_trump))
    app.add_handler(CommandHandler("verify", cmd_verify))
    app.add_handler(CommandHandler("newcoins", cmd_newcoins))
    app.add_handler(CommandHandler("gainers", cmd_gainers))
    app.add_handler(CommandHandler("trending", cmd_trending))
    app.add_handler(CommandHandler("price", cmd_price))
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

    if IS_PYTHONANYWHERE:
        print("Bot demarre sur PythonAnywhere!")
        print("- Proxy actif pour Telegram + news")
        print("- News auto toutes les 15 min (9 sources)")
        print("- Whale alertes toutes les 10 min")
        print("- Economy alertes toutes les 15 min")
        print("- Trump alertes toutes les 10 min")
        print("- Resume quotidien a 9h00")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
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
