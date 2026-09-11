# 博士職缺追蹤

每天自動去各校／各大學術職缺網站抓博士（PhD）職缺，整理成一個網頁，開起來就知道今天多了哪些。

- `index.html` — 網頁本體，讀 `data/jobs.json`
- `scraper/run.py` — 抓取程式
- `scraper/sources.yml` — 要抓哪些網站
- `.github/workflows/update-jobs.yml` — 每天 UTC 05:00（台灣 13:00）跑一次，把結果 commit 回來

## 網頁能做什麼

- 自上次造訪新增 / 今天新增 / 未讀 / 已收藏 / 14 天內截止 的篩選
- 依學校、國家、關鍵字搜尋
- 已讀、收藏、上次造訪時間存在瀏覽器的 localStorage，不會上傳
- 職缺從對方網站消失後，會標成「已下架」再留 45 天
- 同一個職缺同時登在兩個網站時（例如 EURAXESS 和學校自己的系統）會合併成一筆，
  另一個連結顯示在「另見」
- 最下面的「來源狀態」會顯示哪些網站抓成功、哪些掛了

## 目前的來源

| 來源 | 狀態 |
| --- | --- |
| AcademicTransfer（荷蘭各大學，TU Delft 的職缺都在這） | 開 |
| EURAXESS（全歐洲，翻 12 頁） | 開 |
| Academic Positions（彙整站） | 開 |
| jobs.ac.uk（英國） | 關：搜尋結果要 JS 才渲染，HTML 裡只有贊助職缺 |
| ETH Zürich | 開 |
| KTH（kth.varbi.com） | 開 |
| TU München | 開 |
| DTU、KU Leuven、Chalmers | 關：清單要 JS 才渲染，HTML 裡只有導覽列 |

網頁最下面的「來源狀態」看的是每天實際跑出來的結果，以那邊為準。

## 怎麼看

**GitHub Pages**：repo 的 Settings → Pages → Source 選 `Deploy from a branch`，分支選這個分支、資料夾選 `/ (root)`，
之後開 `https://vvn-hsu.github.io/phd/` 就是。

**本機**：

```bash
python3 -m http.server 8000
# 瀏覽器開 http://localhost:8000
```

不要直接用 `file://` 開 `index.html`，瀏覽器會擋掉讀取 `data/jobs.json`。

## 自己跑一次抓取

```bash
pip install -r scraper/requirements.txt
python scraper/run.py              # 正式抓，寫入 data/jobs.json
python scraper/run.py --probe      # 只測試各來源通不通，不寫檔
python scraper/run.py --only tudelft,euraxess
python scraper/test_parse.py       # 不連網的解析測試
```

## 每日排程

GitHub 的 `schedule` 只會在**預設分支**上跑。這個 repo 的預設分支目前就是
`claude/tu-delft-phd-tracker-5sj9u5`（因為它是第一個推上去的分支），所以排程直接就會動，
不用另外合併。之後如果把預設分支換掉，記得把這些檔案一起帶過去。

排程超過 60 天沒有任何 commit 活動時，GitHub 會自動停用；有自動 commit 資料的話通常不會遇到。

也可以手動跑：Actions → 更新博士職缺 → Run workflow。

## 新增一所學校

編 `scraper/sources.yml`，加一段：

```yaml
  - id: uu
    name: Utrecht University
    country: NL
    homepage: https://www.uu.nl/en/organisation/working-at-utrecht-university/jobs
    type: links                 # links / rss / jsonld
    urls:                       # 依序嘗試，第一個抓到東西的就用
      - https://www.uu.nl/en/organisation/working-at-utrecht-university/jobs
    link_pattern: '/vacancy/\d+'   # 職缺網址長什麼樣（正則）
    pages: 5                    # 要往後翻幾頁（預設 1，不翻頁）
    page_param: page            # 翻頁參數名稱（預設 page）
    enrich: jsonld              # 對新職缺再抓詳細頁補截止日
```

不知道對方網站的職缺網址長什麼樣時，先用偵查工具：

```bash
python scraper/sniff.py "https://www.uu.nl/en/organisation/working-at-utrecht-university/jobs"
```

它會印出：頁面上連結的形狀統計（數字換成 `{n}` 之後分群）、有沒有 schema.org JobPosting、
頁面自己宣告的 RSS feed、以及 HTML 裡出現的 API 網址。
在 GitHub 上也可以跑：Actions → 更新博士職缺 → Run workflow，把網址填進 `sniff` 欄位（空白分隔）。

`links` 這個 adapter 是靠職缺網址的形狀抓連結，不靠 CSS class，對方改版時比較不會整個壞掉。
加完先跑 `python scraper/run.py --only uu --probe` 確認抓得到。

## 已知限制

- 每個來源的解析都是對著別人的網站猜的，對方改版或擋機器人（Cloudflare、需要 JS 才渲染的頁面）就會失效。
  網頁最下面的「來源狀態」就是用來發現這件事的：某個來源長期 error 或 0 筆，就是該去修 `sources.yml`。
- 只用標題判斷是不是博士職缺，偶爾會漏掉標題寫得很怪的（例：只寫 "Vacancy 2026-045"）。
- 學校名稱來自職缺詳細頁（schema.org JobPosting 或頁面上的「Organisation/Company」欄位）。
  抓不到的時候會退回顯示來源名稱，例如「EURAXESS（全歐洲）」，那代表不知道是哪一校，不是真的雇主。
- AcademicTransfer 沒有可用的分頁參數（`?page=2` 回傳同一批），所以荷蘭那邊一次只看得到最新的一頁。
- 沒有寄信通知，要自己開網頁看。
