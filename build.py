"""TrendScout - phân tích snapshot mới nhất và dựng dashboard.html"""
import json, re
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "raw"
SOCIAL = ROOT / "data" / "social"
HISTORY = ROOT / "data" / "history.json"
HIST_DAYS = 35
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))

STOP = set("""a an the and or but if of to in on at by for with from as is are was were be been being it its this that these those
i you he she we they them his her our your their my me us not no so do does did done has have had having will would can could should
may might must just than then there here what which who whom whose when where why how all any both each few more most other some such
only own same too very s t can will don now new says say said about after before over under up down out off again into via vs amid
one two three four five first last year years day days week weeks month months today tonight best top get gets got make makes made
how why what know need want way ways time times people thing things like look looks really still even also back much many every
review reviews deal deals sale sales news report reports according update live watch video videos photos photo inside here's it's
don't can't won't you're they're we're i'm let's 2025 2026 2027 per percent million billion us u.s. america american americans
going goes go come comes coming take takes see seen show shows find found tell told think big small good great bad better worse
worth actually explained meaning instead online finds selling sell everything something anything nothing ever never always right left
using use used help helps start starts started ready long short high low free full part side real truly totally finally officially
ahead behind around against between without within while during since until because though although latest early late
mes los las del que para con una por fall spring summer winter night morning best-selling must-have try tried trying love loves
brand brands getting bringing work works minutes fans black song obsessed experts expert popular line market growth man woman stop items item
launches launch launched could become becomes biggest huge major little lot lots shares shared share reveals revealed simple easy
customers customer save saving store stores announces announced less through design money place places way end ends set sets
food skin beauty health
""".split())
PLATFORM_WORDS = set("tiktok tiktoks reddit redditors facebook marketplace viral trend trends trending shop amazon gen z instagram consumer consumers shopping shoppers buy bought seller sellers sold product products users user".split())
QWORDS = set(w for q in CFG["niches"] + CFG["buzz_queries"] for w in re.findall(r"[a-z]+", q.lower()))
QPHRASES = set(q.lower() for q in CFG["niches"])

CATS = {
    "Làm đẹp & chăm sóc": ["skincare", "skin", "serum", "beauty", "makeup", "hair", "haircare", "lipstick", "sunscreen", "spf", "fragrance", "perfume", "nail", "moisturizer", "retinol", "cosmetic"],
    "Sức khoẻ & thực phẩm bổ sung": ["supplement", "supplements", "vitamin", "protein", "creatine", "magnesium", "glp-1", "ozempic", "wegovy", "probiotic", "sleep", "melatonin", "collagen", "gut", "wellness", "health"],
    "Đồ ăn & thức uống": ["matcha", "coffee", "snack", "drink", "drinks", "soda", "recipe", "food", "candy", "chocolate", "tea", "beverage", "restaurant", "starbucks", "costco", "trader joe"],
    "Nhà cửa & bếp": ["kitchen", "air fryer", "home", "decor", "cleaning", "furniture", "bedding", "mattress", "vacuum", "cookware", "organizer", "candle", "laundry", "christmas", "holiday"],
    "Thời trang & phụ kiện": ["fashion", "shoes", "sneaker", "dress", "jacket", "jeans", "bag", "handbag", "jewelry", "outfit", "clothing", "apparel", "boots", "costume"],
    "Công nghệ & gadget": ["phone", "iphone", "android", "gadget", "gadgets", "headphones", "earbuds", "charger", "laptop", "ai", "app", "camera", "smartwatch", "gaming", "console"],
    "Thú cưng": ["pet", "pets", "dog", "dogs", "cat", "cats", "puppy", "kitten", "chewy"],
    "Mẹ & bé": ["baby", "babies", "toddler", "kids", "parent", "parents", "stroller", "diaper", "toy", "toys"],
    "Thể thao & fitness": ["fitness", "gym", "workout", "running", "yoga", "pilates", "treadmill", "athletic"],
    "Tài chính & chi tiêu": ["price", "prices", "tariff", "tariffs", "inflation", "budget", "spending", "afford", "cost", "costs", "frugal", "recession", "black friday"],
}


def categorize(text):
    t = " " + text.lower() + " "
    for c, kws in CATS.items():
        for k in kws:
            if re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", t):
                return c
    return "Khác"


def tokens(title):
    words = re.findall(r"[a-z][a-z0-9'\-]+", title.lower().replace("’", "'"))
    return [re.sub(r"'s$", "", w).strip("'-") for w in words]


def terms_of(title):
    ws = tokens(title)
    out = set()
    for i, w in enumerate(ws):
        if w not in STOP and w not in PLATFORM_WORDS and len(w) > 2:
            out.add(w)
        if i + 1 < len(ws):
            a, b = w, ws[i + 1]
            if a not in STOP and b not in STOP and len(a) > 2 and len(b) > 2 and not (a in PLATFORM_WORDS and b in PLATFORM_WORDS):
                out.add(a + " " + b)
    return out


def term_counts(items):
    c = Counter()
    for it in items:
        c.update(terms_of(it["title"]))
    return c


def strip_q(cnt):
    """bỏ các cụm chỉ gồm chính từ khoá truy vấn (vd 'fitness', 'tiktok viral')"""
    return Counter({t: v for t, v in cnt.items()
                    if t not in QPHRASES and not all(w in QWORDS or w.rstrip("s") in QWORDS or w in PLATFORM_WORDS for w in t.split())})


def collapse(counter, n=40, min_count=3):
    """ưu tiên cụm 2 từ; bỏ từ đơn nếu đã nằm trong cụm mạnh"""
    ranked = sorted(counter.items(), key=lambda kv: kv[1] * (2.0 if " " in kv[0] else 1), reverse=True)
    picked = []
    for term, cnt in ranked:
        if cnt < min_count:
            continue
        if " " not in term:
            if any(term in p[0].split() and p[1] >= 0.5 * cnt for p in picked):
                continue
        else:
            picked = [p for p in picked if not (" " not in p[0] and p[0] in term.split() and cnt >= 0.5 * p[1])]
        picked.append((term, cnt))
        if len(picked) >= n:
            break
    return sorted(picked, key=lambda p: p[1], reverse=True)


def load_snapshots():
    files = sorted(RAW.glob("*.json"))
    snaps = [json.loads(f.read_text(encoding="utf-8")) for f in files[-2:]]
    return (snaps[-1], snaps[-2] if len(snaps) > 1 else None)


def load_social():
    files = sorted(SOCIAL.glob("*.json"))
    return [json.loads(f.read_text(encoding="utf-8")) for f in files]


def update_history(date_str, niche_rows, dom_cur):
    """Lưu đà tăng của từng ngách + số lượt nhắc từng ngày lễ vào data/history.json, cắt bớt chỉ giữ HIST_DAYS ngày gần nhất."""
    hist = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else {"niches": {}, "holidays": {}}
    hist.setdefault("niches", {}); hist.setdefault("holidays", {})
    for r in niche_rows:
        hist["niches"].setdefault(r["niche"], {})[date_str] = r["momentum"]
    for h in ((dom_cur.get("season") or {}).get("holidays") or []):
        hist["holidays"].setdefault(h["name"], {})[date_str] = h["n_news"] + h["n_social"]
    all_dates = sorted(set(d for s in hist["niches"].values() for d in s) | set(d for s in hist["holidays"].values() for d in s))
    if len(all_dates) > HIST_DAYS:
        keep = set(all_dates[-HIST_DAYS:])
        for series in list(hist["niches"].values()) + list(hist["holidays"].values()):
            for d in list(series):
                if d not in keep:
                    del series[d]
    HISTORY.write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")
    return hist


def main():
    cur, prev = load_snapshots()
    now = datetime.fromisoformat(cur["collected_at"])
    seen, items = set(), []
    for it in cur["items"]:
        k = (it["source"], it["title"].lower()[:90])
        if k in seen:
            continue
        seen.add(k); items.append(it)
    for it in items:
        it["category"] = categorize(it.get("title", "") + " " + it.get("query", ""))
        it["platform_hint"] = next((p for p in ("tiktok", "reddit", "facebook", "instagram", "amazon") if p in it["title"].lower()), None)

    text_items = [i for i in items if i["source"] in ("google_news", "reddit")]
    cur_terms = strip_q(term_counts(text_items))
    prev_terms = strip_q(term_counts([i for i in prev["items"] if i["source"] in ("google_news", "reddit")])) if prev else Counter()
    term_rows = []
    for t, c in collapse(cur_terms, 40):
        p = prev_terms.get(t, 0)
        term_rows.append({"term": t, "count": c, "prev": p if prev else None,
                          "delta": (c - p) if prev else None, "is_new": bool(prev) and p == 0,
                          "category": categorize(t)})

    buzz = [i for i in items if i["source"] == "google_news" and i["kind"] == "buzz"]
    buzz_rows = []
    buzz_bi = Counter({t: v for t, v in strip_q(term_counts(buzz)).items() if " " in t})
    for t, c in collapse(buzz_bi, 30, 2):
        ex = [i for i in buzz if t in terms_of(i["title"])][:5]
        buzz_rows.append({"term": t, "count": c, "category": categorize(t) if categorize(t) != "Khác" else categorize(ex[0]["title"] if ex else ""),
                          "examples": [{"title": e["title"], "url": e["url"], "outlet": e.get("outlet")} for e in ex]})

    social = load_social()
    fb, tiktok, tiktok_ind = {}, [], {}
    for s in social:
        for r in s.get("facebook_ads", []):
            fb[r["keyword"].lower()] = r
        if s.get("tiktok_hashtags"):
            tiktok = s["tiktok_hashtags"]
        if s.get("tiktok_all"):
            tiktok = [{"rank": r[0], "hashtag": r[1], "industry": r[2], "posts": r[3], "views": r[4]} for r in s["tiktok_all"]]
        if s.get("tiktok_by_industry"):
            tiktok_ind = {k: [{"rank": r[0], "hashtag": r[1], "industry": k, "posts": r[2], "views": r[3]} for r in v]
                          for k, v in s["tiktok_by_industry"].items()}
    notes_all = [n for s in social for n in s.get("notes", [])]
    social_notes = notes_all
    social_at = social[-1]["collected_at"] if social else None

    niche_rows = []
    for n in CFG["niches"]:
        arts = [i for i in items if i["source"] == "google_news" and i.get("query") == n]
        recent = [a for a in arts if a.get("published") and now - datetime.fromisoformat(a["published"]) <= timedelta(hours=48)]
        share = len(recent) / len(arts) if arts else 0
        nt = [t for t, _ in collapse(strip_q(term_counts(arts)), 8, 2) if t != n][:5]
        prevn = len([i for i in prev["items"] if i.get("query") == n]) if prev else None
        niche_rows.append({"niche": n, "articles": len(arts), "recent48": len(recent), "share": share,
                           "prev_articles": prevn, "fb": fb.get(n.lower()), "terms": nt,
                           "headlines": [{"title": a["title"], "url": a["url"], "outlet": a.get("outlet")}
                                         for a in sorted(recent or arts, key=lambda a: a.get("published") or "", reverse=True)[:3]]})
    shares = sorted(r["share"] for r in niche_rows if r["articles"])
    med = shares[len(shares) // 2] if shares else 0
    for r in niche_rows:
        r["momentum"] = round(r["share"] / med * 100) if med else 0
    niche_rows.sort(key=lambda r: r["momentum"], reverse=True)

    gtrends = sorted([i for i in items if i["source"] == "google_trends"], key=lambda i: i["score"], reverse=True)

    # ---- trend theo lĩnh vực ----
    import domain_build as DB
    gnews_general = [i for i in items if i["source"] == "google_news"]
    dom_cur = DB.domain_rankings(cur.get("domains"), gnews_general)
    dom_prev = DB.domain_rankings(prev.get("domains"), [i for i in prev["items"] if i["source"] == "google_news"]) if prev and prev.get("domains") else None
    DB.mark_new(dom_cur, dom_prev)
    for g in gtrends:
        g["domain"] = DB.classify_trend(g, dom_cur)
    soc = (cur.get("domains") or {}).get("social") or {}
    domains_out = {"order": DB.ORDER, "meta": DB.meta(), "data": dom_cur,
                   "wiki_day": (cur.get("domains") or {}).get("wiki_day"), "has_prev": dom_prev is not None,
                   "bsky_trending": soc.get("bsky_trending", []), "holidays": soc.get("holidays", [])}
    # gợi ý sản phẩm: research thủ công mới nhất + gợi ý tự động
    rfiles = sorted((ROOT / "data" / "research").glob("*.json"))
    research = json.loads(rfiles[-1].read_text(encoding="utf-8-sig")) if rfiles else None
    ideas = {"research": research, "auto": DB.auto_ideas(dom_cur)}

    date_str = cur["collected_at"][:10]
    hist = update_history(date_str, niche_rows, dom_cur)
    hist_dates = sorted(set(d for s in hist["niches"].values() for d in s) | set(d for s in hist["holidays"].values() for d in s))
    history_payload = {
        "dates": hist_dates,
        "niches": {k: [v.get(d) for d in hist_dates] for k, v in hist["niches"].items()},
        "holidays": {k: [v.get(d) for d in hist_dates] for k, v in hist["holidays"].items()},
    }
    reddit = sorted([i for i in items if i["source"] == "reddit"], key=lambda i: i["score"], reverse=True)[:60]
    feed = sorted(text_items, key=lambda i: i.get("published") or "", reverse=True)[:800]
    feed = [{k: i.get(k) for k in ("source", "kind", "query", "title", "url", "outlet", "published", "category", "platform_hint", "score", "subreddit")} for i in feed]
    cat_counts = Counter(i["category"] for i in text_items if i["category"] != "Khác")

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "collected_at": cur["collected_at"],
        "prev_at": prev["collected_at"] if prev else None, "status": cur["status"],
        "social_at": social_at, "social_notes": social_notes,
        "terms": term_rows, "buzz": buzz_rows, "niches": niche_rows, "gtrends": gtrends,
        "tiktok": tiktok, "tiktok_ind": tiktok_ind, "feed": feed, "cats": cat_counts.most_common(),
        "n_signals": len(items) + sum(len((cur.get("domains") or {}).get(k, [])) for k in ("wiki", "charts", "news")),
        "domains": domains_out,
        "ideas": ideas,
        "history": history_payload,
        "fb_all": sorted(fb.values(), key=lambda r: -r["active_ads"]),
    }
    tpl = (ROOT / "template.html").read_text(encoding="utf-8")
    import base64
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    enc = base64.b64encode(bytes(b ^ ((i * 7 + 13) % 256) for i, b in enumerate(raw))).decode()
    out = tpl.replace('/*__DATA__*/""', '"' + enc + '"')
    (ROOT / "dashboard.html").write_text(out, encoding="utf-8")
    print("Đã tạo dashboard.html:", len(items), "tín hiệu,", len(term_rows), "cụm từ")


if __name__ == "__main__":
    main()

