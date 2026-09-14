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

## 卡片上的中文標籤

每筆職缺會貼兩種標籤，目的是讓人不用讀完標題就掃得過去：

**綠色＝HCI 關鍵字**（同時是相關度分數的來源，每命中一個 2 分）

VR XR AR、眼動追蹤、腦機介面、腦電、觸覺回饋、穿戴式、無障礙、包容性設計、
對話式代理、聊天機器人、語音介面、對話系統、資料視覺化、視覺分析、情感運算、
情緒辨識、多模態互動、手勢互動、可解釋 AI、說服式科技、嚴肅遊戲、遊戲設計、
遠端操作、情境覺察、行為改變、自動駕駛、駕駛模擬、社會運算、群眾外包、普適運算、
認知人因、參與式設計、使用者介面、設計研究

另外還有一個 `HCI 關鍵字搜尋` 標籤：代表這筆是被 AcademicTransfer 的 HCI
關鍵字搜尋撈到的（`sources.yml` 裡那 14 組關鍵字），標成「（弱）」的是關鍵字
沒有出現在職缺內文、只是被搜尋引擎鬆散比對到。

**藍色＝工具與研究方法**（不算分）

Unity、Unreal、Godot、Blender、Python、R、MATLAB、JavaScript、C++/C#、
PyTorch/TensorFlow、Arduino、3D 列印、SPSS/Stata、NVivo、問卷平台、Figma、
訪談、焦點團體、工作坊、問卷調查、田野／民族誌、日誌研究、使用者測試、
實驗室實驗、RCT、質性分析、混合方法、動作捕捉、生理量測、原型製作、
參與式研究、文獻回顧、模擬建模

**灰色＝領域標籤**（不算分，只為了掃視）

醫療、神經科學、機器學習、機器人、能源、材料化學、量子、光電半導體、氣候環境、
生命科學、教育、法律政策、語言、影像視覺、資安隱私、交通移動、農業食品、經濟商管、
建築城市、音訊語音、製造工程、數學最佳化、社會心理

對照表在 `scraper/topics.yml`，格式是「正則: 中文標籤」；同一個中文標籤可以對到
多個正則（VR XR AR 就是這樣合起來的），計分時只算一次。
搜尋框也吃中文標籤（打「眼動追蹤」就會篩出來），上面還有一個「領域標籤」下拉。

## HCI 相關度

抓進來的職缺都會用 `scraper/topics.yml` 的關鍵字表算一個 `topic_score`，
命中的詞會以中文顯示在職缺卡片上。網頁預設只顯示「HCI 相關（廣泛）」，
上方的主題選單可以切到「嚴格」或「全部領域」。

分數規則：綠色標籤每命中一個 2 分。

分數是拿職缺詳細頁的前 8000 字算的（比只看摘要準）。
從 HCI 關鍵字搜尋來源進來的職缺，如果那組關鍵字**整個片語**真的出現在職缺內文，
再加 3 分（`sources.yml` 的 `topic_boost`），卡片上會顯示是哪組關鍵字搜到的。
只是被搜尋引擎鬆散撈出來、內文沒出現的只加 1 分——那些站的全文搜尋很鬆，
搜 human-computer interaction 會跑出植物細胞學。

同一個網域裡多數頁面都出現的詞會被當成網站樣板、不採計（用網域而不是來源分組，
因為 Varbi 上的各校是不同 subdomain 但共用同一套版型）——KTH 每一頁的頁尾
都有 "user experience" 和 "accessibility"，不處理的話 28 筆全會被誤判成相關。

廣泛＝2 分以上（命中一個關鍵字就算），嚴格＝6 分以上。要放寬或收緊就改 `scraper/topics.yml`。

除了一般來源之外，另外有兩個「HCI 關鍵字搜尋」來源，直接拿 HCI 的詞去搜
AcademicTransfer 和 EURAXESS——因為 HCI 的缺常常排不進「最新職缺」那一頁。

## 目前的來源

| 來源 | 狀態 |
| --- | --- |
| AcademicTransfer（HCI 關鍵字搜尋，14 組關鍵字） | 開 |
| EURAXESS（HCI 關鍵字搜尋） | 關：`?keywords=` 沒有作用，10 組關鍵字回來的是同一批職缺 |
| AcademicTransfer（荷蘭各大學，TU Delft 的職缺都在這） | 開 |
| EURAXESS（全歐洲，翻 3 頁） | 開，但不穩：翻頁會被 429，回來的常常是非博士的公告 |
| Academic Positions（彙整站） | 關：卡片文字會整團變成標題，多半是招生廣告 |
| THE Unijobs（英國為主，3 個學科分類＋4 組 HCI 關鍵字） | 開 |
| jobs.ac.uk、FindAPhD | 關：搜尋結果要 JS 才渲染，HTML 裡只有幾則贊助職缺 |
| ETH Zürich | 開 |
| KTH（kth.varbi.com） | 開 |
| Uppsala、Stockholm、Lund、Umeå（都是 Varbi，跟 KTH 同一套版型） | 開 |
| Linköping | 關：`liu.varbi.com` 不存在，它用的不是 Varbi |
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

## 每日摘要信

`scraper/mail.py` 會把當天的職缺整理成一封中文信：今天新增的 HCI 相關、
7 天內截止的 HCI 相關、今天新增的其他領域、來源異常。
同時會寫出 `data/summary.html`，不寄信也看得到。

```bash
python scraper/mail.py --dry-run   # 只產生 data/summary.html
```

**要真的收到信，得在 repo 設三個 secrets**（Settings → Secrets and variables →
Actions → New repository secret）：

| Secret | 內容 |
| --- | --- |
| `MAIL_TO` | 收件人信箱 |
| `MAIL_USER` | 寄件帳號，例如你的 Gmail |
| `MAIL_PASS` | 該帳號的**應用程式密碼**（Gmail 兩步驟驗證下產生的 16 碼），不是登入密碼 |

另外可選 `MAIL_HOST`（預設 `smtp.gmail.com`）、`MAIL_PORT`（預設 465，用 587 會走 STARTTLS）、
`MAIL_FROM`。三個必要的 secrets 沒設的話這一步會跳過，不會讓執行失敗。

只有**排程**和手動勾 `send_mail` 才會真的寄——不然每次 push 都會收到一封。

## 每日排程

GitHub 的 `schedule` 只會在**預設分支**上跑。這個 repo 的預設分支目前就是
`claude/tu-delft-phd-tracker-5sj9u5`（因為它是第一個推上去的分支），所以排程直接就會動，
不用另外合併。之後如果把預設分支換掉，記得把這些檔案一起帶過去。

排程超過 60 天沒有任何 commit 活動時，GitHub 會自動停用；有自動 commit 資料的話通常不會遇到。

也可以手動跑：Actions → 更新博士職缺 → Run workflow。

`data/jobs.json` 是整份重新產生的，不跟遠端做三方合併——提交前會先對齊遠端、
再把這次的結果放回去。兩次執行重疊時以後跑完的那次為準，漏掉的下一次會再抓到。

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
