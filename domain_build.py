"""Phân tích trend theo lĩnh vực: gộp Wikipedia + bảng xếp hạng + tin tức thành 1 bảng xếp hạng trend cho mỗi lĩnh vực."""
import re, math, urllib.parse
from collections import defaultdict
from domains import DOMAINS, classify_text

ORDER = ["season", "game", "sports", "music", "idol", "film", "tv", "tech", "books", "news"]
TITLE_STOP = set("""Watch Watches New The A An And Of In On For To With At By From Is Are Be As Its It His Her Their Our Your My Me We You He She They
Drama Dramas Variety Show Shows Star Stars Group Groups Member Members Debut Comeback Album Song Songs MV Teaser Teasers Photos Photo Poster Posters
Music Fans Fan First Full Official Concert Tour World Korean Korea K-Pop K-Drama Kdrama Episode Episodes Ratings Rating Netflix Chart Charts Billboard
Release Releases Released Reveals Revealed Shares Shared Talks Says Opens Up Gets Get Hits Hit Tops Top Wins Win More Than After Before Upcoming
Special Behind Scenes Update Updates News Day Week Year Will Has Have Had Was Were Not Into Out Over About Who What How Why When Where This That These
Those Agency Agencies Confirms Confirmed Reportedly Report Reports Announces Announced Military Enlistment Discharge Solo Japanese Chinese Global
Makes Make Stun Stuns Teams Team Faces Face Clashes Supports Pursues Stand Stands Stares Raise Raises Praise Praises Denies Deny Launch Launches
Rise Rises Enters Stumble Stumbles Return Returns Brand Reputation Rankings Ranking October November December January February March April
May June July August September Love Film Films Awards Award Nominees Profile Channels Social Media Talks Reported Director Writer Writers
Performances Powerful Romance Genre Years Weekly Circle Rumors Banning Challenge Among Artists Marriage Wife Pregnancy Action Dashing Glimpse
Troubled Family Life Pillars Support Boss Wants Poster Intently Injured Relationship Crisis Serve Just Food Swords GAME Nine Six
Both All Each Every Some Many Other Another""".split())
GENERIC = set("""the one love home time life lies money back again free more stay forever better baby girl boy man woman night day
alone world dance tonight heaven paradise dream dreams fire gold golden blue red black white wild queen king star stars hero heroes
rust home games game football season news live show music movie film series""".split())


def norm_name(s):
    s = re.sub(r"\s*\((?:[^()]*\b(?:film|series|miniseries|video game|game|singer|band|rapper|musician|actor|actress|footballer|"
               r"American football|basketball|baseball|soccer|song|album|TV|politician)\b[^()]*|\d{4}[^()]*)\)", "", s, flags=re.I)
    s = re.sub(r"\s*\((feat|with)\.?[^)]*\)|\s+(feat\.|featuring)\s.*$", "", s, flags=re.I)
    s = re.sub(r"[™®©]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def key(s):
    return re.sub(r"[^a-z0-9]+", " ", norm_name(s).lower()).strip()


def mention_re(name):
    k = key(name)
    w = k.split()
    if not w or len(k) < 4 or k in GENERIC or (len(w) == 1 and len(k) < 6):
        return None
    return re.compile(r"(?<![a-z0-9])" + r" ".join(map(re.escape, w)) + r"(?![a-z0-9])")


def split_artists(s):
    parts = re.split(r"\s*(?:&|,| x | X |\bFeaturing\b|\bfeat\.?|\bwith\b|\band\b)\s*", s or "")
    return [p.strip() for p in parts if len(p.strip()) > 2]


def soompi_entities(news):
    """Từ tiêu đề Soompi: tên idol/nhóm nhạc (cụm 2-3 chữ viết hoa hoặc tên VIẾT HOA) và tên K-drama/show (trong ngoặc kép)."""
    from collections import Counter
    people, shows = Counter(), Counter()
    for n in news:
        if n.get("outlet") != "Soompi (K-pop)":
            continue
        t = n.get("title") or ""
        for q in re.findall(r"[“\"]([^”\"]{2,60})[”\"]", t):
            shows[q.strip()] += 1
        rest = re.sub(r"[“\"][^”\"]*[”\"]", " | ", t)
        rest = re.sub(r"[’']s\b", "", rest)
        rest = re.sub(r"^\s*(Watch|Exclusive|Update|Breaking)\s*:", "", rest)
        seen = set()
        for seg in re.split(r",|\+|\||:|\b(?:And|With|In|For|By|To|Of|On|As|At|From|Vs\.?)\b", rest):
            words = seg.split()
            run = []
            for w in words:
                w2 = w.strip(".!?()")
                if w2 and (w2[0].isupper() or w2[0].isdigit()) and w2 not in TITLE_STOP and not re.fullmatch(r"\d+(st|nd|rd|th)?", w2):
                    run.append(w2)
                else:
                    break
            name = " ".join(run[:3])
            ok = (2 <= len(run) <= 3) or (len(run) == 1 and (run[0].isupper() and len(run[0]) >= 3 or len(words) > 1))
            if run and ok and name not in seen and len(name) >= 3:
                people[name] += 1; seen.add(name)
    return people.most_common(25), shows.most_common(15)


def domain_rankings(dom, extra_news=()):
    """dom = snapshot['domains']; trả về dict domain -> {top, charts, wiki, news}"""
    if not dom:
        return {}
    news_all = list(dom.get("news", [])) + list(extra_news)
    to_txt = lambda n: " " + re.sub(r"[^a-z0-9]+", " ", (n.get("title") or "").lower()) + " "
    news_txt = [(n, to_txt(n)) for n in news_all]
    social = (dom.get("social") or {}).get("posts", [])
    soc_txt = [(p, to_txt(p)) for p in social]
    out = {}
    for d in ORDER:
        if d == "season":
            out[d] = season_block(dom, news_txt, soc_txt)
            continue
        ents = {}
        # tác phẩm (bài hát, phim, game...) chỉ đếm tin cùng lĩnh vực để tránh nhầm tên chung chung
        dom_txt = [(n, t) for n, t in news_txt if n.get("domain") == d]

        def ent(name, **kw):
            k = key(name)
            if not k:
                return None
            e = ents.setdefault(k, {"name": norm_name(name), "key": k, "charts": [], "wiki": None, "subs": set(), "url": None})
            if kw.get("url") and not e["url"]:
                e["url"] = kw["url"]
            return e

        wiki = [w for w in dom.get("wiki", []) if w["domain"] == d]
        for w in wiki:
            e = ent(w["title"], url=w["url"])
            if e and not e["wiki"]:
                e["wiki"] = {"views": w["views"], "change": w["change"], "is_new": w["is_new"], "desc": w["desc"]}
        charts = defaultdict(list)
        for c in dom.get("charts", []):
            if c["domain"] != d:
                continue
            charts[c["chart"]].append(c)
        if d in ("idol", "tv"):
            kp, ks = soompi_entities(dom.get("news", []))
            src = kp if d == "idol" else ks
            name = "Idol & sao Hàn được nhắc nhiều (Soompi)" if d == "idol" else "K-drama & show Hàn đang hot (Soompi)"
            if src:
                charts[name] = [{"rank": i, "title": p, "sub": f"{c} tin", "url": "https://www.soompi.com/search?query=" + urllib.parse.quote(p)}
                                for i, (p, c) in enumerate(src, 1)]
        chart_len = {k: len(v) for k, v in charts.items()}
        for cname, rows in charts.items():
            for c in rows:
                e = ent(c["title"], url=c.get("url"))
                if not e:
                    continue
                e["work"] = True
                e["charts"].append({"chart": cname, "rank": c["rank"], "n": chart_len[cname]})
                if c.get("sub") and not c["sub"].startswith(("$", "CCU")) and "đang chơi" not in c["sub"]:
                    e["subs"].add(c["sub"])
                if d == "music":  # nghệ sĩ cũng là 1 trend
                    for a in split_artists(c.get("sub")):
                        ea = ent(a)
                        if ea:
                            ea["charts"].append({"chart": cname + " (nghệ sĩ)", "rank": c["rank"], "n": chart_len[cname]})
        # đếm số tin nhắc tới
        for e in ents.values():
            rx = mention_re(e["name"])
            pool = dom_txt if (e.get("work") and not e["wiki"]) or len(e["key"].split()) == 1 else news_txt
            hits = [n for n, t in pool if rx and rx.search(t)] if rx else []
            e["mentions"] = len(hits)
            e["examples"] = [{"title": n["title"], "url": n["url"], "outlet": n.get("outlet")} for n in hits[:3]]
            spool = [(p, t) for p, t in soc_txt if p["domain"] == d] if pool is dom_txt else soc_txt
            sh = [p for p, t in spool if rx and rx.search(t)] if rx else []
            e["social"] = len(sh)
            e["social_eng"] = sum(p.get("engagement", 0) for p in sh)
            e["social_ex"] = [{"title": p["title"][:160], "url": p["url"], "source": p["source"], "eng": p.get("engagement", 0)}
                              for p in sorted(sh, key=lambda p: -p.get("engagement", 0))[:3]]
        maxv = max([e["wiki"]["views"] for e in ents.values() if e["wiki"]] or [1])
        maxm = max([e["mentions"] for e in ents.values()] or [1]) or 1
        maxs = max([e["social_eng"] for e in ents.values()] or [1]) or 1
        rows = []
        for e in ents.values():
            ws = math.sqrt(e["wiki"]["views"] / maxv) if e["wiki"] else 0
            if e["wiki"] and (e["wiki"]["is_new"] or (e["wiki"]["change"] or 0) >= 2):
                ws = min(1.0, ws + 0.15)
            cs = max([1 - (c["rank"] - 1) / max(c["n"], 1) for c in e["charts"]] or [0])
            ns = math.sqrt(e["mentions"] / maxm)
            ss = math.sqrt(e["social_eng"] / maxs) if e["social"] else 0
            n_sig = (1 if e["wiki"] else 0) + (1 if e["charts"] else 0) + (1 if e["mentions"] else 0) + (1 if e["social"] else 0)
            score = (0.32 * ws + 0.25 * ns + 0.2 * cs + 0.23 * ss + 0.06 * (n_sig - 1)) / 1.18
            if score <= 0:
                continue
            best = sorted(e["charts"], key=lambda c: c["rank"])[:2]
            rows.append({"name": e["name"], "key": e["key"], "score": round(score * 100), "url": e["url"],
                         "wiki": e["wiki"], "charts": best, "mentions": e["mentions"], "examples": e["examples"],
                         "sub": ", ".join(sorted(e["subs"]))[:80], "signals": n_sig,
                         "social": e["social"], "social_eng": e["social_eng"], "social_ex": e["social_ex"]})
        rows.sort(key=lambda r: (r["score"], r["mentions"]), reverse=True)
        seen, news = set(), []
        for n in sorted([n for n in dom.get("news", []) if n["domain"] == d], key=lambda n: n.get("published") or "", reverse=True):
            k = (n["title"] or "").lower()[:80]
            if k in seen:
                continue
            seen.add(k); news.append(n)
        soc_d = sorted([p for p in social if p["domain"] == d], key=lambda p: -p.get("engagement", 0))
        out[d] = {"top": rows[:25],
                  "social": [{k: p.get(k) for k in ("source", "title", "url", "author", "likes", "reposts", "replies", "views", "engagement", "ago", "published")} for p in soc_d[:20]],
                  "charts": {k: [{"rank": c["rank"], "title": c["title"], "sub": c.get("sub", ""), "url": c.get("url")} for c in v[:15]] for k, v in charts.items()},
                  "wiki": [{"title": w["title"], "desc": w["desc"], "views": w["views"], "change": w["change"], "is_new": w["is_new"], "url": w["url"]} for w in wiki[:20]],
                  "news": news[:30], "n_news": len(news)}
    return out


SEASON_STOP = set("""halloween thanksgiving christmas black friday cyber monday day dead new year eve trend trends viral tiktok 2026 2025
best ideas idea easy diy last minute minute top get make made makes our your you this that with for and the how what why new""".split())


def _phrases(texts, n=15):
    from collections import Counter
    stop = set("""a an the and or of to in on at by for with from is are was be it its this that my your our their you we i he she they
    me us so not no do does did has have had will just can how why what when who all any more most new best top get gets got make
    one two first last year day days week time people like look really still even also back much many every here there amp""".split())
    c = Counter()
    for t in texts:
        t = re.sub(r"https?://\S+|www\.\S+|\S+\.(com|net|org)\S*", " ", (t or "").lower())
        ws = [w.strip("'-") for w in re.findall(r"[a-z][a-z'\-]+", t)]
        seen = set()
        for i in range(len(ws) - 1):
            a, b = ws[i], ws[i + 1]
            if a in stop or b in stop or a in SEASON_STOP and b in SEASON_STOP or len(a) < 3 or len(b) < 3:
                continue
            ph = a + " " + b
            if ph not in seen:
                c[ph] += 1; seen.add(ph)
    return [(p, k) for p, k in c.most_common(n * 2) if k >= 2][:n]


def season_block(dom, news_txt, soc_txt):
    hols = (dom.get("social") or {}).get("holidays") or []
    blocks = []
    for h in hols:
        nm = h["name"]
        news = [n for n, t in news_txt if n.get("holiday") == nm]
        posts = [p for p, t in soc_txt if p.get("holiday") == nm]
        low = nm.lower()
        if not news and not posts:
            news = [n for n, t in news_txt if low in t]
        ph = _phrases([n["title"] for n in news] + [p["title"] for p in posts])
        blocks.append({"name": nm, "date": h["date"], "days_left": h["days_left"], "n_news": len(news), "n_social": len(posts),
                       "phrases": ph,
                       "news": [{"title": n["title"], "url": n["url"], "outlet": n.get("outlet"), "published": n.get("published")}
                                for n in sorted(news, key=lambda n: n.get("published") or "", reverse=True)[:10]],
                       "social": [{k: p.get(k) for k in ("source", "title", "url", "author", "likes", "reposts", "replies", "views", "engagement", "ago")}
                                  for p in sorted(posts, key=lambda p: -p.get("engagement", 0))[:12]]})
    # dạng 'top' để hiển thị chung với các lĩnh vực khác
    top = []
    for b in blocks:
        if b["n_news"] or b["n_social"]:
            top.append({"name": f"{b['name']} ({'còn ' + str(b['days_left']) + ' ngày' if b['days_left'] >= 0 else 'vừa qua'})", "key": key(b["name"]),
                        "score": min(100, 40 + b["n_news"] // 5 + b["n_social"] // 3), "url": None, "wiki": None, "charts": [],
                        "mentions": b["n_news"], "examples": b["news"][:2], "sub": ", ".join(p for p, _ in b["phrases"][:6]),
                        "signals": 2, "social": b["n_social"], "social_eng": sum(p.get("engagement") or 0 for p in b["social"]), "social_ex": b["social"][:3]})
    wiki = [{"title": w["title"], "desc": w["desc"], "views": w["views"], "change": w["change"], "is_new": w["is_new"], "url": w["url"]}
            for w in dom.get("wiki", []) if w["domain"] == "season"]
    return {"top": top, "holidays": blocks, "charts": {}, "wiki": wiki[:15], "news": [], "social": [], "n_news": sum(b["n_news"] for b in blocks)}


# ---------------- Gợi ý sản phẩm tự động từ trend ----------------
ANGLES = {
    "game": [("Phụ kiện gaming theo phong cách game", "{n} inspired gaming accessories"), ("Áo/hoodie gamer (thiết kế riêng, không logo)", "{n} gamer hoodie")],
    "sports": [("Đồ cổ động: áo, mũ, cờ, móc khoá", "{n} fan gear")],
    "music": [("Áo phong cách tour/concert (không dùng hình nghệ sĩ khi chưa có license)", "{n} concert outfit"), ("Phụ kiện đi concert", "{n} concert accessories")],
    "idol": [("Phụ kiện fan: photocard holder, bag charm, sticker", "{n} fan merch")],
    "film": [("Hoá trang / cosplay theo nhân vật", "{n} costume"), ("Áo/poster lấy cảm hứng phim", "{n} inspired shirt")],
    "tv": [("Hoá trang & áo in câu thoại fan", "{n} costume"), ("Merch lấy cảm hứng series", "{n} merch")],
    "books": [("Merch bookish: bookmark, nến, tote", "{n} bookmark")],
    "season": [("Trang trí & quà theo mùa", "{n} decor"), ("Trang phục / phụ kiện theo mùa", "{n} outfit")],
}


def auto_ideas(rankings, per_domain=4):
    ideas = []
    for d, v in rankings.items():
        if d not in ANGLES:
            continue
        if d == "season":
            for b in v.get("holidays", [])[:4]:
                if b["days_left"] < 0:
                    continue
                for label, tpl in ANGLES[d]:
                    q = tpl.format(n=b["name"])
                    ideas.append({"domain": d, "trend": b["name"], "angle": label, "query": q, "score": 60,
                                  "why": f"Còn {b['days_left']} ngày; {b['n_news']} tin, {b['n_social']} bài MXH. Cụm nổi: " + ", ".join(p for p, _ in b["phrases"][:5])})
            continue
        cands = [r for r in v["top"] if r["signals"] >= 2 and not re.search(r"documentary|died|\(\d{4}.\d{4}\)", (r.get("wiki") or {}).get("desc") or "")]
        for r in cands[:per_domain]:
            for label, tpl in ANGLES[d][:1 if r["score"] < 50 else 2]:
                why = []
                if r.get("wiki"): why.append(f"{r['wiki']['views']:,} lượt xem Wikipedia")
                if r.get("charts"): why.append("#" + str(r["charts"][0]["rank"]) + " " + r["charts"][0]["chart"])
                if r.get("mentions"): why.append(f"{r['mentions']} tin")
                if r.get("social"): why.append(f"{r['social']} bài MXH")
                ideas.append({"domain": d, "trend": r["name"], "angle": label, "query": tpl.format(n=r["name"]), "score": r["score"],
                              "why": "; ".join(why)})
    return sorted(ideas, key=lambda i: (i["domain"] != "season", -i["score"]))


def mark_new(cur, prev):
    """đánh dấu trend mới lọt top so với lần quét trước"""
    for d, v in cur.items():
        pk = {r["key"] for r in prev.get(d, {}).get("top", [])} if prev else None
        for i, r in enumerate(v["top"]):
            r["is_new_top"] = (pk is not None and r["key"] not in pk)


def meta():
    m = {d: {"label": DOMAINS[d]["label"], "icon": DOMAINS[d]["icon"]} for d in ORDER}
    return m


def classify_trend(item, rankings=None):
    """Google Trends: khớp với trend của các lĩnh vực trước, rồi tới từ khoá"""
    k = key(item.get("title") or "")
    if rankings and k:
        for d, v in rankings.items():
            for r in v["top"] + [{"key": key(w["title"])} for w in v["wiki"]]:
                if r["key"] == k or (len(k) >= 5 and (r["key"].startswith(k) or k in r["key"].split(" ", 1)[0])):
                    return d
    if re.search(r"halloween|thanksgiving|christmas|black friday|costume", (item.get("title") or "").lower()):
        return "season"
    return (classify_text(item.get("wiki_desc") or "") or classify_text(item.get("title") or "")
            or classify_text(" ".join((n.get("title") or "") for n in item.get("news", []) or [])) or "other")
