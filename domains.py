"""TrendScout - thu thập trend theo LĨNH VỰC (game, thể thao, nhạc, idol, phim, TV...).
Toàn bộ nguồn miễn phí, không cần key:
  - Wikipedia: top bài được xem nhiều nhất (hôm qua so với 7 ngày trước) + mô tả để phân loại lĩnh vực
  - Apple: top bài hát, phim, TV, podcast, app, sách tại Mỹ
  - Billboard Hot 100, Box Office Mojo (doanh thu phòng vé cuối tuần)
  - SteamCharts, SteamSpy (game PC đang được chơi nhiều)
  - RSS tin tức chuyên ngành: IGN, Billboard, Variety, Soompi + Google News theo từng lĩnh vực
"""
import json, re, time, html as H, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta, date
from email.utils import parsedate_to_datetime

UA_BROWSER = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
UA_WIKI = "TrendScout/0.2 (personal trend dashboard)"

# ---- Định nghĩa lĩnh vực: tên hiển thị, từ khoá Google News, từ khoá phân loại mô tả Wikipedia ----
DOMAINS = {
    "game": {"label": "Game", "icon": "🎮",
             "news": ["video game", "gaming news", "PlayStation", "Xbox", "Nintendo Switch", "Roblox", "Fortnite", "Steam game", "esports"],
             "wiki": ["video game", "game developer", "esports", "gaming", "game publisher", "mmorpg", "battle royale", "roblox", "minecraft"]},
    "sports": {"label": "Thể thao", "icon": "🏈",
               "news": ["NFL", "NBA", "MLB", "World Series", "NHL", "college football", "WNBA", "UFC", "MLS soccer", "Formula 1", "golf PGA", "tennis"],
               "wiki": ["football", "footballer", "football club", "f.c.", "basketball", "baseball", "ice hockey", "soccer", "tennis", "cricketer", "golfer", "boxer", "mixed martial", "wrestler",
                        "racing driver", "wnba", "mls", "quarterback", "athlete", "olympic", "world series", "super bowl", "nfl", "nba", "mlb", "nhl", "ufc",
                        "grand prix", "championship", "league season", "sports", "cricket", "rugby", "coach", "pitcher", "sprinter", "cyclist"]},
    "music": {"label": "Ca sĩ & âm nhạc", "icon": "🎤",
              "news": ["new album", "Billboard chart", "music tour", "concert tour", "rapper", "new single", "Grammy", "country music"],
              "wiki": ["singer", "rapper", "musician", "band", "song", "album", "record producer", "songwriter", "dj", "music group",
                       "concert tour", "single by", "hip hop", "rock band", "pop group"]},
    "idol": {"label": "Idol & người nổi tiếng", "icon": "⭐",
             "news": ["K-pop", "celebrity", "influencer", "TikTok star", "YouTuber", "Hollywood couple", "Kardashian", "reality star"],
             "wiki": ["actor", "actress", "model", "influencer", "youtuber", "media personality", "television personality", "socialite",
                      "internet personality", "streamer", "tiktoker", "k-pop", "idol", "comedian", "presenter", "podcaster",
                      "voice actor", "actors", "supermodel", "television host", "drag queen"]},
    "film": {"label": "Phim điện ảnh", "icon": "🎬",
             "news": ["box office", "movie trailer", "new movie", "film release", "Marvel movie", "horror movie", "Oscar"],
             "wiki": ["film", "movie", "film director", "filmmaker", "film series", "franchise", "animated feature", "documentary"]},
    "tv": {"label": "TV, series & anime", "icon": "📺",
           "news": ["Netflix series", "TV show", "streaming series", "HBO", "Disney+", "anime", "reality show", "season finale"],
           "wiki": ["television series", "tv series", "miniseries", "sitcom", "reality", "talk show", "anime", "manga", "streaming",
                    "web series", "game show", "soap opera", "episode", "season"]},
    "tech": {"label": "Công nghệ & app", "icon": "📱",
             "news": ["new app", "AI app", "iPhone", "ChatGPT", "tech gadget", "smartphone launch"],
             "wiki": ["software", "mobile app", "smartphone", "artificial intelligence", "technology company", "chatbot", "website", "operating system",
                      "social media", "programming", "computer", "video-sharing", "platform", "top-level domain", "search engine"]},
    "books": {"label": "Sách & podcast", "icon": "📚",
              "news": ["bestselling book", "BookTok", "new novel", "podcast charts"], "wiki": ["novel", "book by", "novelist", "podcast"]},
    "season": {"label": "Mùa lễ & sự kiện", "icon": "🎃", "news": [],
               "wiki": ["holiday", "festival", "observance", "celebrated", "shopping holiday", "parade"]},
    "news": {"label": "Thời sự & xã hội", "icon": "📰",
             "news": ["breaking news", "viral video", "internet reacts"], "wiki": ["politician", "political", "election", "elections", "polling", "businesswoman", "businessperson",
                                  "executive", "serial killer", "criminal", "activist", "journalist", "president", "senator", "governor", "shooting", "attack", "disaster", "hurricane",
                                  "war", "conflict", "murder", "protest", "lawyer", "judge", "businessman", "billionaire", "death of",
                                  "assassination", "crash", "earthquake", "military", "prime minister", "monarch", "pope", "royal"]},
}
# thứ tự ưu tiên khi một mô tả khớp nhiều lĩnh vực
# kiểm tra nghề nghiệp con người trước (actor -> idol, rapper -> music, footballer -> sports), rồi mới tới tác phẩm
WIKI_ORDER = ["game", "sports", "music", "idol", "season", "news", "tv", "film", "books", "tech"]
SKIP_WIKI = re.compile(r"^(Main_Page|Special:|Wikipedia:|Portal:|File:|Help:|Template:|Category:|Talk:|User:|List_of_|Lists_of_|Deaths_in_|\.xxx$|XNXX|XVideos|Pornhub|xHamster|.*\.(php|jpg|png))", re.I)
NSFW = re.compile(r"pornograph|adult website|sex offender", re.I)


def _get(url, ua=UA_BROWSER, timeout=40, tries=3):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Language": "en-US,en;q=0.9"})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(5)


def wiki_lookup(queries):
    """tìm bài Wikipedia gần nhất cho mỗi từ khoá (dùng để phân loại Google Trends)"""
    out = {}
    for q in queries:
        try:
            j = json.loads(_get("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
                {"action": "query", "list": "search", "srsearch": q, "srlimit": 1, "format": "json"}), UA_WIKI))
            hits = j.get("query", {}).get("search", [])
            if hits:
                t = hits[0]["title"]
                out[q] = {"title": t, "desc": wiki_descriptions([t.replace(" ", "_")]).get(t.replace(" ", "_"), "")}
        except Exception:
            pass
        time.sleep(0.2)
    return out


def _iso(pub):
    try:
        return parsedate_to_datetime(pub).astimezone(timezone.utc).isoformat()
    except Exception:
        return None


WORK_RULES = [(r"\bvideo game\b", "game"), (r"\b(television|tv|web|anime|streaming) series\b|\bminiseries\b|\bsitcom\b|\breality (television )?(series|show|competition)\b", "tv"),
              (r"\b(19|20)\d\d\b[^,;]*\b(film|documentary)\b", "film"), (r"\b(song|single|album|ep) by\b", "music"), (r"\b(novel|book) by\b", "books")]


def classify_text(text):
    t = " " + (text or "").lower() + " "
    for pat, d in WORK_RULES:  # tác phẩm (phim, series, game, bài hát) nhận diện trước nghề nghiệp
        if re.search(pat, t):
            return d
    for d in WIKI_ORDER:
        for k in DOMAINS[d]["wiki"]:
            if re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", t):
                return d
    return None


# ---------------- Wikipedia ----------------
def wiki_top(day):
    u = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/{day:%Y/%m/%d}"
    j = json.loads(_get(u, UA_WIKI))
    return {a["article"]: a["views"] for a in j["items"][0]["articles"] if not SKIP_WIKI.match(a["article"])}


def wiki_descriptions(titles):
    out = {}
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        q = urllib.parse.urlencode({"action": "query", "prop": "description|pageprops", "ppprop": "disambiguation",
                                    "titles": "|".join(t.replace("_", " ") for t in chunk), "format": "json", "redirects": 1})
        j = json.loads(_get("https://en.wikipedia.org/w/api.php?" + q, UA_WIKI))
        norm = {n["to"]: n["from"] for n in j.get("query", {}).get("normalized", [])}
        redir = {r["to"]: r["from"] for r in j.get("query", {}).get("redirects", [])}
        for p in j.get("query", {}).get("pages", {}).values():
            t = p.get("title", "")
            orig = redir.get(t, t)
            orig = norm.get(orig, orig).replace(" ", "_")
            out[orig] = p.get("description", "")
        time.sleep(0.3)
    return out


def collect_wikipedia(n=250):
    today = datetime.now(timezone.utc).date()
    d1 = today - timedelta(days=1)
    try:
        cur = wiki_top(d1)
    except Exception:
        d1 = today - timedelta(days=2); cur = wiki_top(d1)
    prev = wiki_top(d1 - timedelta(days=7))
    top = sorted(cur.items(), key=lambda kv: kv[1], reverse=True)[:n]
    desc = wiki_descriptions([t for t, _ in top])
    items = []
    for rank, (t, v) in enumerate(top, 1):
        dsc = desc.get(t, "")
        if NSFW.search(dsc):
            continue
        dom = classify_text(dsc) or classify_text(t.replace("_", " "))
        pv = prev.get(t)
        items.append({"source": "wikipedia", "domain": dom or "other", "title": t.replace("_", " "), "desc": dsc,
                      "views": v, "views_prev_week": pv, "rank": rank,
                      "change": (round(v / pv, 2) if pv else None), "is_new": pv is None,
                      "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(t)})
    return items, str(d1)


# ---------------- Bảng xếp hạng ----------------
def apple_feed(kind, path, domain, label, limit=25):
    j = json.loads(_get(f"https://rss.applemarketingtools.com/api/v2/us/{path}/{limit}/{kind}.json", timeout=60))
    return [{"source": "chart", "chart": label, "domain": domain, "rank": i, "title": r["name"],
             "sub": r.get("artistName", ""), "url": r.get("url")} for i, r in enumerate(j["feed"]["results"], 1)]


def itunes_feed(path, domain, label, limit=25):
    j = json.loads(_get(f"https://itunes.apple.com/us/rss/{path}/limit={limit}/json"))
    out = []
    for i, e in enumerate(j["feed"].get("entry", []), 1):
        out.append({"source": "chart", "chart": label, "domain": domain, "rank": i, "title": e["im:name"]["label"],
                    "sub": e.get("im:artist", {}).get("label", ""), "url": e.get("link", {}).get("attributes", {}).get("href") if isinstance(e.get("link"), dict) else None})
    return out


def billboard_hot100(limit=50):
    h = _get("https://www.billboard.com/charts/hot-100/")
    rows = re.findall(r'<li class="o-chart-results-list__item[^"]*">\s*<h3 id="title-of-a-story"[^>]*>(.*?)</h3>\s*<span\s+class="\s*c-label\s+a-no-trucate[^"]*">(.*?)</span>', h, re.S)
    clean = lambda s: H.unescape(re.sub(r"<[^>]+>", "", s)).strip()
    return [{"source": "chart", "chart": "Billboard Hot 100", "domain": "music", "rank": i, "title": clean(t), "sub": clean(a),
             "url": "https://www.billboard.com/charts/hot-100/"} for i, (t, a) in enumerate(rows[:limit], 1)]


def box_office():
    today = date.today()
    last_sun = today - timedelta(days=(today.weekday() + 1) % 7 or 7)
    for back in (0, 1, 2):
        d = last_sun - timedelta(days=7 * back)
        y, w, _ = (d - timedelta(days=2)).isocalendar()
        url = f"https://www.boxofficemojo.com/weekend/{y}W{w:02d}/"
        try:
            h = _get(url)
        except Exception:
            continue
        rows = re.findall(r'mojo-field-type-release[^"]*">\s*<a class="a-link-normal"[^>]*href="(/release/[^"]+)"[^>]*>([^<]+)</a>.*?mojo-field-type-money[^"]*">\$([\d,]+)', h, re.S)
        if rows:
            return [{"source": "chart", "chart": f"Phòng vé Mỹ cuối tuần ({y}W{w:02d})", "domain": "film", "rank": i, "title": H.unescape(t).strip(),
                     "sub": "$" + g, "value": int(g.replace(",", "")), "url": "https://www.boxofficemojo.com" + u.split("?")[0]}
                    for i, (u, t, g) in enumerate(rows[:15], 1)]
    return []


def steamcharts(limit=25):
    h = _get("https://steamcharts.com/top")
    rows = re.findall(r'<td class="game-name left">\s*<a href="/app/(\d+)">\s*(.*?)\s*</a>\s*</td>\s*<td class="num">([\d,]+)</td>', h, re.S)
    return [{"source": "chart", "chart": "Steam - người chơi cùng lúc (toàn cầu)", "domain": "game", "rank": i, "title": H.unescape(n).strip(),
             "sub": f"{int(c.replace(',', '')):,} đang chơi", "value": int(c.replace(",", "")), "url": f"https://steamcharts.com/app/{a}"}
            for i, (a, n, c) in enumerate(rows[:limit], 1)]


def steamspy_2weeks(limit=25):
    j = json.loads(_get("https://steamspy.com/api.php?request=top100in2weeks"))
    rows = sorted(j.values(), key=lambda g: g.get("ccu", 0), reverse=True)[:limit]
    return [{"source": "chart", "chart": "SteamSpy - hot 2 tuần qua", "domain": "game", "rank": i, "title": g["name"],
             "sub": f"CCU {g.get('ccu', 0):,}", "value": g.get("ccu", 0), "url": f"https://steamcharts.com/app/{g['appid']}"}
            for i, g in enumerate(rows, 1)]


# ---------------- Tin tức ----------------
def rss(url, domain, outlet, limit=40):
    root = ET.fromstring(_get(url).encode("utf-8"))
    out = []
    for it in list(root.iter("item"))[:limit]:
        out.append({"source": "news", "domain": domain, "title": H.unescape(it.findtext("title") or "").strip(),
                    "url": it.findtext("link"), "outlet": outlet, "published": _iso(it.findtext("pubDate") or "")})
    return out


def gnews(query, domain, window="3d"):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": f"{query} when:{window}", "hl": "en-US", "gl": "US", "ceid": "US:en"})
    root = ET.fromstring(_get(url).encode("utf-8"))
    out = []
    for it in root.iter("item"):
        t = it.findtext("title") or ""; src = it.findtext("source") or ""
        if src and t.endswith(" - " + src):
            t = t[: -len(src) - 3]
        out.append({"source": "news", "domain": domain, "query": query, "title": t, "url": it.findtext("link"),
                    "outlet": src, "published": _iso(it.findtext("pubDate") or "")})
    return out


# ---------------- Lịch lễ hội Mỹ (tự tính theo năm) ----------------
def _nth_weekday(y, m, wd, n):
    d = date(y, m, 1)
    d += timedelta(days=(wd - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _last_weekday(y, m, wd):
    d = (date(y, m + 1, 1) if m < 12 else date(y + 1, 1, 1)) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - wd) % 7)


def _easter(y):
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25; g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mo = (h + l - 7 * m + 114) // 31; dy = ((h + l - 7 * m + 114) % 31) + 1
    return date(y, mo, dy)


def holiday_calendar(y):
    tg = _nth_weekday(y, 11, 3, 4)
    return [
        ("Valentine's Day", date(y, 2, 14), ["gift", "decor"]),
        ("Super Bowl", _nth_weekday(y, 2, 6, 2), ["party", "merch"]),
        ("St. Patrick's Day", date(y, 3, 17), ["outfit", "decor"]),
        ("Easter", _easter(y), ["basket", "decor"]),
        ("Mother's Day", _nth_weekday(y, 5, 6, 2), ["gift"]),
        ("Memorial Day", _last_weekday(y, 5, 0), ["sale"]),
        ("Father's Day", _nth_weekday(y, 6, 6, 3), ["gift"]),
        ("4th of July", date(y, 7, 4), ["outfit", "decor"]),
        ("Back to School", date(y, 8, 10), ["supplies", "outfit"]),
        ("Labor Day", _nth_weekday(y, 9, 0, 1), ["sale"]),
        ("Halloween", date(y, 10, 31), ["costume", "decor", "candy"]),
        ("Day of the Dead", date(y, 11, 1), ["decor", "makeup"]),
        ("Thanksgiving", tg, ["decor", "recipe", "table"]),
        ("Black Friday", tg + timedelta(days=1), ["deals", "best sellers"]),
        ("Cyber Monday", tg + timedelta(days=4), ["deals"]),
        ("Christmas", date(y, 12, 25), ["gift", "decor", "stocking stuffers", "ugly sweater"]),
        ("New Year's Eve", date(y, 12, 31), ["outfit", "party"]),
    ]


def upcoming_holidays(ahead=70, past=3, today=None):
    today = today or date.today()
    out = []
    for y in (today.year, today.year + 1):
        for name, d, kinds in holiday_calendar(y):
            delta = (d - today).days
            if -past <= delta <= ahead:
                out.append({"name": name, "date": d.isoformat(), "days_left": delta, "kinds": kinds})
    return sorted(out, key=lambda h: h["days_left"])


def season_queries(h):
    n = h["name"]
    qs = [f"{n} trend", f"viral {n} TikTok", f"{n} 2026"] + [f"{n} {k}" for k in h["kinds"]]
    return qs[:7]


# ---------------- Mạng xã hội: Bluesky + YouTube (miễn phí, công khai) ----------------
def bsky_trending():
    j = json.loads(_get("https://public.api.bsky.app/xrpc/app.bsky.unspecced.getTrendingTopics", UA_WIKI))
    out = []
    for i, t in enumerate(j.get("topics", []), 1):
        out.append({"source": "bluesky_trend", "rank": i, "title": t.get("topic"), "desc": t.get("description", ""),
                    "url": "https://bsky.app" + t.get("link", ""), "domain": classify_text((t.get("topic") or "") + " " + (t.get("description") or "")) or "other"})
    return out


def bsky_search(q, domain, limit=25, days=4, extra=None):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    u = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?" + urllib.parse.urlencode(
        {"q": q, "limit": limit, "sort": "top", "lang": "en", "since": since})
    j = json.loads(_get(u, UA_WIKI))
    out = []
    for p in j.get("posts", []):
        rec = p.get("record", {})
        handle = p.get("author", {}).get("handle", "")
        rk = p.get("uri", "").rsplit("/", 1)[-1]
        it = {"source": "bluesky", "domain": domain, "query": q, "title": (rec.get("text") or "").strip()[:400],
              "url": f"https://bsky.app/profile/{handle}/post/{rk}", "author": handle,
              "likes": p.get("likeCount", 0), "reposts": p.get("repostCount", 0), "replies": p.get("replyCount", 0),
              "published": rec.get("createdAt")}
        it["engagement"] = it["likes"] + 2 * it["reposts"] + 2 * it["replies"]
        if extra:
            it.update(extra)
        out.append(it)
    return out


def _views(txt):
    m = re.search(r"([\d,.]+)\s*([KMB]?)", txt or "")
    if not m:
        return 0
    v = float(m.group(1).replace(",", ""))
    return int(v * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}[m.group(2)])


def yt_search(q, domain, extra=None):
    """YouTube: video đăng trong tuần này khớp từ khoá (đọc trang kết quả công khai)"""
    h = _get("https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": q, "sp": "EgIIAw==", "hl": "en", "gl": "US"}))
    out = []
    for chunk in h.split('"videoRenderer":{')[1:16]:
        chunk = chunk[:6000]
        vid = re.search(r'"videoId":"([\w-]{11})"', chunk)
        title = re.search(r'"title":\{"runs":\[\{"text":"((?:[^"\\]|\\.)+)"', chunk)
        views = re.search(r'"viewCountText":\{"simpleText":"([^"]+)"', chunk)
        ch = re.search(r'"ownerText":\{"runs":\[\{"text":"((?:[^"\\]|\\.)+)"', chunk)
        pub = re.search(r'"publishedTimeText":\{"simpleText":"([^"]+)"', chunk)
        if not (vid and title):
            continue
        t = json.loads('"' + title.group(1) + '"')
        it = {"source": "youtube", "domain": domain, "query": q, "title": t, "url": "https://www.youtube.com/watch?v=" + vid.group(1),
              "author": json.loads('"' + ch.group(1) + '"') if ch else "", "views": _views(views.group(1) if views else ""),
              "ago": pub.group(1) if pub else ""}
        it["engagement"] = it["views"] // 1000
        if extra:
            it.update(extra)
        out.append(it)
    return out


def collect_social(log=print):
    """thảo luận mạng xã hội theo lĩnh vực + mùa lễ"""
    posts, status = [], {}
    try:
        tr = bsky_trending(); status["Bluesky trending"] = f"ok ({len(tr)})"
    except Exception as e:
        tr = []; status["Bluesky trending"] = f"lỗi: {str(e)[:60]}"
    nb = ny = 0
    hols = upcoming_holidays()
    jobs = []
    for d, cfg in DOMAINS.items():
        for q in cfg["news"][:4]:
            jobs.append((q, d, None))
    for h in hols[:4]:
        for q in season_queries(h)[:4]:
            jobs.append((q, "season", {"holiday": h["name"]}))
    for q, d, extra in jobs:
        try:
            r = bsky_search(q, d, extra=extra); posts += r; nb += len(r)
        except Exception as e:
            log("  bsky", q, str(e)[:60])
        time.sleep(0.35)
    status["Bluesky bài viết"] = f"ok ({nb})"
    yt_jobs = [(cfg["news"][0], d, None) for d, cfg in DOMAINS.items() if cfg["news"]]
    yt_jobs += [(cfg["news"][1], d, None) for d, cfg in DOMAINS.items() if len(cfg["news"]) > 1]
    for h in hols[:3]:
        for q in season_queries(h)[2:5]:
            yt_jobs.append((q, "season", {"holiday": h["name"]}))
    for q, d, extra in yt_jobs:
        try:
            r = yt_search(q, d, extra); posts += r; ny += len(r)
        except Exception as e:
            log("  yt", q, str(e)[:60])
        time.sleep(0.6)
    status["YouTube tuần này"] = f"ok ({ny})"
    log(f"  bluesky: {nb}, youtube: {ny}, trending: {len(tr)}")
    return {"posts": posts, "bsky_trending": tr, "holidays": hols, "status": status}


def collect_all(log=print):
    res = {"wiki": [], "charts": [], "news": [], "status": {}}
    def run(name, fn):
        try:
            r = fn(); log(f"  {name}: {len(r) if isinstance(r, list) else 'ok'}"); res["status"][name] = f"ok ({len(r)})"; return r
        except Exception as e:
            log(f"  {name}: LỖI {e}"); res["status"][name] = f"lỗi: {str(e)[:80]}"; return []
    try:
        w, day = collect_wikipedia(); res["wiki"] = w; res["wiki_day"] = day; res["status"]["wikipedia"] = f"ok ({len(w)})"; log(f"  wikipedia: {len(w)}")
    except Exception as e:
        res["status"]["wikipedia"] = f"lỗi: {e}"; log("  wikipedia LỖI", e)
    charts = [
        ("Apple Music top bài hát", lambda: apple_feed("songs", "music/most-played", "music", "Apple Music - top bài hát Mỹ")),
        ("Billboard Hot 100", billboard_hot100),
        ("Apple top phim", lambda: itunes_feed("topmovies", "film", "iTunes - phim mua/thuê nhiều nhất")),
        ("Box Office Mojo", box_office),
        ("Apple top TV", lambda: itunes_feed("toptvseasons", "tv", "iTunes - mùa phim TV bán chạy")),
        ("Apple top podcast", lambda: apple_feed("podcasts", "podcasts/top", "books", "Apple Podcasts - top show")),
        ("SteamCharts", steamcharts),
        ("SteamSpy", steamspy_2weeks),
        ("Apple top app miễn phí", lambda: apple_feed("apps", "apps/top-free", "tech", "App Store - top app miễn phí")),
        ("Apple top sách", lambda: apple_feed("books", "books/top-paid", "books", "Apple Books - sách bán chạy")),
    ]
    for name, fn in charts:
        res["charts"] += run(name, fn)
    feeds = [("IGN", "https://feeds.feedburner.com/ign/games-all", "game"),
             ("Billboard news", "https://www.billboard.com/feed/", "music"),
             ("Variety", "https://variety.com/feed/", "film"),
             ("Soompi (K-pop)", "https://www.soompi.com/feed", "idol")]
    for name, url, dom in feeds:
        res["news"] += run(name, lambda u=url, d=dom, n=name: rss(u, d, n))
    n_g = 0
    for dom, cfg in DOMAINS.items():
        for q in cfg["news"]:
            try:
                r = gnews(q, dom); res["news"] += r; n_g += len(r)
            except Exception as e:
                log("  gnews", q, e)
            time.sleep(0.6)
    res["status"]["Google News theo lĩnh vực"] = f"ok ({n_g})"
    log(f"  google news theo lĩnh vực: {n_g}")
    # mùa lễ sắp tới
    n_s = 0
    for h in upcoming_holidays()[:5]:
        for q in season_queries(h):
            try:
                r = gnews(q, "season", window="7d")
                for x in r:
                    x["holiday"] = h["name"]
                res["news"] += r; n_s += len(r)
            except Exception as e:
                log("  gnews", q, e)
            time.sleep(0.6)
    res["status"]["Google News mùa lễ"] = f"ok ({n_s})"
    log(f"  google news mùa lễ: {n_s}")
    soc = collect_social(log)
    res["social"] = soc
    res["status"].update(soc["status"])
    return res
