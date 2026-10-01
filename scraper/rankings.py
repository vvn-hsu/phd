#!/usr/bin/env python3
"""抓世界大學排名，存成 data/rankings.json 給網頁用。

    python scraper/rankings.py --probe    # 只印出抓到什麼，不寫檔
    python scraper/rankings.py            # 寫入 data/rankings.json（7 天內不重抓）

資料來源是維基百科的排名條目（API 回傳 wikitext，解析表格）。
抓不到就沿用上次的結果，再不然就空的——網頁上沒有排名就不顯示，不會亂編。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run import SESSION, clean  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "rankings.json")
MAX_AGE_DAYS = 7

# 維基百科上有完整名次表格的條目。每個來源試著解析「名次 + 校名」。
SOURCES = [
    ("QS", "QS_World_University_Rankings"),
    ("THE", "Times_Higher_Education_World_University_Rankings"),
    ("ARWU", "Academic_Ranking_of_World_Universities"),
]
API = ("https://en.wikipedia.org/w/api.php?action=parse&page={page}"
       "&prop=wikitext&format=json&formatversion=2")

ROW = re.compile(
    r"^\s*\|\s*(\d{1,3})\s*(?:\|\||\n\s*\|)\s*(?:\{\{[^}]*\}\}\s*)?"
    r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]",
    re.M,
)


def fetch_wikitext(page: str) -> str:
    resp = SESSION.get(API.format(page=page), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("parse", {}).get("wikitext", "") or ""


def parse_ranks(wikitext: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for match in ROW.finditer(wikitext):
        rank = int(match.group(1))
        name = clean(match.group(2))
        if not name or rank > 500:
            continue
        name = re.sub(r"\s*\(.*?\)\s*$", "", name).strip()
        if len(name) < 4 or name.lower().startswith(("file:", "image:")):
            continue
        out.setdefault(name, rank)
    return out


def load_existing() -> dict:
    if not os.path.exists(OUT):
        return {}
    try:
        with open(OUT, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def fresh_enough(existing: dict) -> bool:
    stamp = existing.get("fetched_at", "")
    try:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(stamp)
    except (ValueError, TypeError):
        return False
    return age.days < MAX_AGE_DAYS


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--dump", action="store_true", help="印出 wikitext 的表格片段，用來看格式")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    existing = load_existing()
    if not args.probe and not args.force and fresh_enough(existing):
        print(f"排名資料還很新（{existing.get('fetched_at')}），跳過。")
        return 0

    if args.dump:
        for label, page in SOURCES:
            try:
                text = fetch_wikitext(page)
            except Exception as exc:  # noqa: BLE001
                print(f"[FAIL] {label}: {exc}")
                continue
            print("=" * 70)
            print(f"{label}（{page}）長度 {len(text)}，表格數 {text.count('{|')}")
            idx = text.find("{|")
            while idx != -1:
                chunk = text[idx:idx + 900]
                if re.search(r"rank|Rank", chunk):
                    print(chunk.replace("\n", "\n  ")[:900])
                    break
                idx = text.find("{|", idx + 2)
            else:
                print(text[:600])
        return 0

    tables: dict[str, dict[str, int]] = {}
    for label, page in SOURCES:
        try:
            ranks = parse_ranks(fetch_wikitext(page))
        except Exception as exc:  # noqa: BLE001 - 抓不到就算了
            print(f"[FAIL] {label}（{page}）：{exc}")
            continue
        print(f"[ok]   {label}（{page}）：解析出 {len(ranks)} 所")
        for name, rank in sorted(ranks.items(), key=lambda kv: kv[1])[:8]:
            print(f"         {rank:>3}  {name}")
        if ranks:
            tables[label] = ranks

    if args.probe:
        return 0

    if not tables:
        print("三個來源都沒解析出東西，沿用舊的 data/rankings.json。")
        return 0

    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": "名次解析自英文維基百科的排名條目，僅供排序參考。",
        "tables": tables,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"寫入 {OUT}：" + "、".join(f"{k} {len(v)} 所" for k, v in tables.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
