#!/usr/bin/env python3
"""不連網的解析測試：python scraper/test_parse.py"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run  # noqa: E402

FAILS = []


def check(label, got, want):
    if got != want:
        FAILS.append(f"{label}: 得到 {got!r}，預期 {want!r}")


TITLES = [
    ("PhD Position in Quantum Computing", True),
    ("PhD-position: Urban Flooding", True),
    ("Promovendus Hydrologie", True),
    ("Doktorandin / Doktorand (m/w/d)", True),
    ("Doctoral Candidate in Machine Learning", True),
    ("Doctoral researcher, 4 years", True),
    ("Early Stage Researcher (ESR) in Photonics", True),
    ("Research Assistant / PhD student", True),
    ("Postdoctoral Researcher in Robotics", False),
    ("Post-doctoral fellow in Fluid Dynamics", False),
    ("Assistant Professor of Physics", False),
    ("Lab Technician", False),
    ("Tenure Track position", False),
    ("PhD Studentship: Understanding how GLP-1 medications shape social life", True),
    ("Fully funded studentship in Human Factors", True),
    ("EPSRC Centre for Doctoral Training (CDT) studentship", True),
    ("Doctoral Training Partnership studentship in Informatics", True),
    ("Postdoctoral studentship coordinator", False),
]

DATES = [
    ("2026-09-01", "2026-09-01"),
    ("2026-09-01T10:00:00+02:00", "2026-09-01"),
    ("15 October 2026", "2026-10-15"),
    ("01/09/2026", "2026-09-01"),
    ("garbage", ""),
    ("", ""),
    ("1823-01-01", ""),
]

LISTING = """<html><body>
<a href="/en/jobs/12345">PhD Position on Floating Wind Turbines</a>
<a href="/en/jobs/12345?utm_source=x">PhD Position on Floating Wind Turbines</a>
<a href="/en/jobs/999">Postdoc in Fluid Dynamics</a>
<a href="/about">About us</a>
<a href="/en/jobs/555">ok</a>
<a href="/en/jobs/363889/phd-co-production-of-land-use-futures/"><span></span></a>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"JobPosting","title":"PhD Candidate Structural Health",
 "url":"https://example.org/en/jobs/777","datePosted":"2026-09-01","validThrough":"2026-10-15",
 "hiringOrganization":{"@type":"Organization","name":"Delft University of Technology"},
 "jobLocation":{"@type":"Place","address":{"addressLocality":"Delft","addressCountry":"NL"}},
 "description":"<p>We seek a <b>PhD</b> candidate.</p>"}
</script></body></html>"""

DETAIL = """<html><head><title>x</title></head><body>
<h1>PhD position: Offshore Wind</h1>
<p>Posted on: 11 September 2026</p>
<p>Organisation/Company Delft University of Technology</p>
<p>Research Field Engineering</p>
<p>Application deadline: 30 November 2026</p></body></html>"""


def check_sources():
    """sources.yml 本身的健檢：格式壞掉的話這裡就會擋下來。"""
    import yaml

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources.yml"),
              encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    check("sources.yml 有 defaults", isinstance(config.get("defaults"), dict), True)
    sources = config.get("sources")
    check("sources.yml 有 sources 清單", isinstance(sources, list) and len(sources) > 0, True)
    if not isinstance(sources, list):
        return
    ids = [s.get("id") for s in sources]
    check("來源 id 不重複", len(ids), len(set(ids)))
    for source in sources:
        label = source.get("id", "?")
        check(f"{label} 有 name", bool(source.get("name")), True)
        check(f"{label} 有 urls", bool(source.get("urls")), True)
        check(f"{label} type 合法", source.get("type", "links") in run.ADAPTERS, True)
        if source.get("type", "links") == "links":
            pattern = source.get("link_pattern")
            check(f"{label} 有 link_pattern", bool(pattern), True)
            if pattern:
                try:
                    re.compile(pattern)
                except re.error as exc:
                    FAILS.append(f"{label} 的 link_pattern 不是合法正則：{exc}")


def main():
    check_sources()
    for title, want in TITLES:
        check(f"is_phd({title!r})", run.is_phd(title), want)
    for raw, want in DATES:
        check(f"parse_date({raw!r})", run.parse_date(raw), want)

    run.fetch = lambda url, timeout=30: LISTING
    source = {"id": "t", "name": "Test", "country": "NL", "type": "links",
              "link_pattern": r"/en/jobs/\d+", "urls": ["https://example.org/en/jobs/"]}
    items, _ = run.adapter_links(source, {"timeout": 10})
    check("連結去重後筆數", len(items), 4)  # 12345（含重複網址）、999、777、363889；"ok" 標題太短
    check("錨點沒文字時用網址 slug 當標題",
          run.title_from_slug("https://x/en/jobs/363889/phd-co-production-of-land-use-futures/"),
          "Phd Co Production Of Land Use Futures")

    records = run.collect(dict(source), {"timeout": 10, "filter": "phd"})
    check("過濾後筆數", len(records), 3)
    by_title = {r["title"]: r for r in records}
    ld = by_title.get("PhD Candidate Structural Health", {})
    check("JSON-LD 學校", ld.get("university"), "Delft University of Technology")
    check("JSON-LD 地點", ld.get("location"), "Delft, NL")
    check("JSON-LD 城市", ld.get("city"), "Delft")
    check("JSON-LD 截止日", ld.get("deadline"), "2026-10-15")
    check("沒有 JSON-LD 時學校先留空（補抓詳細頁後才退回來源名）",
          by_title.get("PhD Position on Floating Wind Turbines", {}).get("university"), "")

    check("標題切掉尾巴的雜訊",
          run.tidy_title("PhD Position Movement Biomarkers 100%, Zurich, fixed-term | ETH"),
          "PhD Position Movement Biomarkers 100%, Zurich, fixed-term")
    check("標題前段太短時保留全文",
          run.tidy_title("PhD | Quantum Computing at TU Delft"),
          "PhD | Quantum Computing at TU Delft")

    # mode: all 會把每個候選網址的結果合併
    source_all = dict(source, mode="all",
                      urls=["https://example.org/en/jobs/?q=a", "https://example.org/en/jobs/?q=b"])
    items_all, used = run.adapter_links(source_all, {"timeout": 10})
    check("mode all 合併後仍然去重", len(items_all), 4)
    check("mode all 回報用了幾個網址", used, "2 個搜尋網址")

    check("HCI 分數：命中兩個關鍵字是 4 分",
          run.score_topics("PhD on gaze and haptics in VR")[0], 4)
    check("HCI 分數：不相關的是 0",
          run.score_topics("PhD in Inhalation Toxicology")[0], 0)
    check("網域分組取最後兩段", run.site_of("https://uu.varbi.com/en/what:job/jobID:1/"), "varbi.com")
    check("關鍵字真的出現在內文才算命中",
          run.query_matches("human-computer interaction",
                            "A PhD on human computer interaction in cars"), True)
    check("搜尋引擎亂撈的不算命中",
          run.query_matches("human-computer interaction",
                            "PhD position in Plant Cell and Molecular Biology"), False)
    check("片語要連在一起才算命中",
          run.query_matches("interaction design",
                            "the interaction between design and policy"), False)
    check("關鍵字標籤是中文",
          run.score_topics("PhD on eye tracking in virtual reality")[1],
          ["VR XR AR", "眼動追蹤"])
    check("VR / AR / XR 合成一個標籤",
          run.score_topics("augmented reality and mixed reality study")[1], ["VR XR AR"])
    check("同一個標籤只算一次",
          run.score_topics("augmented reality and mixed reality study")[0], 2)
    check("工具／方法標籤",
          run.tool_tags("We use Unity and Python, run semi-structured interviews "
                        "and co-design workshops"),
          ["Unity", "Python", "訪談", "工作坊"])
    check("城市去掉 County", run.clean_city("Stockholm County"), "Stockholm")
    check("城市去掉瑞典文所有格", run.clean_city("Stockholms län"), "Stockholm")
    check("國碼不是城市", run.clean_city("AT"), "")
    check("多字城市保留", run.clean_city("The Hague"), "The Hague")
    check("詳細頁抓得到城市",
          run.page_fallback_fields(
              "<html><body><h1>PhD</h1><p>Work location Uppsala</p></body></html>")["city"],
          "Uppsala")
    check("領域標籤是中文",
          run.field_tags("PhD on clinical imaging for patients"), ["醫療", "影像視覺"])
    check("整頁計分忽略弱詞（現在沒有弱詞了，泛用字不該命中）",
          run.score_topics("we look for prototyping experience", min_weight=2)[0], 0)
    check("搜尋網址取得出關鍵字",
          run.query_of("https://x/jobs?q=human-AI+interaction"), "human-AI interaction")
    check("沒給中文時退回從正則推標籤",
          run.term_label("conversational (agent|interface|ai)"), "conversational agent")

    check("詳細頁 fallback 截止日", run.page_fallback_fields(DETAIL)["deadline"], "2026-11-30")
    check("Varbi 的 Last application date 也讀得到",
          run.page_fallback_fields(
              "<html><body><h1>PhD in HCI</h1>"
              "<p>Last application date 30 Oct 2026</p></body></html>")["deadline"],
          "2026-10-30")
    check("詳細頁 fallback 學校",
          run.page_fallback_fields(DETAIL)["university"], "Delft University of Technology")
    check("同標題同學校算同一個職缺",
          run.dedupe_key({"title": "PhD Position on Wind", "university": "TU Delft"}),
          run.dedupe_key({"title": "PhD  position   on wind!", "university": "TU  Delft"}))
    check("同標題不同學校不算重複",
          run.dedupe_key({"title": "PhD in ML", "university": "TU Delft"})
          != run.dedupe_key({"title": "PhD in ML", "university": "KTH"}), True)

    check("詳細頁 fallback 發布日",
          run.page_fallback_fields(DETAIL)["posted"], "2026-09-11")
    check("詳細頁 fallback 標題", run.page_fallback_fields(DETAIL)["title"], "PhD position: Offshore Wind")

    if FAILS:
        print("測試失敗：")
        for f in FAILS:
            print("  -", f)
        return 1
    print("所有解析測試通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
