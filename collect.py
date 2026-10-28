"""TrendScout - thu thập tín hiệu xu hướng thị trường Mỹ từ nguồn miễn phí.
Nguồn: Google Trends (RSS trending US), Google News (RSS theo từ khoá) + domains.py (Wikipedia, chart, Bluesky, YouTube...).
Chạy: .venv\\Scripts\\python.exe collect.py
"""
import json, time, base64, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))
RAW = ROOT / "data" / "raw"; RAW.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TrendScout/0.1"
HT = "{https://trends.google.com/trending/rss}"


def fetch(url, headers=None, data=None, timeout=30):
    h = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h, data=data)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def iso(pub):
    try:
        return parsedate_to_datetime(pub).astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def google_trends():
    out = []
    root = ET.fromstring(fetch("https://trends.google.com/trending/rss?geo=US"))
    for it in root.iter("item"):
        traffic = (it.findtext(HT + "approx_traffic") or "0").replace(",", "").replace("+", "")
        news = [{"title": n.findtext(HT + "news_item_title"), "url": n.findtext(HT + "news_item_url"),
                 "source": n.findtext(HT + "news_item_source")} for n in it.findall(HT + "news_item")]
        out.append({"source": "google_trends", "platform": "google", "kind": "search_trend",
                    "title": it.findtext("title"), "score": int(traffic) if traffic.isdigit() else 0,
                    "url": news[0]["url"] if news else "https://trends.google.com/trending?geo=US",
                    "published": iso(it.findtext("pubDate") or ""), "news": news[:3],
                    "picture": it.findtext(HT + "picture")})
    return out


def google_news(query, group):
    q = f'{query} when:{CFG.get("news_window", "7d")}'
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"})
    root = ET.fromstring(fetch(url))
    out = []
    for it in root.iter("item"):
        title = it.findtext("title") or ""
        src = it.findtext("source") or ""
        if src and title.endswith(" - " + src):
            title = title[: -len(src) - 3]
        out.append({"source": "google_news", "platform": "news", "kind": group, "query": query,
                    "title": title, "url": it.findtext("link"), "outlet": src,
                    "published": iso(it.findtext("pubDate") or ""), "score": 0})
    return out


def reddit():
    rc = CFG.get("reddit", {})
    if not rc.get("client_id") or not rc.get("client_secret"):
        return [], "chưa bật – mạng của máy này chặn reddit.com, xem HUONG_DAN.md"
    auth = base64.b64encode(f'{rc["client_id"]}:{rc["client_secret"]}'.encode()).decode()
    tok = json.loads(fetch("https://www.reddit.com/api/v1/access_token",
                           headers={"Authorization": "Basic " + auth, "User-Agent": rc["user_agent"]},
                           data=b"grant_type=client_credentials"))["access_token"]
    out = []
    for sub in rc["subreddits"]:
        try:
            j = json.loads(fetch(f"https://oauth.reddit.com/r/{sub}/top?t=week&limit={rc.get('posts_per_sub', 25)}",
                                 headers={"Authorization": "bearer " + tok, "User-Agent": rc["user_agent"]}))
            for c in j["data"]["children"]:
                d = c["data"]
                out.append({"source": "reddit", "platform": "reddit", "kind": "post", "subreddit": sub,
                            "title": d["title"], "score": d.get("score", 0), "comments": d.get("num_comments", 0),
                            "url": "https://www.reddit.com" + d["permalink"],
                            "published": datetime.fromtimestamp(d["created_utc"], timezone.utc).isoformat()})
        except Exception as e:
            print("  reddit", sub, "lỗi:", e)
        time.sleep(1.2)
    return out, None


def main():
    items, status = [], {}
    try:
        g = google_trends(); items += g; status["google_trends"] = f"ok ({len(g)})"
        try:
            import domains
            lk = domains.wiki_lookup([x["title"] for x in g])
            for x in g:
                if x["title"] in lk:
                    x["wiki_title"] = lk[x["title"]]["title"]; x["wiki_desc"] = lk[x["title"]]["desc"]
        except Exception as e:
            print("  wiki lookup lỗi:", e)
    except Exception as e:
        status["google_trends"] = f"lỗi: {e}"
    n_news = 0
    for group, qs in (("niche", CFG["niches"]), ("buzz", CFG["buzz_queries"])):
        for q in qs:
            try:
                r = google_news(q, group); items += r; n_news += len(r)
            except Exception as e:
                print("  news", q, "lỗi:", e)
            time.sleep(0.8)
    status["google_news"] = f"ok ({n_news})"
    print("Thu thập trend theo lĩnh vực...")
    try:
        import domains
        dom = domains.collect_all()
        status.update({"[lĩnh vực] " + k: v for k, v in dom["status"].items()})
    except Exception as e:
        dom = None; status["lĩnh vực"] = f"lỗi: {e}"
    now = datetime.now(timezone.utc)
    snap = {"collected_at": now.isoformat(), "status": status, "items": items, "domains": dom}
    p = RAW / f"{now.strftime('%Y-%m-%d_%H%M')}.json"
    p.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Đã lưu", p.name, status)


if __name__ == "__main__":
    main()
