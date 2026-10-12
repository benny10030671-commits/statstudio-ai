# StatStudio AI

繁體中文的本機統計工具。這個 `feat/spss-ai-research-assistant` 分支新增 **Codex / Claude Code → Python → 本機 SPSS** 的研究助理；原有獨立 Python 引擎仍保留。

## 新分支：從想法到 SPSS 研究報告

直接告訴 AI：「我想研究什麼？」它會釐清設計、告訴你要準備哪些資料、建議統計方法、產生資料範本，再檢查資料並執行 SPSS。最後讀取原生數值與圖像，另存有來源引用的解讀報告。

1. 每台電腦安裝 Python 3.12，以及可正常授權使用的 IBM SPSS Statistics（本機驗證版本 30）。
2. 在這個分支執行 `setup.cmd`。
3. 依使用的 AI 執行 `connect-spss-codex.cmd` 或 `connect-spss-claude.cmd`，重新開啟 AI。
4. 對 AI 說：**「使用 statstudio-spss 研究助理。我想知道教育訓練前後分數是否改變，請先告訴我需要準備什麼資料，再建議分析方式。」**
5. 收到資料後，AI 可執行本機 SPSS，保存 `.sps`、`.spv`、`.xml`、PNG 圖與可攜式 HTML 報告。

完整的資料流程、方法範圍、MCP 工具與多台電腦設定見 **[研究助理使用指南](docs/research-assistant.md)**。自然語言互動在 Codex / Claude Code；`start.cmd` 網頁仍是原有獨立引擎介面。統計運算在本機，傳給 AI 的結果/圖像則會進入所選服務的上下文。

## 原有獨立引擎

以下介紹 `statstudio` MCP 與原有網頁。這條路徑**不需要安裝、啟動或授權 SPSS**，與新的 `statstudio-spss` 服務分開。

目前是 0.1.0 研究版。已實作 18 類常用分析，**尚未達到使用者要求的 SPSS 全功能、全算法、全輸出一致**。SPSS 僅在開發驗證時作為對照基準；同一固定樣本的數值通過，不能推論所有資料、預設與選項都一致。請先閱讀 [實测範圍](docs/validation.md) 與 [算法規格](docs/implemented-algorithms.md)。

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
| 輸出 | 結果表、直方圖／散布圖／長條圖、完整精度 JSON、含 SVG 圖的獨立 HTML |

未支援的選項會報錯，不會默默忽略。尚未涵蓋 GLM 多因子／重複量數、混合模型、存活分析、時間序列、複雜抽樣、多重插補、Bootstrap、全部事後比較、加權、SPSS 語法相容解析器及 SPV 原生輸出。獨立介面與報表不是 SPSS Viewer 的版面複製品。

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
