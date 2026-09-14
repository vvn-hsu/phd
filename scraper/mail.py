#!/usr/bin/env python3
"""把當天的職缺整理成一封摘要信。

    python scraper/mail.py --dry-run     # 只產生 data/summary.html，不寄信
    python scraper/mail.py               # 有設環境變數才會真的寄

需要的環境變數（GitHub Actions 就是 repository secrets）：
    MAIL_TO    收件人
    MAIL_USER  寄件用的帳號（Gmail 請用「應用程式密碼」，不是登入密碼）
    MAIL_PASS  該帳號的密碼／應用程式密碼
    MAIL_HOST  預設 smtp.gmail.com
    MAIL_PORT  預設 465（SSL）
    MAIL_FROM  預設跟 MAIL_USER 一樣
    SITE_URL   信裡「打開完整清單」的連結
少了 MAIL_TO／MAIL_USER／MAIL_PASS 的話會直接跳過、不當成失敗。
"""
from __future__ import annotations

import argparse
import html
import json
import os
import smtplib
import ssl
import sys
from datetime import date, datetime
from email.message import EmailMessage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "jobs.json")
OUT = os.path.join(ROOT, "data", "summary.html")
SOON_DAYS = 7


def days_to(deadline: str) -> int | None:
    try:
        return (date.fromisoformat(deadline) - date.today()).days
    except (ValueError, TypeError):
        return None


def esc(text) -> str:
    return html.escape(str(text or ""))


def chips(job: dict) -> str:
    out = []
    for tag in job.get("topics") or []:
        out.append(f'<span style="background:#e3f4ea;color:#0f7a4d;border-radius:9px;'
                   f'padding:1px 7px;margin-right:4px;font-size:12px">{esc(tag)}</span>')
    for tag in job.get("tools") or []:
        out.append(f'<span style="background:#e7eefa;color:#1f5fb4;border-radius:9px;'
                   f'padding:1px 7px;margin-right:4px;font-size:12px">{esc(tag)}</span>')
    for tag in job.get("fields") or []:
        out.append(f'<span style="border:1px solid #e3e2dd;color:#6b6a66;border-radius:9px;'
                   f'padding:1px 7px;margin-right:4px;font-size:12px">{esc(tag)}</span>')
    return "".join(out)


def job_block(job: dict, show_tags: bool = True) -> str:
    where = " · ".join(x for x in [job.get("university") or job.get("source_name"),
                                   job.get("city")] if x)
    dd = days_to(job.get("deadline", ""))
    when = ""
    if job.get("deadline"):
        when = f"截止 {job['deadline']}"
        if dd is not None and 0 <= dd <= SOON_DAYS:
            when += f"（剩 {dd} 天）"
    meta = " · ".join(x for x in [where, when] if x)
    score = job.get("topic_score", 0)
    badge = (f'<span style="background:#0f7a4d;color:#fff;border-radius:9px;padding:1px 7px;'
             f'font-size:11px;margin-left:6px">HCI {score}</span>') if score else ""
    return (
        f'<div style="margin:0 0 14px;padding:0 0 12px;border-bottom:1px solid #eee">'
        f'<div style="font-size:15px;font-weight:600;line-height:1.4">'
        f'<a href="{esc(job.get("url"))}" style="color:#1b1b1a;text-decoration:none">'
        f'{esc(job.get("title"))}</a>{badge}</div>'
        f'<div style="color:#6b6a66;font-size:13px;margin:3px 0 5px">{esc(meta)}</div>'
        f'{chips(job) if show_tags else ""}'
        f'</div>'
    )


def build(data: dict, site_url: str) -> tuple[str, str, str]:
    stamp = data.get("date") or date.today().isoformat()
    jobs = [j for j in data.get("jobs", []) if j.get("status") != "closed"]
    thresholds = data.get("topic_thresholds") or {}
    broad = thresholds.get("broad", 2)

    new_jobs = [j for j in jobs if j.get("first_seen") == stamp]
    new_hci = sorted([j for j in new_jobs if j.get("topic_score", 0) >= broad],
                     key=lambda j: -j.get("topic_score", 0))
    new_other = [j for j in new_jobs if j.get("topic_score", 0) < broad]
    soon = sorted([j for j in jobs
                   if j.get("topic_score", 0) >= broad
                   and days_to(j.get("deadline", "")) is not None
                   and 0 <= days_to(j.get("deadline", "")) <= SOON_DAYS],
                  key=lambda j: j.get("deadline", ""))
    broken = [s for s in data.get("sources", []) if s.get("status") != "ok"]

    month_day = f"{int(stamp[5:7])}/{int(stamp[8:10])}" if len(stamp) == 10 else stamp
    subject = (f"[博士職缺] {month_day} 新增 {len(new_jobs)} 筆"
               f"（HCI 相關 {len(new_hci)} 筆）")

    parts = [
        '<div style="font-family:-apple-system,\'Noto Sans TC\',sans-serif;max-width:680px;'
        'margin:0 auto;padding:18px;color:#1b1b1a">',
        f'<h2 style="font-size:18px;margin:0 0 4px">博士職缺摘要 · {esc(stamp)}</h2>',
        f'<div style="color:#6b6a66;font-size:13px;margin-bottom:18px">'
        f'目前開放 {len(jobs)} 筆，其中 HCI 相關 {sum(1 for j in jobs if j.get("topic_score",0)>=broad)} 筆'
        f'　·　<a href="{esc(site_url)}">打開完整清單</a></div>',
    ]

    if new_hci:
        parts.append('<h3 style="font-size:15px;margin:18px 0 10px">今天新增的 HCI 相關</h3>')
        parts += [job_block(j) for j in new_hci]
    if soon:
        parts.append(f'<h3 style="font-size:15px;margin:18px 0 10px">'
                     f'{SOON_DAYS} 天內截止的 HCI 相關</h3>')
        parts += [job_block(j) for j in soon]
    if new_other:
        parts.append('<h3 style="font-size:15px;margin:18px 0 10px">'
                     '今天新增的其他領域</h3>')
        parts.append('<ul style="padding-left:18px;margin:0;color:#3a3a38;font-size:13px">')
        for job in new_other[:25]:
            where = " · ".join(x for x in [job.get("university") or job.get("source_name"),
                                           job.get("city")] if x)
            parts.append(f'<li style="margin-bottom:5px"><a href="{esc(job.get("url"))}"'
                         f' style="color:#1f5fb4">{esc(job.get("title"))}</a>'
                         f' <span style="color:#6b6a66">{esc(where)}</span></li>')
        if len(new_other) > 25:
            parts.append(f'<li>⋯還有 {len(new_other) - 25} 筆</li>')
        parts.append('</ul>')
    if not new_jobs:
        parts.append('<p style="color:#6b6a66">今天沒有新增的職缺。</p>')
    if broken:
        parts.append('<h3 style="font-size:15px;margin:18px 0 8px">來源異常</h3>'
                     '<ul style="padding-left:18px;margin:0;color:#9a3412;font-size:13px">')
        for src in broken:
            parts.append(f'<li>{esc(src.get("name"))}：{esc(src.get("status"))} '
                         f'{esc((src.get("error") or "")[:120])}</li>')
        parts.append('</ul>')
    parts.append('</div>')
    body_html = "\n".join(parts)

    lines = [f"博士職缺摘要 {stamp}", ""]
    for title, group in (("今天新增的 HCI 相關", new_hci),
                         (f"{SOON_DAYS} 天內截止的 HCI 相關", soon)):
        if not group:
            continue
        lines.append(f"== {title}")
        for job in group:
            where = " / ".join(x for x in [job.get("university") or job.get("source_name"),
                                           job.get("city")] if x)
            lines.append(f"- [{job.get('topic_score', 0)}] {job.get('title')}")
            lines.append(f"  {where}｜截止 {job.get('deadline') or '—'}")
            lines.append(f"  標籤：{'、'.join((job.get('topics') or []) + (job.get('tools') or []))}")
            lines.append(f"  {job.get('url')}")
        lines.append("")
    if new_other:
        lines.append(f"== 今天新增的其他領域（{len(new_other)} 筆）")
        for job in new_other[:25]:
            lines.append(f"- {job.get('title')} / {job.get('university') or job.get('source_name')}")
        lines.append("")
    lines.append(site_url)
    return subject, body_html, "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只寫出 data/summary.html，不寄信")
    args = ap.parse_args()

    with open(DATA, encoding="utf-8") as fh:
        data = json.load(fh)
    site_url = os.environ.get("SITE_URL", "")
    subject, body_html, body_text = build(data, site_url)

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(body_html)
    print(f"主旨：{subject}")
    print(f"已寫出 {OUT}")

    if args.dry_run:
        return 0

    to = os.environ.get("MAIL_TO", "").strip()
    user = os.environ.get("MAIL_USER", "").strip()
    password = os.environ.get("MAIL_PASS", "").strip()
    if not (to and user and password):
        print("沒有設定 MAIL_TO／MAIL_USER／MAIL_PASS，跳過寄信。")
        return 0

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = os.environ.get("MAIL_FROM", user)
    message["To"] = to
    message.set_content(body_text)
    message.add_alternative(body_html, subtype="html")

    host = os.environ.get("MAIL_HOST", "smtp.gmail.com")
    port = int(os.environ.get("MAIL_PORT", "465"))
    context = ssl.create_default_context()
    if port == 587:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls(context=context)
            server.login(user, password)
            server.send_message(message)
    else:
        with smtplib.SMTP_SSL(host, port, timeout=30, context=context) as server:
            server.login(user, password)
            server.send_message(message)
    print(f"已寄到 {to}（{host}:{port}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
