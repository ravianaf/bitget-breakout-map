"""
Builds news.json for the Crypto Breakout Map page: recent headlines from public
crypto news RSS feeds, each tagged with the coins it mentions.

Runs on a schedule in GitHub Actions (see .github/workflows/news.yml), because
browsers cannot read these feeds directly (no CORS) and no API key is needed.

Coin matching (deliberately conservative -- short tickers collide with words):
  - "$TICKER" anywhere, or the ticker as an UPPERCASE word of 3+ letters that is
    not a common acronym (ETF, SEC, CEO, ...)
  - or the project's name as a whole word, only for the top ~300 coins by market
    cap and only for names that are not ordinary English words
Standard library only.
"""
import html
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

FEEDS = {
    "Cointelegraph": "https://cointelegraph.com/rss",
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "Decrypt": "https://decrypt.co/feed",
    "The Block": "https://www.theblock.co/rss.xml",
    "CryptoSlate": "https://cryptoslate.com/feed/",
    "Bitcoinist": "https://bitcoinist.com/feed/",
    "Bitcoin.com News": "https://news.bitcoin.com/feed/",
    "U.Today": "https://u.today/rss",
    "NewsBTC": "https://www.newsbtc.com/feed/",
    "BeInCrypto": "https://beincrypto.com/feed/",
    "Cryptonews": "https://cryptonews.com/news/feed/",
    "CryptoPotato": "https://cryptopotato.com/feed/",
}
KEEP_DAYS = 7
MAX_ITEMS = 600
UA = {"User-Agent": "Mozilla/5.0 (crypto-breakout-map news builder)"}
NOT_TICKERS = {"THE", "AND", "FOR", "NEW", "CEO", "CTO", "ETF", "ETFS", "USD", "SEC", "CFTC", "NFT", "NFTS", "DAO", "API", "APP",
               "TOP", "ONE", "BIG", "GAS", "ALL", "ATH", "ATL", "TVL", "OTC", "IPO", "GDP", "CPI", "FED", "FOMC", "IMF", "USA",
               "UK", "EU", "AI", "DEX", "CEX", "KYC", "AML", "BTC2", "WEB", "WEB3", "NOW", "GET", "HOT", "WIN", "OUT", "OPEN",
               "JUST", "MORE", "BEST", "REAL", "LIVE", "NEXT", "MOVE", "BACK", "SAFE", "MAX", "MAGIC", "TRUMP", "DOGS", "CAT",
               "HIGH", "LOW", "FUN", "ACE", "ZERO", "BOND", "META", "FORM", "FIRE", "GOLD", "IRS", "DOJ", "FBI", "UAE", "CEOS",
               "PEOPLE", "TIME", "NEAR", "LINK", "SAND", "MASK", "ROSE", "GALA", "FLOW", "ICP", "POL", "DATA", "SUN", "ONT",
               "AUDIO", "SIGN", "STORY", "CORE", "ICE", "BANK", "PUMP", "COOKIE", "HOME", "STEP", "SOON", "PLAY", "SKY"}
COMMON_NAME_WORDS = {"near", "link", "chain", "sand", "mask", "rose", "gala", "flow", "sun", "dash", "core", "ice", "bank", "pump",
                     "cookie", "home", "step", "soon", "play", "sky", "story", "sign", "magic", "trump", "people", "time", "data",
                     "audio", "gold", "fire", "form", "meta", "bond", "zero", "ace", "fun", "high", "low", "max", "safe", "move",
                     "real", "live", "next", "best", "more", "just", "open", "out", "win", "hot", "get", "now", "web", "one",
                     "polygon", "maker", "graph", "render", "hedera", "celestia", "stacks", "arbitrum", "optimism", "starknet",
                     "injective", "sei", "sui", "aptos", "toncoin", "tron", "stellar", "cosmos", "theta", "fantom", "harmony",
                     "kava", "mina", "oasis", "zcash", "algorand", "tezos", "neo", "waves", "loopring", "curve", "compound",
                     "uniswap", "aave", "lido", "ethena", "pendle", "jupiter", "raydium", "pepe", "bonk", "floki", "brett"}
# names above that ARE distinctive project names get re-enabled here (curated)
DISTINCTIVE = {"polygon", "hedera", "celestia", "arbitrum", "optimism", "starknet", "injective", "aptos", "toncoin", "algorand",
               "tezos", "loopring", "uniswap", "aave", "lido", "ethena", "pendle", "raydium", "pepe", "bonk", "floki", "zcash",
               "fantom", "stellar", "cosmos"}
POS = ["surge", "surges", "soar", "soars", "rally", "rallies", "jump", "jumps", "gain", "gains", "record high", "all-time high",
       "bullish", "breakout", "partnership", "partners", "launch", "launches", "listing", "lists", "approval", "approved",
       "upgrade", "adoption", "inflow", "inflows", "rebound", "recover", "recovers", "buyback", "integrat", "milestone"]
NEG = ["plunge", "plunges", "crash", "crashes", "drop", "drops", "fall", "falls", "slump", "bearish", "hack", "hacked", "exploit",
       "lawsuit", "sued", "delist", "delisting", "outflow", "outflows", "selloff", "sell-off", "liquidation", "liquidations",
       "scam", "fraud", "investigation", "ban", "bans", "warning", "dump", "dumps", "decline", "declines", "risk"]


def get(url, timeout=25):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def clean(text, limit=320):
    text = re.sub(r"<[^>]+>", " ", html.unescape(text or ""))
    text = re.sub(r"\s+", " ", text.replace("�", "'")).strip()      # some feeds mis-encode curly quotes
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def parse_feed(name, raw):
    out = []
    root = ET.fromstring(raw)
    for it in root.iter("item"):
        title = clean(it.findtext("title"), 240)
        link = (it.findtext("link") or "").strip()
        desc = clean(it.findtext("description"))
        pub = it.findtext("pubDate")
        try:
            ts = parsedate_to_datetime(pub).timestamp() if pub else time.time()
        except Exception:
            ts = time.time()
        if title and link:
            out.append({"ts": int(ts), "title": title, "desc": desc, "link": link, "src": name})
    return out


DISTINCTIVE |= {"cardano", "solana", "polkadot", "litecoin", "monero", "ethereum", "bitcoin", "hyperliquid", "chainlink",
                "dogecoin", "avalanche", "ripple", "sui", "tron", "near", "toncoin", "worldcoin", "fartcoin", "bittensor"}
COMMON_NAME_WORDS |= {"vision", "bedrock", "four", "genius", "grass", "beam", "canton", "midnight", "golem", "gram", "spark",
                      "pyth", "kite", "plume", "ondo", "aster", "sonic", "berachain", "mantle", "linea", "blast", "zora"}


def name_is_safe(name):
    """Multi-word names are specific enough; single words only when they read as a project name."""
    low = name.lower()
    if low in DISTINCTIVE:
        return True
    if " " in name.strip() or low in COMMON_NAME_WORDS:
        return " " in name.strip() and low not in COMMON_NAME_WORDS
    camel = any(ch.isupper() for ch in name[1:]) or any(ch.isdigit() for ch in name)
    return camel or len(name) >= 8


def coin_universe():
    """Base tickers tradable on the page's exchange + names for the top coins by market cap."""
    syms = json.loads(get("https://api.bitget.com/api/v2/spot/public/symbols"))["data"]
    bases = sorted({s["baseCoin"].upper() for s in syms if s.get("quoteCoin") == "USDT" and s.get("status") == "online"
                    and s.get("areaSymbol") != "yes"})
    names = {}
    try:
        for page in (1, 2):
            for c in json.loads(get(f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=150&page={page}")):
                sym, nm = (c.get("symbol") or "").upper(), (c.get("name") or "").strip()
                if sym in bases and nm and len(nm) >= 4 and name_is_safe(nm):
                    names.setdefault(sym, nm)
            time.sleep(3)
    except Exception as e:
        print("coingecko names skipped:", e)
    return bases, names


def tag(items, bases, names):
    ticker_re = {b: re.compile(r"(?:\$" + re.escape(b) + r"\b)|(?:(?<![A-Za-z0-9$])" + re.escape(b) + r"(?![A-Za-z0-9]))")
                 for b in bases if len(b) >= 3 and b not in NOT_TICKERS and b.isalnum()}
    dollar_only = {b: re.compile(r"\$" + re.escape(b) + r"\b") for b in bases if b in NOT_TICKERS or len(b) < 3}
    name_re = {b: re.compile(r"\b" + re.escape(n) + r"\b", re.I) for b, n in names.items()}
    for it in items:
        text = it["title"] + " " + it["desc"]
        coins = set()
        for b, rx in ticker_re.items():
            if rx.search(text):
                coins.add(b)
        for b, rx in dollar_only.items():
            if rx.search(text):
                coins.add(b)
        for b, rx in name_re.items():
            if rx.search(text):
                coins.add(b)
        low = text.lower()
        p = sum(low.count(w) for w in POS)
        n = sum(low.count(w) for w in NEG)
        it["coins"] = sorted(coins)
        it["tone"] = 1 if p > n else (-1 if n > p else 0)
    return items


def main():
    items, ok = [], []
    for name, url in FEEDS.items():
        try:
            got = parse_feed(name, get(url))
            items += got
            ok.append(f"{name} {len(got)}")
        except Exception as e:
            print(f"feed failed: {name}: {type(e).__name__}: {e}")
    cutoff = time.time() - KEEP_DAYS * 86400
    seen, uniq = set(), []
    for it in sorted(items, key=lambda x: -x["ts"]):
        key = re.sub(r"\W+", "", it["title"].lower())[:80]
        if it["ts"] >= cutoff and key not in seen:
            seen.add(key)
            uniq.append(it)
    bases, names = coin_universe()
    uniq = tag(uniq[:MAX_ITEMS], bases, names)
    out = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "sources": ok, "items": uniq}
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    tagged = sum(1 for i in uniq if i["coins"])
    print(f"feeds ok: {', '.join(ok)}")
    print(f"{len(uniq)} articles in the last {KEEP_DAYS} days, {tagged} mention at least one coin")


if __name__ == "__main__":
    main()
