"""Gop data/history.json cua may nay voi ban tren GitHub (do GitHub Actions ghi), ghi ket qua ra ca 2 noi.
Cach dung: python merge_history.py <duong_dan_history_local> <duong_dan_history_site>"""
import json, sys
from pathlib import Path

local, site = Path(sys.argv[1]), Path(sys.argv[2])
load = lambda p: json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
a, b = load(site), load(local)  # b (may nay) ghi de a (cloud) neu trung ngay
out = {}
for sec in ("niches", "holidays"):
    out[sec] = {}
    for src in (a, b):
        for k, series in (src.get(sec) or {}).items():
            out[sec].setdefault(k, {}).update(series)
dates = sorted({d for sec in out.values() for s in sec.values() for d in s})
keep = set(dates[-35:])
for sec in out.values():
    for s in sec.values():
        for d in [d for d in s if d not in keep]:
            del s[d]
txt = json.dumps(out, ensure_ascii=False)
local.write_text(txt, encoding="utf-8")
site.write_text(txt, encoding="utf-8")
print("  Da gop lich su:", len(dates[-35:]), "ngay")
