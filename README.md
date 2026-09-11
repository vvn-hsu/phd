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
- 最下面的「來源狀態」會顯示哪些網站抓成功、哪些掛了

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

## 每日排程的前提

GitHub 的 `schedule` 只會在**預設分支**上跑。目前這些檔案在 `claude/tu-delft-phd-tracker-5sj9u5`，
要讓它每天自動跑，得把這個分支合併進預設分支（或把它設成預設分支）。
在其他分支上只有 `push` 和手動 `workflow_dispatch` 會觸發。

排程超過 60 天沒有任何 commit 活動時，GitHub 會自動停用；有自動 commit 資料的話通常不會遇到。

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
    enrich: jsonld              # 對新職缺再抓詳細頁補截止日
```

`links` 這個 adapter 是靠職缺網址的形狀抓連結，不靠 CSS class，對方改版時比較不會整個壞掉。
加完先跑 `python scraper/run.py --only uu --probe` 確認抓得到。

## 已知限制

- 每個來源的解析都是對著別人的網站猜的，對方改版或擋機器人（Cloudflare、需要 JS 才渲染的頁面）就會失效。
  網頁最下面的「來源狀態」就是用來發現這件事的：某個來源長期 error 或 0 筆，就是該去修 `sources.yml`。
- 只用標題判斷是不是博士職缺，偶爾會漏掉標題寫得很怪的（例：只寫 "Vacancy 2026-045"）。
- 沒有寄信通知，要自己開網頁看。
