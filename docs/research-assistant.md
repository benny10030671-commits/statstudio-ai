# 用想法開始的 SPSS 研究助理

本分支把 Codex / Claude Code 作為對話與推理入口，把已安裝的 SPSS 作為統計引擎。不是用關鍵字選方法的假聊天，也不是把 Python 重算結果冒充 SPSS。它不另外呼叫付費模型 API；使用你正在使用的 AI 客戶端及其帳戶。

## 使用方式

在 Windows 安裝 Python 3.12 與正常授權的 SPSS，再執行 `setup.cmd`。Codex 使用 `connect-spss-codex.cmd`；Claude Code 使用 `connect-spss-claude.cmd`。登錄名稱為 **statstudio-spss**，與原有 **statstudio** 獨立引擎分開。登錄前會備份既有設定。重新開啟 AI 後可直接說：

> 使用 statstudio-spss 研究助理。我想了解教育訓練前後的分數有沒有改變。我還不知道應該準備什麼檔案，請先問我必要問題，提供資料範本、建議的方法與原因，收到資料後幫我執行 SPSS、製作圖表並解讀。

> 我有兩組獨立受試者，想比較分數，也想調整年齡。請先幫我整理主要研究問題、要準備的欄位、缺失值編碼與適合的分析方式；不要直接猜測研究設計。

> 延續先前的研究，讀取保存的計畫。我已填好 D:\研究\資料.csv，請檢查資料後完成分析，將數值結論與圖形解讀保存成報告。

在 Claude Code 也可選 MCP prompt `research_assistant`；一般自然語言請求即可，不必記工具名。

雙擊 `start-spss.cmd` 開啟 `http://127.0.0.1:8766/research`，可整理想法、複製給 AI 的請求、下載各版資料範本、閱讀已完成解讀或開啟原生 SPSS 檔。此頁與 MCP 讀取同一個 `STATSTUDIO_HOME`；它不在網頁內嵌另一個聊天模型。

## 你會得到什麼

| 階段 | AI 與工具的工作 | 保存的產物 |
|---|---|---|
| 想法 | 問清研究對象、觀察單位、配對/獨立、抽樣、結果與分組 | 研究紀錄 |
| 資料需求 | 列出欄名、角色、單位、編碼及缺失值，說明一列代表什麼 | 可填寫 CSV 範本、資料字典 |
| 方法建議 | 依問題及設計說明候選方法、假設、主要/探索性分析與限制 | 不覆寫舊版的研究計畫 |
| 檢查 | 缺欄、型態、組別、缺失、重複 ID、完全共線、模型所需有效資料 | 資料檢查結果與 SHA-256 |
| 執行 | Python 啟動自己的 SPSS engine；不接管使用者已開啟的資料視窗 | 完整 `.sps`、SPSS `.spv`、各程序 `.xml`、原生 PNG、執行日誌 |
| 解讀 | AI 讀取精確表格、註腳與警告，實際查看圖形，解釋效果與限制 | 有表格/儲存格/圖形來源 ID 的 AI 解讀與可攜式 HTML 報告 |

收到資料且必要問題已釐清後，AI 可直接進行已授權的分析，不需要每一步重複問「可以嗎」。如果設計、編碼或排除規則仍不明確，會先解決會改變結果的問題。

## 計算與解讀的界線

- 原生表格與圖來自這次本機 SPSS，保留 OMS `number` 的原始字串與 SPSS 顯示文字。OMS 數值本身是 SPSS 匯出的精度，不宣稱取得其內部完整浮點位元。
- AI 負責採訪、方法建議與解釋，並保存其作者及引用。工具核對引用 ID 存在，**不會自動證明 AI 的統計推論或文字完全正確**。
- `p=.000` 不解讀為機率等於零；不顯著不能當作證明沒有差異；觀察性關聯不能直接寫成因果。圖形不能取代研究設計與精確估計。
- 正式樣本數規劃需效果大小、變異、檢定力、顯著水準與設計資訊；本版不自動做檢定力計算。
- 不自動刪極端值、補值、重編碼、反向計分、排除未指定組別或為了顯著而換方法。需要的資料轉換必須另行明確設計。

## 原生分析範圍

支援 18 種明確的模板，不接受任意 SPSS syntax 或任意作業系統命令。`research_capabilities` 回傳完整可用參數，未知參數會拒絕執行。

| 方法 | 輸出與目前設定 |
|---|---|
| 描述統計 | EXAMINE，信賴區間、分位數，箱形/直方/常態機率圖；逐變數缺失排除 |
| 次數分配 | 原生次數表、百分比、長條圖 |
| 交叉表 | 卡方、Phi/Cramér's V、期望次數與列/欄百分比、長條圖 |
| 單樣本 t | 指定比較值與信賴水準，分布圖 |
| 獨立樣本 t | 明確指定兩個數值組碼，保留兩種變異數假設的原生結果與分組箱形圖 |
| 成對 t | 同列前後值，方向固定「後－前」；散布圖及差值分布圖 |
| 單因子 ANOVA | 描述、變異同質性、整體 ANOVA 與 Welch，分組箱形圖；未加入事後比較 |
| 相關 | Pearson 或 Spearman，pairwise 缺失排除；散布圖呈現前兩個選定變數 |
| 線性迴歸 | 數值預測變數、截距、listwise、係數 CI、共線性、殘差/常態機率圖；附的原始散布圖不代表調整後效果 |
| 二元 logistic | 結果必須 0/1，事件為 1；數值預測變數、OR/CI、適配度；未實作自動類別 dummy 或完整校準圖 |
| 信度 | Cronbach alpha、題目/總分統計；不自動處理反向題 |
| Mann–Whitney | 明確兩個數值組碼，原生秩次與檢定表 |
| Wilcoxon | 同列前後值，原生秩次與檢定，另附差值圖 |
| Kruskal–Wallis | 數值組碼範圍必須涵蓋實際所有組別 |
| PCA / 主軸因子 | 指定成分/因子數、不旋轉，原生萃取/KMO/碎石圖 |
| K-means | 原始尺度、指定 k、固定首批初始中心規則；不自動標準化 |
| 階層分群 | 原始尺度、組間平均連結、平方歐氏距離、樹狀圖；最多 2,000 列 |

統計模板有意採取固定選項；它不是全 SPSS 對話框的替代品。混合模型、多層次、三次以上重複量測、複雜抽樣、加權、存活分析、多重插補、SEM、自動事後比較與多重檢定校正尚未提供。無法滿足設計時應說明缺口，不把資料硬塞進另一種方法。SPSS 模組可用性仍依本機授權；失敗保留日誌並標示 failed，不切換成其他引擎。

## 資料、隱私與多台電腦

CSV/TSV 使用 UTF-8；XLSX 讀第一張工作表與已儲存的公式結果；SAV/ZSAV 保留原檔字典與使用者定義缺失。CSV/XLSX 在本機轉為 SAV，欄名映射為 `v001` 等安全名稱，原欄名保留為標籤。分組檢定目前要求數值組碼，AI 會先提供編碼規格。上限 25 MB、100,000 列、300 欄。每次明確關閉 WEIGHT、FILTER、SPLIT FILE，避免隱藏設定改變研究。

本機預設資料位置為 `%USERPROFILE%\.statstudio\research`。可用 `STATSTUDIO_HOME` 改根目錄；建議短路徑。計畫、資料、原始 SPSS 輸出與 AI 敘述均留在本機，Git 忽略私有資料與二進位結果。工具傳給 Codex/Claude 的欄位、類別值、結果和圖形會進入該 AI 服務的上下文；不是完全離線 AI。個案層級圖與分群表可能含個案資訊。

其他電腦從私人 GitHub repo 切到此分支，重新執行 setup 與 connect。不要複製 `.venv`、IBM 二進位檔或授權材料；每台需正常可用的 SPSS。Git 同步程式和文件，不會自動同步研究資料與報告。

```powershell
git clone --branch feat/spss-ai-research-assistant https://github.com/benny10030671-commits/statstudio-ai.git
cd statstudio-ai
.\setup.cmd
.\connect-spss-codex.cmd
# 或 .\connect-spss-claude.cmd
```

非預設 SPSS 安裝位置可設定 `STATSTUDIO_SPSS_HOME`，重新啟動 AI 讓 MCP 繼承設定。初版只支援 Windows 的 `SPSS_HOME\Python3\python.exe`，本機實測 SPSS 30 / bundled Python 3.10。

## 實作與驗證

應用 Python 3.12 執行 MCP、資料檢查與報告；獨立標準函式庫 worker 由 SPSS 自帶 Python 執行。工作程序自己 StartSPSS / StopSPSS、跨程序鎖定避免同時啟動，逾時只終止自身程序樹。每次保留輸入快照、語法、worker 雜湊與 SPSS engine 雜湊。超時、授權錯誤、無統計表或輸出損壞都不標成成功。

一般測試不需要 SPSS：`python -m pytest -q`。本機整合驗證需已授權 SPSS：

```powershell
.venv\Scripts\python.exe validation/validate_research_spss.py --output C:\研究測試
```

整合測試透過真正 MCP stdio 執行合成資料，讀取分頁表格與 PNG image content。它驗證串接與固定模板的可執行性，不能證明所有資料、選項或 AI 判斷都正確。

2026-10-12 本機 SPSS 30 實測：18 種模板完成，輸出 119 張表、1,543 個數值儲存格、37 張 PNG；均可經 MCP 讀取。成對 t 與 Wilcoxon 已分別核對 SPSS 不同的語法順序，讓報告都呈現後測減前測。保留的執行摘要、明確選項與雜湊見 [research-spss-summary.json](../validation/research-spss-summary.json)。另有一份 60 位合成學員的繁體中文前後測示範，實際查看差值圖後保存有引用的 AI 解讀。這是功能驗證與教學示範，不是真實成效證據。

本次 81 項一般測試通過，包含原獨立引擎回歸測試、資料缺失與雜湊、錯誤阻擋、原生輸出解析、HTML 逸出、MCP stdio、失敗執行留存、程序鎖定、重複登錄與本機報告路由。瀏覽器已實際檢查研究首頁、複製請求及示範報告。

設定依據：[Codex 官方 MCP 文件](https://developers.openai.com/codex/mcp/)、[Claude Code 官方 MCP 文件](https://code.claude.com/docs/en/mcp)。原生輸出依據：[IBM SPSS 30 OMS](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=reference-oms)、[IBM OMS 圖像匯出](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=command-images-imageformat-keywords-oms)。
