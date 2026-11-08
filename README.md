# StatStudio AI

繁體中文的本機統計工具，可由 Codex 透過 MCP 操作。計算使用獨立 Python 引擎，**不需要安裝、啟動或授權 SPSS**。

目前是 0.1.0 研究版。已實作 18 類常用分析，另加 4 個統合分析方法（以 R meta／metafor／rjags 為對照），**尚未達到使用者要求的 SPSS 全功能、全算法、全輸出一致**。SPSS 僅在開發驗證時作為對照基準；同一固定樣本的數值通過，不能推論所有資料、預設與選項都一致。請先閱讀 [實测範圍](docs/validation.md) 與 [算法規格](docs/implemented-algorithms.md)。

## 在這台或另一台 Windows 電腦使用

1. 安裝 Python 3.12。
2. 下載這個專案，雙擊 `setup.cmd`（第一次需要網路）。
3. 雙擊 `start.cmd`，開啟 `http://127.0.0.1:8765`。
4. 載入示範資料，或匯入 CSV / TSV / XLSX / SAV；選方法、欄位和參數後執行。
5. 每次分析可下載完整 JSON 和獨立 HTML 報告。HTML 可由瀏覽器列印成 PDF。

統計工作完成後關閉啟動的終端視窗即可停止服務。啟動後僅接受本機連線。另一台電腦要自行安裝其 Python 環境；不要複製 `.venv`。

### 讓 AI 操作

安裝 Codex 後雙擊 `connect-ai.cmd`，或在這個專案執行：

```powershell
.venv\Scripts\python.exe -m statstudio install-mcp
```

程式會備份 Codex 設定，透過官方 `codex mcp add` 登錄 `statstudio`。重新啟動 Codex 後可說：

> 用 StatStudio 匯入 D:\研究\問卷.csv，先列出欄位、型別與缺失值。比較兩個組別的分數，呈現兩種變異數假設的 t 檢定、信賴區間、有效樣本數及報告路徑。

> 用 StatStudio 的示範資料，以 y 為應變數、x 和 z 為預測變數做線性迴歸。先確認選項，再執行；解釋係數與不確定性，列出與 SPSS 尚未驗證之處。

沒有 Codex CLI 時，`python -m statstudio mcp-config` 會輸出可手動加入設定的區塊。[Codex 官方 MCP 說明](https://developers.openai.com/codex/mcp/)。

網頁本身沒有內建語言模型或假聊天機器人；自然語言能力來自已連接的 Codex。統計計算在本機進行；使用 AI 時，工具傳回的資料預覽、欄位及結果會進入所選 AI 服務的上下文。工具不會自動上傳完整原始檔，但結果表可能包含個案資訊，例如群集分派。MCP 結果表每表最多傳回前 200 列，明列截斷狀態；完整內容仍保留於本機 JSON／HTML。可請 AI 呼叫 `get_validation_status` 查看固定樣本的 SPSS 比對範圍。

## 目前分析

| 類別 | 方法 |
|---|---|
| 基本統計 | 描述統計、次數分配、交叉表／卡方、單樣本／独立樣本／配對 t 檢定、單因子 ANOVA、Pearson／Spearman／Kendall 相關 |
| 建模與量表 | 線性迴歸、二元 logistic、PCA、主軸因素分析、Cronbach α |
| 群集／無母數 | K-means、階層式群集、Mann–Whitney、Wilcoxon、Kruskal–Wallis |
| 統合分析（二元結果） | 反變異數共同／隨機效應（DL／REML／PM）、Hartung–Knapp、預測區間、Peto／MH、子群、Egger；單變量統合迴歸（Knapp–Hartung）；貝氏二項–常態階層模型（MCMC）；試驗序列分析（Lan–DeMets O'Brien–Fleming）。整體隨機效應部分欄位有 SPSS 30 合成資料對照，其他方法另有 R／文獻參照，範圍見驗證文件 |
| 輸出 | 結果表、直方圖／散布圖／長條圖、完整精度 JSON、含 SVG 圖的獨立 HTML |

未支援的選項會報錯，不會默默忽略。尚未涵蓋 GLM 多因子／重複量數、混合模型、存活分析、時間序列、複雜抽樣、多重插補、Bootstrap、全部事後比較、加權、SPSS 語法相容解析器及 SPV 原生輸出。獨立介面與報表不是 SPSS Viewer 的版面複製品。

## 統合分析的 SPSS 設定（2026-11-08）

`meta-analysis` 分支的 `meta_binary` 現在預設採用本次 SPSS 30 對照設定：

- `prediction_df="k-2"`：預測區間使用 t(k−2)。**Q 檢定及 Hartung–Knapp 合併效果信賴區間仍使用 k−1**，沒有全部改成 k−2。k 為排除缺失及不可估計研究後實際納入合併的數量；少於 3 篇時不提供預測區間。
- `heterogeneity_method="tau2"`：整體隨機效應 I²／H² 依估計的 τ² 及典型研究內變異數計算；H² ≥ 1。輸出同時列出 H、H² 及預測區間自由度，避免混用。
- `tau2_method="DL"`、一般合併 CI 的 z 近似、額外的未截斷 Hartung–Knapp CI、單零研究加 0.5、雙零研究排除，維持本研究已在 SPSS 明確指定的設定。這不是改成 SPSS 的所有原廠預設值（例如 IBM 的 τ² 原廠預設為 REML）。

要重現修改前的預測區間與整體異質性定義，明確指定：

```python
result = analyze(df, "meta_binary", {
    **roles,
    "prediction_df": "k-1",
    "heterogeneity_method": "q",
})
```

舊的 k−1 預測區間是另一種近似方法，不是計算錯誤；新預設是為了對齊此次 SPSS 報告。434 個原生 SPSS 數值欄位在 10 個合成案例下通過比較，並保存修改前的 25 個差異。詳見 [驗證範圍](docs/validation.md#統合分析的-spss-30-對照2026-11-08) 與 [逐欄報告](validation/meta/spss-parity-report.json)。

程式仍由獨立引擎運算。設定與 SPSS 對齊不代表結果由 SPSS 產生；論文軟體名稱應依實際執行方式記載。既有結果檔不會自動改寫，需重新執行分析才會使用新預設。

## 資料與重現性

- 每次分析保留資料 SHA-256、完整明確選項、有效樣本／缺失規則、版本、seed、警告與原始數值。
- 資料與結果預設儲存在使用者家目錄 `.statstudio`；Windows 為 `%USERPROFILE%\.statstudio`。`STATSTUDIO_HOME` 可改成指定資料夾，網頁與 MCP 須使用同一設定。
- JSON 儲存完整浮點值，HTML 顯示 8 位有效數字；不是位元完全等同 SPSS 的保證。
- 檔案上限 25 MB、100,000 列、300 欄；個別高成本分析會有額外限制。
- CSV / TSV 使用 UTF-8；空值視為缺失，`NA` 字串保留。XLSX 只取第一張工作表及已儲存的公式結果。
- SAV 保留原始數值與變數／值標籤中繼資料；含使用者定義缺失值的 SAV 暫時拒絕。匯入不套用 SPSS 原有篩選、加權與 SPLIT FILE，這些分析流程要另行重建。
- 不執行輸入資料或 AI 產生的任意 Python／SPSS 程式碼，MCP 只能呼叫明列分析。

## GitHub 與多台電腦

專案不包含 IBM 執行檔、DLL、JAR、私有資料或授權資訊。`docs/command-catalog.json` 是本機語法宣告的結構盤點，並不是 IBM 原始碼或算法實作。`tests/fixtures` 只放人工合成資料。

私人儲存庫：[benny10030671-commits/statstudio-ai](https://github.com/benny10030671-commits/statstudio-ai)。另一台電腦登入有權限的 GitHub 帳號後，執行：

```powershell
git clone https://github.com/benny10030671-commits/statstudio-ai.git
cd statstudio-ai
.\setup.cmd
.\connect-ai.cmd
.\start.cmd
```

也可從 GitHub 的 **Code → Download ZIP** 下載、解壓縮，再雙擊相同的安裝與啟動檔。更新時先 `git pull`，再執行 `setup.cmd`。每台電腦各自設定 Codex MCP，因為 Python 路徑不同。

`.gitignore` 排除環境、私人資料、結果及秘密設定。**GitHub 同步程式碼，不會自動同步 `.statstudio` 資料與報告。** 若要在其他電腦重現，同步經你選定的資料檔及分析 JSON，再匯入同一資料。

## 開發與驗證

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.venv\Scripts\python.exe -m pip install --no-deps -e .
.venv\Scripts\python.exe -m pytest -q
```

驗證 fixture 可在沒有 SPSS 的電腦跑回歸測試。只有重新產生 SPSS 對照樣本時需要開發者合法安裝的 SPSS；詳見 `validation/`。Windows Python 3.12 為本次實測環境，跨 OS / BLAS 的結果仍須重新跑測試。

研究紀錄：[算法盤點](docs/algorithm-catalog.md)、[實作公式與邊界](docs/implemented-algorithms.md)、[原版對照結果](docs/validation.md)。
