import os
import json
import aiohttp
import asyncio
import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse


COINGECKO_BASE = "https://api.coingecko.com/api/v3"
CRYPTOPANIC_BASE = "https://cryptopanic.com/api/free/v1"
CRYPTOCOMPARE_BASE = "https://min-api.cryptocompare.com/data/v2"
SEEN_FILE = Path(__file__).parent / "seen_news.json"
NS_MEDIA = {"media": "http://search.yahoo.com/mrss/"}
NS_CONTENT = {"content": "http://purl.org/rss/1.0/modules/content/"}


def load_seen():
    if SEEN_FILE.exists():
        try:
            return json.loads(SEEN_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(seen))


def news_hash(title):
    return hashlib.md5(title.encode()).hexdigest()[:12]


def extract_image_from_rss(item):
    media = item.find("media:thumbnail", NS_MEDIA)
    if media is not None:
        url = media.get("url", "")
        if url:
            return url

    media = item.find("media:content", NS_MEDIA)
    if media is not None:
        url = media.get("url", "")
        if url:
            return url

    enclosure = item.find("enclosure")
    if enclosure is not None:
        url = enclosure.get("url", "")
        mime = enclosure.get("type", "")
        if url and "image" in mime:
            return url

    content_encoded = item.find("content:encoded", NS_CONTENT)
    if content_encoded is not None and content_encoded.text:
        match = re.search(r'<img[^>]+src=["\']([^"\']+)', content_encoded.text)
        if match:
            return match.group(1)

    desc = item.findtext("description", "")
    if desc:
        match = re.search(r'<img[^>]+src=["\']([^"\']+)', desc)
        if match:
            return match.group(1)

    return ""


async def fetch_og_image(url, session):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            if resp.status != 200:
                return ""
            html = await resp.text()
            match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html)
            if match:
                return match.group(1)
            match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html)
            if match:
                return match.group(1)
    except Exception:
        pass
    return ""


TRUSTED_SOURCES = [
    "coindesk", "cointelegraph", "the block", "bitcoin magazine",
    "decrypt", "dlnews", "blockworks", "the defiant",
    "reuters", "bloomberg", "cnbc", "financial times",
    "wall street journal", "forbes", "barrons",
    "ethereum.org", "bitcoin.org", "solana.com",
]

SUSPICIOUS_SIGNALS = [
    "guaranteed returns", "get rich quick", "100x guaranteed",
    "send me crypto", "private key", "seed phrase",
    "double your bitcoin", "free money", "no risk",
    "secret investment", "insider tip", "act fast",
    "limited time only", "exclusive opportunity",
]

WHALE_KEYWORDS = [
    "whale", "whales", "large transfer", "big move",
    "million bitcoin", "million ethereum", "million usdt",
    "million usdc", "institutional", "blackrock", "fidelity",
    "microstrategy", "tesla bitcoin", "coinbase whale",
    "exchange inflow", "exchange outflow", "accumulation",
    "major holder", "big buyer", "massive buy",
]

ECONOMY_KEYWORDS = [
    "regulation", "ban", "legal", "law", "sec", "cftc",
    "interest rate", "fed", "federal reserve", "inflation",
    "gdp", "recession", "monetary policy", "fiscal",
    "adoption", "etf", "spot etf", "institutional",
    "country", "government", "senate", "congress",
    "tax", "compliance", "aml", "kyc",
    "mining", "halving", "hash rate",
    "stablecoin", "cbdc", "digital dollar",
]


def analyze_credibility(title, body="", source=""):
    score = 50
    reasons = []

    src_lower = source.lower()
    for trusted in TRUSTED_SOURCES:
        if trusted in src_lower:
            score += 25
            reasons.append(f"Source fiable: {source}")
            break

    title_lower = title.lower()
    body_lower = body.lower()
    full_text = title_lower + " " + body_lower

    for signal in SUSPICIOUS_SIGNALS:
        if signal in full_text:
            score -= 20
            reasons.append(f"Signal suspect detecte: '{signal}'")
            break

    if any(w in full_text for w in ["confirmed", "official", "announced", "verified", "confirme", "officiel", "annonce"]):
        score += 10
        reasons.append("Termes officiels detectes dans l'article")

    if any(w in full_text for w in ["rumor", "rumour", "reportedly", "allegedly", "unconfirmed", "rumeur", "non confirme", "selon des sources"]):
        score -= 15
        reasons.append("Information non confirmee / rumeur")

    if any(w in full_text for w in ["hack", "exploit", "rug pull", "scam", "fraud", "piratage", "arnaque"]):
        score -= 10
        reasons.append("Contexte negatif: possible incident de securite")

    if any(w in full_text for w in ["partnership", "listing", "upgrade", "mainnet", "partenariat", "listing", "mise a jour"]):
        score += 10
        reasons.append("Evenement positif pour le projet")

    if any(w in full_text for w in ["bloomberg", "reuters", "cnbc", "financial times", "wall street journal"]):
        score += 15
        reasons.append("Source de premier plan international")

    if any(w in full_text for w in ["sec", "cftc", "regulation", "regulation", "reglementation", "ban", "interdiction"]):
        score += 5
        reasons.append("Contexte regulatorie important")

    score = max(0, min(100, score))

    if score >= 70:
        verdict = "VERIFIE"
        icon = "\U0001f7e2"
    elif score >= 40:
        verdict = "A VERIFIER"
        icon = "\U0001f7e1"
    else:
        verdict = "SUSPECT"
        icon = "\U0001f534"

    return {
        "score": score,
        "verdict": verdict,
        "icon": icon,
        "reasons": reasons,
    }


def is_whale_news(title, body=""):
    text = (title + " " + body).lower()
    return any(kw in text for kw in WHALE_KEYWORDS)


def is_economy_news(title, body=""):
    text = (title + " " + body).lower()
    matches = sum(1 for kw in ECONOMY_KEYWORDS if kw in text)
    return matches >= 2


def is_trump_crypto(title, body=""):
    trump_kws = [
        "trump", "donald trump", "bitcoin reserve", "strategic reserve",
        "white house crypto", "world liberty financial", "wlfi",
        "trump memecoin", "trump token", "sec trump",
    ]
    text = (title + " " + body).lower()
    return any(kw in text for kw in trump_kws)


async def fetch_cryptopanic_news(limit=15):
    results = []
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{CRYPTOPANIC_BASE}/posts/?filter=hot&public=true"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
            for item in data.get("results", [])[:limit]:
                currencies = [c.get("code", "") for c in item.get("currencies", [])]
                results.append({
                    "title": item.get("title", "N/A"),
                    "source": item.get("source", {}).get("title", "N/A"),
                    "published": item.get("published_at", ""),
                    "url": item.get("url", ""),
                    "currencies": currencies,
                    "body": "",
                })
    except Exception:
        pass
    return results


async def fetch_cryptocompare_news(limit=15):
    results = []
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{CRYPTOCOMPARE_BASE}/news/?lang=EN&sortOrder=latest"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
            for item in data.get("Data", [])[:limit]:
                results.append({
                    "title": item.get("title", "N/A"),
                    "source": item.get("source", "N/A"),
                    "published": item.get("published_on", ""),
                    "url": item.get("url", ""),
                    "currencies": [item.get("categories", "")],
                    "body": item.get("body", "")[:300],
                })
    except Exception:
        pass
    return results


async def fetch_coindesk_rss(limit=10):
    results = []
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return []
                text = await resp.text()
            root = ET.fromstring(text)
            for item in root.findall(".//item")[:limit]:
                image = extract_image_from_rss(item)
                link = item.findtext("link", "")
                if not image and link:
                    image = await fetch_og_image(link, session)
                results.append({
                    "title": item.findtext("title", ""),
                    "source": "CoinDesk",
                    "published": item.findtext("pubDate", ""),
                    "url": link,
                    "currencies": [],
                    "body": (item.findtext("description", "") or "")[:300],
                    "image": image,
                })
    except Exception:
        pass
    return results


async def fetch_cointelegraph_rss(limit=10):
    results = []
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://cointelegraph.com/rss"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return []
                text = await resp.text()
            root = ET.fromstring(text)
            for item in root.findall(".//item")[:limit]:
                image = extract_image_from_rss(item)
                link = item.findtext("link", "")
                if not image and link:
                    image = await fetch_og_image(link, session)
                results.append({
                    "title": item.findtext("title", ""),
                    "source": "CoinTelegraph",
                    "published": item.findtext("pubDate", ""),
                    "url": link,
                    "currencies": [],
                    "body": (item.findtext("description", "") or "")[:300],
                    "image": image,
                })
    except Exception:
        pass
    return results


async def fetch_bitcoin_mag_rss(limit=10):
    results = []
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://bitcoinmagazine.com/.rss/full/"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return []
                text = await resp.text()
            root = ET.fromstring(text)
            for item in root.findall(".//item")[:limit]:
                image = extract_image_from_rss(item)
                link = item.findtext("link", "")
                if not image and link:
                    image = await fetch_og_image(link, session)
                results.append({
                    "title": item.findtext("title", ""),
                    "source": "Bitcoin Magazine",
                    "published": item.findtext("pubDate", ""),
                    "url": link,
                    "currencies": ["BTC"],
                    "body": (item.findtext("description", "") or "")[:300],
                    "image": image,
                })
    except Exception:
        pass
    return results


async def fetch_theblock_rss(limit=10):
    results = []
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://www.theblock.co/rss.xml"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return []
                text = await resp.text()
            root = ET.fromstring(text)
            ns = {"dc": "http://purl.org/dc/elements/1.1/"}
            for item in root.findall(".//item")[:limit]:
                image = extract_image_from_rss(item)
                link = item.findtext("link", "")
                if not image and link:
                    image = await fetch_og_image(link, session)
                results.append({
                    "title": item.findtext("title", ""),
                    "source": "The Block",
                    "published": "",
                    "url": link,
                    "currencies": [],
                    "body": (item.findtext("description", "") or "")[:300],
                    "image": image,
                })
    except Exception:
        pass
    return results


async def fetch_decrypt_rss(limit=10):
    results = []
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://decrypt.co/feed"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return []
                text = await resp.text()
            root = ET.fromstring(text)
            for item in root.findall(".//item")[:limit]:
                image = extract_image_from_rss(item)
                link = item.findtext("link", "")
                if not image and link:
                    image = await fetch_og_image(link, session)
                results.append({
                    "title": item.findtext("title", ""),
                    "source": "Decrypt",
                    "published": item.findtext("pubDate", ""),
                    "url": link,
                    "currencies": [],
                    "body": (item.findtext("description", "") or "")[:300],
                    "image": image,
                })
    except Exception:
        pass
    return results


async def fetch_reuters_rss(limit=10):
    results = []
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://www.reuters.com/arc/outboundfeeds/v3/all/byCategoryTopics/?outputType=xml&size=10"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return []
                text = await resp.text()
            root = ET.fromstring(text)
            for item in root.findall(".//item")[:limit]:
                title = item.findtext("title", "")
                body = (item.findtext("description", "") or "")
                crypto_words = ["bitcoin", "crypto", "ethereum", "blockchain", "token", "defi", "nft"]
                if any(w in (title + body).lower() for w in crypto_words):
                    image = extract_image_from_rss(item)
                    link = item.findtext("link", "")
                    if not image and link:
                        image = await fetch_og_image(link, session)
                    results.append({
                        "title": title,
                        "source": "Reuters",
                        "published": item.findtext("pubDate", ""),
                        "url": link,
                        "currencies": [],
                        "body": body[:300],
                        "image": image,
                    })
    except Exception:
        pass
    return results


async def fetch_bloomberg_rss(limit=10):
    results = []
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://feeds.bloomberg.com/markets/news.rss"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return []
                text = await resp.text()
            root = ET.fromstring(text)
            for item in root.findall(".//item")[:limit]:
                title = item.findtext("title", "")
                body = (item.findtext("description", "") or "")
                crypto_words = ["bitcoin", "crypto", "ethereum", "blockchain", "token", "defi", "digital asset"]
                if any(w in (title + body).lower() for w in crypto_words):
                    image = extract_image_from_rss(item)
                    link = item.findtext("link", "")
                    if not image and link:
                        image = await fetch_og_image(link, session)
                    results.append({
                        "title": title,
                        "source": "Bloomberg",
                        "published": item.findtext("pubDate", ""),
                        "url": link,
                        "currencies": [],
                        "body": body[:300],
                        "image": image,
                    })
    except Exception:
        pass
    return results


async def fetch_all_news_raw(limit=30):
    results = await asyncio.gather(
        fetch_cryptopanic_news(limit),
        fetch_cryptocompare_news(limit),
        fetch_coindesk_rss(limit),
        fetch_cointelegraph_rss(limit),
        fetch_bitcoin_mag_rss(limit),
        fetch_theblock_rss(limit),
        fetch_decrypt_rss(limit),
        fetch_reuters_rss(limit),
        fetch_bloomberg_rss(limit),
        return_exceptions=True,
    )
    all_news = []
    for r in results:
        if isinstance(r, list):
            all_news.extend(r)
    return all_news


def dedup_news(news_list):
    seen = load_seen()
    fresh = []
    for n in news_list:
        h = news_hash(n["title"])
        if h not in seen:
            seen[h] = datetime.now().isoformat()
            fresh.append(n)
    old_keys = [k for k, v in seen.items()
                if datetime.fromisoformat(v) < datetime.now() - timedelta(hours=48)]
    for k in old_keys:
        del seen[k]
    save_seen(seen)
    return fresh


async def fetch_all_news(limit=15):
    all_news = await fetch_all_news_raw(limit)
    return dedup_news(all_news)[:limit]


async def fetch_whale_news(limit=10):
    all_news = await fetch_all_news_raw(50)
    whale_news = []
    for n in all_news:
        if is_whale_news(n.get("title", ""), n.get("body", "")):
            whale_news.append(n)
    return dedup_news(whale_news)[:limit]


async def fetch_economy_news(limit=10):
    all_news = await fetch_all_news_raw(50)
    economy_news = []
    for n in all_news:
        if is_economy_news(n.get("title", ""), n.get("body", "")):
            economy_news.append(n)
    return dedup_news(economy_news)[:limit]


async def fetch_trump_crypto(limit=10):
    all_news = await fetch_all_news_raw(50)
    trump_news = []
    for n in all_news:
        if is_trump_crypto(n.get("title", ""), n.get("body", "")):
            trump_news.append(n)
    return dedup_news(trump_news)[:limit]


async def verify_news(title, body="", source=""):
    return analyze_credibility(title, body, source)


async def fetch_new_coins(limit=10):
    async with aiohttp.ClientSession() as session:
        url = f"{COINGECKO_BASE}/coins/list"
        async with session.get(url) as resp:
            if resp.status != 200:
                return []
            all_coins = await resp.json()
        url2 = f"{COINGECKO_BASE}/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 250,
            "page": 1,
            "sparkline": "false",
        }
        async with session.get(url2, params=params) as resp:
            if resp.status != 200:
                return []
            market_coins = await resp.json()
        market_ids = {c["id"] for c in market_coins}
        new_coins = [c for c in all_coins if c["id"] not in market_ids][-limit:]
        new_coins.reverse()
        results = []
        for coin in new_coins:
            cid = coin.get("id", "")
            results.append({
                "name": coin.get("name", "N/A"),
                "symbol": coin.get("symbol", "N/A").upper(),
                "id": cid,
                "link": f"https://www.coingecko.com/en/coins/{cid}",
            })
        if not results:
            top = market_coins[-limit:]
            top.reverse()
            for c in top:
                cid = c.get("id", "")
                results.append({
                    "name": c.get("name", "N/A"),
                    "symbol": c.get("symbol", "N/A").upper(),
                    "price": c.get("current_price", 0),
                    "change_24h": c.get("price_change_percentage_24h", 0),
                    "market_cap": c.get("market_cap", 0),
                    "link": f"https://www.coingecko.com/en/coins/{cid}",
                })
        return results


async def fetch_top_gainers(limit=10):
    async with aiohttp.ClientSession() as session:
        url = f"{COINGECKO_BASE}/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 250,
            "page": 1,
            "sparkline": "false",
        }
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                return []
            coins = await resp.json()
        for c in coins:
            c["change_24h"] = c.get("price_change_percentage_24h") or 0
        coins.sort(key=lambda x: x["change_24h"], reverse=True)
        results = []
        for c in coins[:limit]:
            cid = c.get("id", "")
            results.append({
                "name": c.get("name", "N/A"),
                "symbol": c.get("symbol", "N/A").upper(),
                "price": c.get("current_price", 0),
                "change_24h": c.get("change_24h", 0),
                "market_cap": c.get("market_cap", 0),
                "link": f"https://www.coingecko.com/en/coins/{cid}",
            })
        return results


async def fetch_trending():
    async with aiohttp.ClientSession() as session:
        url = f"{COINGECKO_BASE}/search/trending"
        async with session.get(url) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
        results = []
        for item in data.get("coins", [])[:10]:
            coin = item.get("item", {})
            cid = coin.get("id", "")
            results.append({
                "name": coin.get("name", "N/A"),
                "symbol": coin.get("symbol", "N/A").upper(),
                "market_cap_rank": coin.get("market_cap_rank", "N/A"),
                "score": coin.get("score", 0),
                "link": f"https://www.coingecko.com/en/coins/{cid}",
            })
        return results


AIRDROP_LIST = [
    {
        "project": "Monad",
        "description": "Blockchain L1 performante (10K TPS) compatible EVM. Lever 225M$.",
        "status": "Pre-launch",
        "task": "Tester les protos sur testnet, suivre sur Twitter",
        "potential": "$100 - $2000+",
        "links": [
            "https://www.monad.xyz",
            "https://testnet.monad.xyz",
            "https://twitter.com/monaboratory_",
            "https://galxe.com/monad",
        ],
    },
    {
        "project": "Berachain",
        "description": "L1 Proof-of-Liquidity. Ecosystème DeFi natif.",
        "status": "Mainnet",
        "task": "Tester les dApps Bera (BEX, Bend, Berps), staker BERA",
        "potential": "$50 - $1500+",
        "links": [
            "https://www.berachain.com",
            "https://bex.berachain.com",
            "https://bend.berachain.com",
            "https://twitter.com/beraboratory",
        ],
    },
    {
        "project": "Scroll",
        "description": "Layer 2 zkEVM pour Ethereum.",
        "status": "En attente",
        "task": "Bridge ETH vers Scroll, swap sur ScrollSwap, minter NFTs",
        "potential": "$50 - $1000+",
        "links": [
            "https://scroll.io",
            "https://scroll.io/ecosystem",
            "https://twitter.com/Scroll_ZKP",
            "https://scrollsky.com",
        ],
    },
    {
        "project": "Linea (ConsenSys)",
        "description": "Layer 2 zkEVM par ConsenSys. Ecosysteme en croissance rapide.",
        "status": "Actif",
        "task": "Bridge ETH, utiliser Velodrome, minter des NFTs",
        "potential": "$30 - $500+",
        "links": [
            "https://linea.build",
            "https://linea.build/ecosystem",
            "https://twitter.com/LineaBuild",
        ],
    },
    {
        "project": "Blast",
        "description": "Layer 2 avec yield natif pour ETH et stables.",
        "status": "Actif",
        "task": "Bridge ETH/stables, participer au Gold",
        "potential": "$20 - $300+",
        "links": [
            "https://blast.io",
            "https://twitter.com/Blur_Foundation",
        ],
    },
    {
        "project": "LayerZero (ZRO)",
        "description": "Protocol de communication cross-chain. Saison 2 possible.",
        "status": "Saison 2 possible",
        "task": "Utiliser les apps sur LayerZero (Stargate, Galxe)",
        "potential": "$50 - $500+",
        "links": [
            "https://layerzero.network",
            "https://stargate.finance",
            "https://galxe.com/layerzero",
        ],
    },
    {
        "project": "EigenLayer",
        "description": "Protocol de restaking sur Ethereum.",
        "status": "Actif",
        "task": "Staker ETH, participer aux AVS, reclamer EIGEN",
        "potential": "$30 - $500+",
        "links": [
            "https://www.eigenlayer.xyz",
            "https://app.eigenlayer.xyz",
            "https://galxe.com/eigenlayer",
        ],
    },
    {
        "project": "Sui",
        "description": "Layer 1 Move-based par Mysten Labs. Airdrops recurrents.",
        "status": "Airdrops recurrents",
        "task": "Utiliser les dApps Sui (Cetus, Turbos, DeepBook)",
        "potential": "$20 - $400+",
        "links": [
            "https://sui.io",
            "https://suiscan.xyz",
            "https://cetus.zone",
        ],
    },
    {
        "project": "Sei Network",
        "description": "Layer 1 optimisee pour le trading. V2 recent.",
        "status": "Actif",
        "task": "Staker SEI, utiliser Sei dApps",
        "potential": "$20 - $300+",
        "links": [
            "https://www.sei.io",
            "https://galxe.com/sei",
        ],
    },
    {
        "project": "Movement",
        "description": "L2 Move-based pour Ethereum. 38M$ leve.",
        "status": "Testnet",
        "task": "Tester le testnet Movement, bridge, faucet",
        "potential": "$50 - $800+",
        "links": [
            "https://www.movementlabs.xyz",
            "https://galxe.com/movement",
        ],
    },
    {
        "project": "Eclipse",
        "description": "L2 Ethereum avec runtime Solana (SVM).",
        "status": "Mainnet",
        "task": "Bridge ETH, utiliser les dApps Eclipse",
        "potential": "$30 - $500+",
        "links": [
            "https://www.eclipse.xyz",
            "https://galxe.com/eclipse",
        ],
    },
    {
        "project": "Abstract",
        "description": "L2 par Pudgy Penguins / Igloo Inc. Focus consumer.",
        "status": "Pre-launch",
        "task": "Suivre les annonces, participer aux campaigns",
        "potential": "$30 - $500+",
        "links": [
            "https://www.abstract.xyz",
            "https://twitter.com/AbstractFTW",
        ],
    },
]

PROMISING_PROJECTS = [
    {
        "name": "Monad",
        "sector": "L1 / Infrastructure",
        "description": "Blockchain L1 EVM-compatible a 10,000 TPS. Lever 225M$.",
        "why": "Performance extreme, gaming/DeFi, forte communaute.",
        "stage": "Testnet",
        "token": "Pas encore",
        "links": ["https://www.monad.xyz", "https://twitter.com/monaboratory_"],
    },
    {
        "name": "Berachain",
        "sector": "L1 / DeFi",
        "description": "Proof-of-Liquidity, DeFi native. TVL testnet >100M$.",
        "why": "Mecanique innovante, community-driven.",
        "stage": "Mainnet",
        "token": "BERA (live)",
        "links": ["https://www.berachain.com", "https://twitter.com/beraboratory"],
    },
    {
        "name": "Hyperliquid",
        "sector": "DeFi / Perps",
        "description": "DEX perpetuals avec orderbook on-chain. Airdrop massif HYPE.",
        "why": "Produit excellent, token distribue equitablement.",
        "stage": "Mainnet",
        "token": "HYPE (live)",
        "links": ["https://hyperliquid.xyz", "https://twitter.com/HyperliquidX"],
    },
    {
        "name": "Eclipse",
        "sector": "L2 / SolanaVM",
        "description": "L2 Ethereum avec runtime Solana (SVM).",
        "why": "Combine le meilleur d'Ethereum et Solana.",
        "stage": "Mainnet",
        "token": "Pas encore",
        "links": ["https://www.eclipse.xyz", "https://twitter.com/EclipseFND"],
    },
    {
        "name": "Movement",
        "sector": "L2 / Move",
        "description": "L2 Move-based pour Ethereum. 38M$ leve.",
        "why": "Securite Move + liquidite Ethereum.",
        "stage": "Testnet",
        "token": "Pas encore",
        "links": ["https://www.movementlabs.xyz", "https://twitter.com/maboratory_"],
    },
    {
        "name": "Sonic Labs (ex Fantom)",
        "sector": "L1 / Infrastructure",
        "description": "Nouvelle chaine Fantom avec 10K TPS et EVM.",
        "why": "Andre Cronje, tech solide, migration FTM->S.",
        "stage": "Mainnet",
        "token": "SONIC (live)",
        "links": ["https://soniclabs.tech", "https://twitter.com/SonicLabs"],
    },
    {
        "name": "Abstract",
        "sector": "L2 / Consumer",
        "description": "L2 par Pudgy Penguins / Igloo Inc.",
        "why": "Focus consumer, forte marque NFT.",
        "stage": "Pre-launch",
        "token": "Pas encore",
        "links": ["https://www.abstract.xyz", "https://twitter.com/AbstractFTW"],
    },
    {
        "name": "Fhenix",
        "sector": "L2 / FHE",
        "description": "L2 avec Fully Homomorphic Encryption.",
        "why": "Confidentialite on-chain, use cases uniques.",
        "stage": "Testnet",
        "token": "Pas encore",
        "links": ["https://fhenix.io", "https://twitter.com/FhenixIO"],
    },
]


def format_news(news_list):
    if not news_list:
        return "\U0001f50d Aucune nouvelle crypto pour le moment."
    msg = f"*\U0001f4f0 News Crypto - {datetime.now().strftime('%d/%m %H:%M')}*\n\n"
    for i, n in enumerate(news_list[:10], 1):
        currencies = ", ".join(n.get("currencies", [])[:3])
        cur_tag = f" [{currencies}]" if currencies else ""
        analysis = analyze_credibility(n.get("title", ""), n.get("body", ""), n.get("source", ""))
        msg += f"*{i}. {n['title']}*{cur_tag}\n"
        msg += f"   {analysis['icon']} Fiabilite: {analysis['verdict']} ({analysis['score']}/100)\n"
        msg += f"   \U0001f4dd Source: {n.get('source', 'N/A')}\n"
        if n.get("body"):
            body = n["body"][:200].replace("\n", " ").strip()
            msg += f"   \U0001f4dd Resume: {body}...\n"
        if analysis["reasons"]:
            msg += f"   \U0001f4a1 Analyse: {'; '.join(analysis['reasons'][:2])}\n"
        if n.get("url"):
            msg += f"   \U0001f517 Lien: {n['url']}\n"
        msg += "\n"
    return msg


def format_news_with_images(news_list):
    if not news_list:
        return None, "\U0001f50d Aucune nouvelle crypto pour le moment."
    first_with_image = None
    for n in news_list[:10]:
        if n.get("image"):
            first_with_image = n
            break

    msg = f"*\U0001f4f0 News Crypto - {datetime.now().strftime('%d/%m %H:%M')}*\n\n"
    for i, n in enumerate(news_list[:10], 1):
        currencies = ", ".join(n.get("currencies", [])[:3])
        cur_tag = f" [{currencies}]" if currencies else ""
        analysis = analyze_credibility(n.get("title", ""), n.get("body", ""), n.get("source", ""))
        msg += f"*{i}. {n['title']}*{cur_tag}\n"
        msg += f"   {analysis['icon']} Fiabilite: {analysis['verdict']} ({analysis['score']}/100)\n"
        msg += f"   \U0001f4dd Source: {n.get('source', 'N/A')}\n"
        if n.get("body"):
            body = n["body"][:200].replace("\n", " ").strip()
            msg += f"   \U0001f4dd Resume: {body}...\n"
        if analysis["reasons"]:
            msg += f"   \U0001f4a1 Analyse: {'; '.join(analysis['reasons'][:2])}\n"
        if n.get("url"):
            msg += f"   \U0001f517 Lien: {n['url']}\n"
        msg += "\n"

    img_url = first_with_image.get("image") if first_with_image else None
    return img_url, msg


def format_whale_news(news_list):
    if not news_list:
        return None, "\U0001f40b Aucune news whale pour le moment."
    first_with_image = None
    for n in news_list[:10]:
        if n.get("image"):
            first_with_image = n
            break

    msg = f"*\U0001f40b News Whales (Gros Detenteurs) - {datetime.now().strftime('%d/%m %H:%M')}*\n\n"
    msg += "_Les whales sont les gros porteurs de crypto qui bougent des millions._\n\n"
    for i, n in enumerate(news_list[:10], 1):
        analysis = analyze_credibility(n.get("title", ""), n.get("body", ""), n.get("source", ""))
        msg += f"*{i}. {n['title']}*\n"
        msg += f"   {analysis['icon']} Fiabilite: {analysis['verdict']} ({analysis['score']}/100)\n"
        msg += f"   \U0001f4dd Source: {n.get('source', 'N/A')}\n"
        if n.get("body"):
            body = n["body"][:200].replace("\n", " ").strip()
            msg += f"   \U0001f4dd Resume: {body}...\n"
        if analysis["reasons"]:
            msg += f"   \U0001f4a1 Analyse: {'; '.join(analysis['reasons'][:2])}\n"
        if n.get("url"):
            msg += f"   \U0001f517 Lien: {n['url']}\n"
        msg += "\n"

    img_url = first_with_image.get("image") if first_with_image else None
    return img_url, msg


def format_economy_news(news_list):
    if not news_list:
        return None, "\U0001f3e2 Aucune news economie crypto pour le moment."
    first_with_image = None
    for n in news_list[:10]:
        if n.get("image"):
            first_with_image = n
            break

    msg = f"*\U0001f3e2 Economie Crypto - {datetime.now().strftime('%d/%m %H:%M')}*\n\n"
    msg += "_Regulations, adoptions, decisions gouvernementales, marches._\n\n"
    for i, n in enumerate(news_list[:10], 1):
        analysis = analyze_credibility(n.get("title", ""), n.get("body", ""), n.get("source", ""))
        msg += f"*{i}. {n['title']}*\n"
        msg += f"   {analysis['icon']} Fiabilite: {analysis['verdict']} ({analysis['score']}/100)\n"
        msg += f"   \U0001f4dd Source: {n.get('source', 'N/A')}\n"
        if n.get("body"):
            body = n["body"][:200].replace("\n", " ").strip()
            msg += f"   \U0001f4dd Resume: {body}...\n"
        if analysis["reasons"]:
            msg += f"   \U0001f4a1 Analyse: {'; '.join(analysis['reasons'][:2])}\n"
        if n.get("url"):
            msg += f"   \U0001f517 Lien: {n['url']}\n"
        msg += "\n"

    img_url = first_with_image.get("image") if first_with_image else None
    return img_url, msg


def format_trump_news(news_list):
    if not news_list:
        return None, "\U0001f1fa\U0001f1f8 Aucune annonce Trump crypto pour le moment."
    first_with_image = None
    for n in news_list[:10]:
        if n.get("image"):
            first_with_image = n
            break

    msg = f"*\U0001f1fa\U0001f1f8 Annonces Trump + Crypto - {datetime.now().strftime('%d/%m %H:%M')}*\n\n"
    msg += "_Tout ce que dit et fait Trump sur les cryptomonnaies._\n\n"
    for i, n in enumerate(news_list[:10], 1):
        analysis = analyze_credibility(n.get("title", ""), n.get("body", ""), n.get("source", ""))
        msg += f"*{i}. {n['title']}*\n"
        msg += f"   {analysis['icon']} Fiabilite: {analysis['verdict']} ({analysis['score']}/100)\n"
        msg += f"   \U0001f4dd Source: {n.get('source', 'N/A')}\n"
        if n.get("body"):
            body = n["body"][:200].replace("\n", " ").strip()
            msg += f"   \U0001f4dd Resume: {body}...\n"
        if analysis["reasons"]:
            msg += f"   \U0001f4a1 Analyse: {'; '.join(analysis['reasons'][:2])}\n"
        if n.get("url"):
            msg += f"   \U0001f517 Lien: {n['url']}\n"
        msg += "\n"

    img_url = first_with_image.get("image") if first_with_image else None
    return img_url, msg


def format_verify(title, body="", source=""):
    analysis = analyze_credibility(title, body, source)
    msg = f"*\U0001f50d Analyse de Fiabilite d'une News*\n\n"
    msg += f"*Titre analyse:* {title}\n"
    if source:
        msg += f"*Source:* {source}\n"
    msg += f"\n*{analysis['icon']} Verdict: {analysis['verdict']}*\n"
    msg += f"*Score de fiabilite:* {analysis['score']}/100\n\n"
    if analysis["reasons"]:
        msg += "*Details de l'analyse:*\n"
        for r in analysis["reasons"]:
            msg += f"  \u2022 {r}\n"
    else:
        msg += "_Aucun signal suspect ou fiable detecte automatiquement._\n"
    msg += "\n*Comment interpreter le score:*\n"
    msg += "  \U0001f7e2 70-100: Information probablement fiable\n"
    msg += "  \U0001f7e1 40-69: A verifier avec d'autres sources\n"
    msg += "  \U0001f534 0-39: Potentiellement faux ou arnaque\n"
    msg += "\n_Utilise /verify suivi du titre d'une news pour l'analyser._"
    return msg


def format_new_coins(coins):
    if not coins:
        return "Aucune nouvelle crypto trouvee."
    msg = f"*\U0001f195 Nouvelles Cryptomonnaies - {datetime.now().strftime('%d/%m/%Y')}*\n\n"
    for i, c in enumerate(coins, 1):
        if "price" in c:
            price_str = f"${c['price']:,.6f}" if c['price'] < 1 else f"${c['price']:,.2f}"
            change = c.get("change_24h", 0) or 0
            arrow = "+" if change >= 0 else ""
            msg += f"*{i}. {c['name']} ({c['symbol']})*\n"
            msg += f"   \U0001f4b0 {price_str} | {arrow}{change:.1f}%\n"
            if c.get("link"):
                msg += f"   \U0001f517 {c['link']}\n"
            msg += "\n"
        else:
            msg += f"*{i}. {c['name']} ({c['symbol']})*\n"
            if c.get("link"):
                msg += f"   \U0001f517 {c['link']}\n"
            msg += "\n"
    return msg


def format_top_gainers(coins):
    if not coins:
        return "Aucun top gainers trouve."
    msg = f"*\U0001f4c8 Top Gainers 24h - {datetime.now().strftime('%d/%m/%Y')}*\n\n"
    for i, c in enumerate(coins, 1):
        change = c.get("change_24h", 0) or 0
        price = c.get("price", 0) or 0
        price_str = f"${price:,.6f}" if price < 1 else f"${price:,.2f}"
        msg += f"*{i}. {c['name']} ({c['symbol']})*\n"
        msg += f"   \U0001f4b0 {price_str} | \U0001f7e2 +{change:.1f}%\n"
        if c.get("link"):
            msg += f"   \U0001f517 {c['link']}\n"
        msg += "\n"
    return msg


def format_trending(coins):
    if not coins:
        return "Aucun trending trouve."
    msg = f"*\U0001f525 Crypto Trending - {datetime.now().strftime('%d/%m/%Y')}*\n\n"
    for i, c in enumerate(coins, 1):
        msg += f"*{i}. {c['name']} ({c['symbol']})*\n"
        if c.get("market_cap_rank"):
            msg += f"   \U0001f3c6 Rang: #{c['market_cap_rank']}\n"
        if c.get("link"):
            msg += f"   \U0001f517 {c['link']}\n"
        msg += "\n"
    return msg


def format_airdrops():
    msg = f"*\U0001f381 Airdrops Series - {datetime.now().strftime('%d/%m/%Y')}*\n\n"
    for i, a in enumerate(AIRDROP_LIST, 1):
        if a["status"] in ("Actif", "Mainnet", "Testnet"):
            status_icon = "\U0001f7e2"
        else:
            status_icon = "\U0001f7e1"
        msg += f"*{i}. {a['project']}* {status_icon} [{a['status']}]\n"
        msg += f"   \U0001f4cb {a['description']}\n"
        msg += f"   \U0001f4dd *Tache:* {a['task']}\n"
        msg += f"   \U0001f4b0 *Potentiel:* {a['potential']}\n"
        if a.get("links"):
            msg += "   \U0001f517 *Liens:*\n"
            for link in a["links"]:
                msg += f"      {link}\n"
        msg += "\n"
    msg += "_\U0001f4d6 DYOR. Les airdrops ne sont jamais garantis._"
    return msg


def format_promising():
    msg = f"*\U0001f680 Projets Crypto Prometteurs - {datetime.now().strftime('%d/%m/%Y')}*\n\n"
    for i, p in enumerate(PROMISING_PROJECTS, 1):
        if p["stage"] == "Mainnet":
            stage_icon = "\U0001f7e2"
        else:
            stage_icon = "\U0001f7e1"
        msg += f"*{i}. {p['name']}* {stage_icon} [{p['stage']}]\n"
        msg += f"   \U0001f4c2 Secteur: {p['sector']}\n"
        msg += f"   \U0001f4dd {p['description']}\n"
        msg += f"   \U0001f4a1 *Pourquoi:* {p['why']}\n"
        msg += f"   \U0001f4b3 Token: {p['token']}\n"
        if p.get("links"):
            msg += "   \U0001f517 *Liens:*\n"
            for link in p["links"]:
                msg += f"      {link}\n"
        msg += "\n"
    msg += "_\U0001f4d6 DYOR. Ceci n'est pas un conseil financier._"
    return msg


def format_daily_summary():
    msg = f"*\U0001f4ca Resume Quotidien - {datetime.now().strftime('%d/%m/%Y')}*\n\n"
    msg += "/news - \U0001f4f0 News crypto temps reel\n"
    msg += "/whales - \U0001f40b News whales\n"
    msg += "/economy - \U0001f3e2 Economie crypto\n"
    msg += "/trump - \U0001f1fa\U0001f1f8 Annonces Trump crypto\n"
    msg += "/verify - \U0001f50d Verifier une news\n"
    msg += "/newcoins - \U0001f195 Nouvelles cryptomonnaies\n"
    msg += "/gainers - \U0001f4c8 Top gainers 24h\n"
    msg += "/trending - \U0001f525 Crypto en tendance\n"
    msg += "/airdrops - \U0001f381 Airdrops avec liens\n"
    msg += "/promising - \U0001f680 Projets prometteurs\n"
    return msg
