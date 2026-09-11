#!/usr/bin/env python3
"""偵查工具：看一個網址到底長什麼樣，好決定 sources.yml 要怎麼寫。

    python scraper/sniff.py https://www.academictransfer.com/en/jobs/ ...

會印出：HTTP 狀態、是不是 feed、有沒有 JSON-LD JobPosting、
連結網址的形狀統計（把數字換成 {n} 之後分群），以及職缺樣本標題。
"""
from __future__ import annotations

import os
import re
import sys
from collections import Counter
from urllib.parse import urljoin, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run  # noqa: E402

from bs4 import BeautifulSoup  # noqa: E402

JOBISH = re.compile(r"job|vacan|vacature|stelle|career|position|anstall|anställ|ledig|phd|promov|offre", re.I)


def shape(path: str) -> str:
    path = re.sub(r"\d+", "{n}", path)
    return re.sub(r"[0-9a-f]{8,}", "{hex}", path)


def sniff(url: str) -> None:
    print("=" * 78)
    print("URL:", url)
    try:
        html = run.fetch(url, 30)
    except Exception as exc:  # noqa: BLE001
        print("  抓取失敗：", exc)
        return
    print(f"  長度 {len(html)} bytes")
    head = html[:200].lstrip().lower()
    if head.startswith("<?xml") or "<rss" in head or "<feed" in head:
        print("  看起來是 XML/RSS feed")
        import feedparser
        feed = feedparser.parse(html)
        print(f"  feed 條目數：{len(feed.entries)}")
        for entry in feed.entries[:8]:
            print(f"    · {entry.get('title','')[:80]}  ->  {entry.get('link','')}")
        return

    soup = BeautifulSoup(html, "lxml")
    print("  <title>:", run.clean(soup.title.get_text() if soup.title else "")[:100])

    feeds = [l.get("href") for l in soup.find_all("link", rel=True)
             if "alternate" in " ".join(l.get("rel")) and "xml" in (l.get("type") or "")]
    if feeds:
        print("  頁面自己宣告的 feed：")
        for feed_url in feeds[:6]:
            print("    ", urljoin(url, feed_url))

    endpoints = Counter()
    for match in re.finditer(r"""https?://[^"'\s<>\\]{10,160}""", html):
        candidate = match.group(0)
        if re.search(r"/api/|graphql|\.json|/rss|/feed|search\?|/jobs\?", candidate, re.I):
            endpoints[candidate.rstrip("\\")] += 1
    if endpoints:
        print("  頁面裡出現的 API / feed 網址：")
        for candidate, count in endpoints.most_common(12):
            print(f"    {count:>3}  {candidate[:140]}")

    if os.environ.get("SNIFF_TEXT"):
        print("  --- 頁面可見文字前 2000 字 ---")
        print("  " + run.clean(soup.get_text(" "))[:2000])
        print("  --- 文字結束 ---")

    ld = run.extract_jsonld(html)
    print(f"  JSON-LD JobPosting：{len(ld)} 個")
    for node in ld[:3]:
        fields = run.jsonld_to_fields(node)
        print(f"    · {fields['title'][:70]} | {fields['university'][:30]} | {fields['deadline']} | {node.get('url','')}")

    anchors = [(a["href"], run.clean(a.get_text(" "))) for a in soup.find_all("a", href=True)]
    print(f"  連結總數：{len(anchors)}")
    shapes = Counter()
    samples: dict[str, tuple[str, str]] = {}
    for href, text in anchors:
        absolute = urljoin(url, href)
        parsed = urlparse(absolute)
        if parsed.netloc and parsed.netloc not in urlparse(url).netloc and not JOBISH.search(absolute):
            continue
        key = f"{parsed.netloc}{shape(parsed.path)}"
        shapes[key] += 1
        samples.setdefault(key, (absolute, text))
    print("  連結形狀（出現次數 / 形狀 / 樣本）：")
    for key, count in shapes.most_common(25):
        link, text = samples[key]
        flag = "  <-- 像職缺" if JOBISH.search(key) else ""
        print(f"    {count:>4}  {key[:70]}{flag}")
        if flag:
            print(f"          樣本：{link[:100]}")
            print(f"          文字：{text[:90]!r}")
    if len(anchors) < 10:
        print("  ⚠ 連結很少，可能要 JS 才渲染得出來，或被擋。前 400 字：")
        print("   ", run.clean(soup.get_text(" "))[:400])


if __name__ == "__main__":
    for target in sys.argv[1:]:
        sniff(target)
