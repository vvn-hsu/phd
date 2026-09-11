#!/usr/bin/env python3
"""抓取各校博士職缺，輸出 data/jobs.json 給網頁讀。

用法：
    python scraper/run.py            # 正式執行，寫入 data/jobs.json
    python scraper/run.py --probe    # 只測試各來源抓不抓得到，不寫檔
    python scraper/run.py --only tudelft,euraxess
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import traceback
from datetime import date, datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
import yaml
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "jobs.json")
CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources.yml")

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 phd-vacancy-tracker/1.0 (personal job alert)"
)
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept-Language": "en,nl;q=0.8"})

# 只留博士職缺用的樣式
PHD_STRONG = re.compile(
    r"(\bph\.?\s?d\b|\bphd|promovend|doktorand|doctorant|dottorand|"
    r"(?<!post)(?<!post-)(?<!post )doctoral\s+"
    r"(student|candidate|researcher|position|fellow|program|school)|"
    r"early\s+stage\s+researcher|\besr\b)",
    re.I,
)
PHD_WEAK = re.compile(r"(\bdoctoral\b|\bdoctorate\b|research\s+student)", re.I)
POSTDOC = re.compile(r"(post[\s\-]?doc|postdoctoral|post[\s\-]?doctoral)", re.I)

KEEP_CLOSED_DAYS = 45  # 職缺從列表消失後，還在資料裡保留幾天


# --------------------------------------------------------------------------- 工具

def log(msg: str) -> None:
    print(msg, flush=True)


def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def job_id(url: str) -> str:
    canon = re.sub(r"[?#].*$", "", (url or "").rstrip("/").lower())
    return hashlib.sha1(canon.encode("utf-8")).hexdigest()[:16]


def clean(text: str | None) -> str:
    if not text:
        return ""
    text = BeautifulSoup(text, "html.parser").get_text(" ") if "<" in text else text
    return re.sub(r"\s+", " ", text).strip()


def in_range(year: int) -> bool:
    return 2000 <= year <= date.today().year + 5


def parse_date(value) -> str:
    if not value:
        return ""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    if isinstance(value, dict):
        value = value.get("startDate") or value.get("value") or ""
    text = str(value).strip()
    iso = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)  # ISO 先處理，免得被當成日/月
    if iso:
        try:
            parsed = date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            return ""
        return parsed.isoformat() if in_range(parsed.year) else ""
    try:
        dt = dateparser.parse(text, dayfirst=True, fuzzy=True)
    except (ValueError, OverflowError, TypeError):
        return ""
    if not dt:
        return ""
    if not in_range(dt.year):
        return ""
    return dt.date().isoformat()


def is_phd(title: str, extra: str = "") -> bool:
    blob = f"{title} {extra}"
    if PHD_STRONG.search(blob):
        return True
    if POSTDOC.search(blob):
        return False
    return bool(PHD_WEAK.search(blob))


def fetch(url: str, timeout: int = 30) -> str:
    """抓網頁。4xx 直接放棄（重試也是一樣的結果），只有連線問題和 5xx/429 才重試。"""
    last = None
    for attempt in range(2):
        try:
            resp = SESSION.get(url, timeout=timeout, allow_redirects=True)
            if resp.status_code == 200:
                return resp.text
            last = f"HTTP {resp.status_code}"
            if 400 <= resp.status_code < 500 and resp.status_code != 429:
                break
        except requests.RequestException as exc:
            last = f"{type(exc).__name__}: {str(exc)[:120]}"
        if attempt == 0:
            time.sleep(2)
    raise RuntimeError(last or "unknown error")


# --------------------------------------------------------------------------- 解析

def extract_jsonld(html: str) -> list[dict]:
    """把頁面裡所有 schema.org JobPosting 挖出來。"""
    out: list[dict] = []
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        raw = tag.string or tag.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        stack = [payload]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                types = node.get("@type") or node.get("type") or ""
                types = types if isinstance(types, list) else [types]
                if any(str(t).lower() == "jobposting" for t in types):
                    out.append(node)
                for value in node.values():
                    if isinstance(value, (dict, list)):
                        stack.append(value)
    return out


def jsonld_to_fields(node: dict) -> dict:
    org = node.get("hiringOrganization") or {}
    if isinstance(org, list):
        org = org[0] if org else {}
    loc = node.get("jobLocation") or {}
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    address = (loc or {}).get("address") or {}
    if isinstance(address, list):
        address = address[0] if address else {}
    city = clean(address.get("addressLocality") if isinstance(address, dict) else "")
    country = clean(address.get("addressCountry") if isinstance(address, dict) else "")
    if isinstance(country, str) and len(country) > 3:
        country = country[:20]
    return {
        "title": clean(node.get("title")),
        "university": clean(org.get("name") if isinstance(org, dict) else ""),
        "location": ", ".join(p for p in (city, country) if p),
        "department": clean(node.get("employmentUnit", {}).get("name")
                            if isinstance(node.get("employmentUnit"), dict) else ""),
        "posted": parse_date(node.get("datePosted")),
        "deadline": parse_date(node.get("validThrough")),
        "employment": clean(node.get("employmentType") if isinstance(node.get("employmentType"), str) else ""),
        "summary": clean(node.get("description"))[:400],
    }


def page_fallback_fields(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    title = ""
    if soup.find("h1"):
        title = clean(soup.find("h1").get_text(" "))
    if not title:
        meta = soup.find("meta", attrs={"property": "og:title"})
        if meta:
            title = clean(meta.get("content"))
    if not title and soup.title:
        title = clean(soup.title.get_text())
    desc = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta", attrs={"property": "og:description"}
    )
    text = clean(soup.get_text(" "))
    deadline = ""
    m = re.search(
        r"(?:deadline|apply before|closing date|sluitingsdatum|reageren voor|"
        r"application deadline)[^\d]{0,40}(\d{1,2}[\s\-/\.][\w]{2,12}[\s\-/\.]\d{2,4}|\d{4}-\d{2}-\d{2})",
        text, re.I,
    )
    if m:
        deadline = parse_date(m.group(1))
    return {
        "title": title,
        "summary": clean(desc.get("content"))[:400] if desc else "",
        "deadline": deadline,
    }


# --------------------------------------------------------------------------- adapters

def harvest_links(soup, base: str, pattern, seen: dict[str, dict]) -> None:
    """把頁面上符合 pattern 的職缺連結收進 seen。"""
    for anchor in soup.find_all("a", href=True):
        absolute = urljoin(base, anchor["href"])
        if not pattern.search(absolute):
            continue
        title = clean(anchor.get_text(" ")) or clean(anchor.get("title") or "")
        if len(title) < 6:
            continue
        key = job_id(absolute)
        if key not in seen:
            seen[key] = {"url": absolute, "title": title}


def sample_hrefs(soup, base: str, limit: int = 12) -> list[str]:
    """列出頁面上像職缺的連結，用來猜 link_pattern。"""
    jobish = re.compile(r"job|vacan|vacature|stelle|career|position|anstall|ledig|phd|promov", re.I)
    shapes: dict[str, str] = {}
    for anchor in soup.find_all("a", href=True):
        absolute = urljoin(base, anchor["href"])
        path = urlparse(absolute).path
        if not jobish.search(absolute):
            continue
        key = re.sub(r"\d+", "{n}", f"{urlparse(absolute).netloc}{path}")
        shapes.setdefault(key, absolute)
        if len(shapes) >= limit:
            break
    return [f"{k}   例：{v[:90]}" for k, v in shapes.items()] or ["（找不到任何像職缺的連結，頁面可能要 JS 才渲染）"]


def adapter_links(source: dict, cfg: dict) -> tuple[list[dict], str]:
    pattern = re.compile(source["link_pattern"])
    timeout = source.get("timeout", cfg["timeout"])
    pages = max(1, int(source.get("pages", 1)))
    page_param = source.get("page_param", "page")
    page_start = int(source.get("page_start", 0))
    errors = []
    for url in source["urls"]:
        try:
            html = fetch(url, timeout)
        except Exception as exc:  # noqa: BLE001 - 換下一個候選網址
            errors.append(f"{url} -> {exc}")
            continue
        soup = BeautifulSoup(html, "lxml")
        seen: dict[str, dict] = {}
        harvest_links(soup, url, pattern, seen)
        # 列表頁沒東西就試下一個候選網址；JSON-LD 有時直接掛在列表頁上
        for node in extract_jsonld(html):
            fields = jsonld_to_fields(node)
            link = node.get("url") or node.get("sameAs") or ""
            if isinstance(link, list):
                link = link[0] if link else ""
            link = urljoin(url, str(link)) if link else ""
            if not link or not fields["title"]:
                continue
            key = job_id(link)
            record = seen.setdefault(key, {"url": link, "title": fields["title"]})
            record.update({k: v for k, v in fields.items() if v})
        if seen and pages > 1:
            # 有分頁就往後翻，翻到沒有新職缺為止
            for page in range(page_start + 1, page_start + pages):
                joiner = "&" if "?" in url else "?"
                next_url = f"{url}{joiner}{page_param}={page}"
                before = len(seen)
                try:
                    extra_soup = BeautifulSoup(fetch(next_url, timeout), "lxml")
                except Exception as exc:  # noqa: BLE001 - 翻頁失敗就用已經抓到的
                    log(f"       ↳ 第 {page} 頁抓取失敗：{exc}")
                    break
                harvest_links(extra_soup, next_url, pattern, seen)
                if len(seen) == before:
                    break
                time.sleep(0.5)
        if seen:
            return list(seen.values()), url
        errors.append(f"{url} -> 0 links matched")
        log(f"       ↳ {url} 抓到 {len(soup.find_all('a', href=True))} 個連結但沒有符合 "
            f"{source['link_pattern']!r}；可能的職缺連結：")
        for sample in sample_hrefs(soup, url):
            log(f"         {sample}")
    raise RuntimeError("; ".join(errors) or "no urls configured")


def adapter_rss(source: dict, cfg: dict) -> tuple[list[dict], str]:
    import feedparser

    errors = []
    for url in source["urls"]:
        try:
            raw = fetch(url, source.get("timeout", cfg["timeout"]))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{url} -> {exc}")
            continue
        feed = feedparser.parse(raw)
        items = []
        for entry in feed.entries:
            link = entry.get("link") or ""
            title = clean(entry.get("title"))
            if not link or not title:
                continue
            items.append({
                "url": link,
                "title": title,
                "posted": parse_date(entry.get("published") or entry.get("updated")),
                "summary": clean(entry.get("summary", ""))[:400],
            })
        if items:
            return items, url
        errors.append(f"{url} -> empty feed")
    raise RuntimeError("; ".join(errors) or "no urls configured")


def adapter_jsonld(source: dict, cfg: dict) -> tuple[list[dict], str]:
    errors = []
    for url in source["urls"]:
        try:
            html = fetch(url, source.get("timeout", cfg["timeout"]))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{url} -> {exc}")
            continue
        items = []
        for node in extract_jsonld(html):
            fields = jsonld_to_fields(node)
            link = node.get("url") or ""
            if isinstance(link, list):
                link = link[0] if link else ""
            if not link or not fields["title"]:
                continue
            fields["url"] = urljoin(url, str(link))
            items.append(fields)
        if items:
            return items, url
        errors.append(f"{url} -> no JobPosting JSON-LD")
    raise RuntimeError("; ".join(errors) or "no urls configured")


ADAPTERS = {"links": adapter_links, "rss": adapter_rss, "jsonld": adapter_jsonld}


# --------------------------------------------------------------------------- 主流程

def enrich_job(job: dict, timeout: int) -> None:
    """抓詳細頁補完發布日／截止日／單位。抓不到就維持原樣。"""
    try:
        html = fetch(job["url"], timeout)
    except Exception as exc:  # noqa: BLE001
        job.setdefault("notes", f"詳細頁抓取失敗：{exc}")
        return
    nodes = extract_jsonld(html)
    fields = jsonld_to_fields(nodes[0]) if nodes else page_fallback_fields(html)
    for key, value in fields.items():
        if value and not job.get(key):
            job[key] = value
    if nodes and fields.get("title"):
        job["title"] = fields["title"] or job["title"]


def load_previous() -> dict:
    if not os.path.exists(DATA):
        return {"jobs": []}
    try:
        with open(DATA, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {"jobs": []}


def collect(source: dict, cfg: dict) -> list[dict]:
    adapter = ADAPTERS[source.get("type", "links")]
    items, used_url = adapter(source, cfg)
    source["_used_url"] = used_url
    out = []
    dropped: list[str] = []
    for item in items:
        title = clean(item.get("title"))
        if not title:
            continue
        if source.get("filter", cfg["filter"]) == "phd" and not is_phd(title, item.get("summary", "")):
            dropped.append(title)
            continue
        record = {
            "id": job_id(item["url"]),
            "source": source["id"],
            "source_name": source["name"],
            "university": item.get("university") or source["name"],
            "country": source.get("country", ""),
            "title": title,
            "url": item["url"],
            "location": item.get("location", ""),
            "department": item.get("department", ""),
            "posted": item.get("posted", ""),
            "deadline": item.get("deadline", ""),
            "summary": item.get("summary", ""),
        }
        out.append(record)
    if not out and dropped:
        log(f"       ↳ {len(dropped)} 筆都被 PhD 過濾擋掉，樣本標題：")
        for title in dropped[:8]:
            log(f"         · {title[:90]}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true", help="只測試來源，不寫檔")
    ap.add_argument("--only", default="", help="只跑這些來源，逗號分隔")
    ap.add_argument("--no-enrich", action="store_true")
    args = ap.parse_args()

    with open(CONFIG, encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    cfg = config.get("defaults", {})
    cfg.setdefault("filter", "phd")
    cfg.setdefault("max_enrich", 25)
    cfg.setdefault("timeout", 30)

    wanted = {s.strip() for s in args.only.split(",") if s.strip()}
    previous = load_previous()
    known = {job["id"]: job for job in previous.get("jobs", [])}

    fresh: dict[str, dict] = {}
    reports = []
    for source in config["sources"]:
        if not source.get("enabled", True):
            continue
        if wanted and source["id"] not in wanted:
            continue
        started = time.time()
        try:
            found = collect(source, cfg)
            for job in found:
                fresh.setdefault(job["id"], job)
            reports.append({
                "id": source["id"], "name": source["name"], "country": source.get("country", ""),
                "homepage": source.get("homepage", ""), "status": "ok" if found else "empty",
                "count": len(found), "url_used": source.get("_used_url", ""), "error": "",
            })
            log(f"[ok]   {source['id']:<18} {len(found):>4} 筆  ({time.time()-started:.1f}s)  {source.get('_used_url','')}")
            for job in found[:3]:
                log(f"         · {job['title'][:90]}")
        except Exception as exc:  # noqa: BLE001 - 單一來源掛掉不影響其他來源
            reports.append({
                "id": source["id"], "name": source["name"], "country": source.get("country", ""),
                "homepage": source.get("homepage", ""), "status": "error", "count": 0,
                "url_used": "", "error": str(exc)[:400],
            })
            log(f"[FAIL] {source['id']:<18} {exc}")
            if os.environ.get("DEBUG"):
                traceback.print_exc()

    if args.probe:
        log("\n--- probe 摘要 ---")
        for r in reports:
            log(f"{r['status']:<6} {r['id']:<18} {r['count']:>4}  {r['error'][:160]}")
        log(f"合計 {len(fresh)} 筆去重後職缺")
        return 0

    stamp = today()
    to_enrich = [j for j in fresh.values() if j["id"] not in known][: cfg["max_enrich"]]
    if not args.no_enrich:
        log(f"補抓 {len(to_enrich)} 個新職缺的詳細頁…")
        for job in to_enrich:
            enrich_job(job, cfg["timeout"])
            time.sleep(0.7)

    merged: dict[str, dict] = {}
    for job in fresh.values():
        old = known.get(job["id"], {})
        job["first_seen"] = old.get("first_seen") or stamp
        job["last_seen"] = stamp
        job["status"] = "open"
        # 舊資料裡補過的欄位不要被空值蓋掉
        for key in ("posted", "deadline", "location", "department", "summary", "university"):
            if not job.get(key) and old.get(key):
                job[key] = old[key]
        merged[job["id"]] = job

    disappeared = 0
    for jid, old in known.items():
        if jid in merged:
            continue
        last_seen = old.get("last_seen") or old.get("first_seen") or stamp
        try:
            age = (date.fromisoformat(stamp) - date.fromisoformat(last_seen)).days
        except ValueError:
            age = 0
        if age <= KEEP_CLOSED_DAYS:
            old["status"] = "closed"
            merged[jid] = old
            disappeared += 1

    jobs = sorted(
        merged.values(),
        key=lambda j: (j.get("first_seen", ""), j.get("posted", ""), j.get("title", "")),
        reverse=True,
    )
    new_today = sum(1 for j in jobs if j.get("first_seen") == stamp and j.get("status") == "open")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "date": stamp,
        "counts": {
            "open": sum(1 for j in jobs if j.get("status") == "open"),
            "new_today": new_today,
            "closed_kept": disappeared,
        },
        "sources": reports,
        "jobs": jobs,
    }
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    with open(DATA, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    log(f"\n寫入 {DATA}：{payload['counts']['open']} 筆開放中，今天新增 {new_today} 筆，"
        f"{disappeared} 筆已下架但保留")
    ok_sources = sum(1 for r in reports if r["status"] == "ok")
    log(f"來源狀態：{ok_sources}/{len(reports)} 正常")
    return 0


if __name__ == "__main__":
    sys.exit(main())
