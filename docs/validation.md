# 與 IBM SPSS Statistics 30 的逐欄數值對照

實測日期：2026-10-12。**18 種獨立實作，在 2 份固定人工資料、明確列出的選項下，1,244 個選定數值欄位通過比較；本次設定的失敗欄位為 0。** 這是有限案例的數值驗證，不是全部程序、所有選項、任意資料或圖表呈現完全相同的證明。348 條 XML 命令仍只是 [命令與算法盤點](algorithm-catalog.md)。

產品執行及本報告的回歸測試不需要安裝 SPSS。只有開發者重新產生 oracle 時，需要另外安裝並取得 SPSS 授權。此次使用新的 Python 驅動 SPSS 引擎，只提交自製合成資料，未操作使用者的 SPSS GUI 或資料。

## 已保存的證據

- [逐欄報告](../validation/parity-report.json)：每個實作值、SPSS 值、絕對/相對誤差、容差、來源 table subtype、行列 category path、原始 `number` 字串及顯示文字。
- [明確分析選項](../validation/analysis-specs.json)、[比較程式](../validation/compare.py)、[OXML 解析器](../validation/oxml.py)。比對按表格和行列身分取值，不按數值尋找最接近的儲存格。
- [完整資料的 SPSS 語法](../validation/spss30/reference/commands.sps)、[缺失資料的 SPSS 語法](../validation/spss30/reference_missing/commands.sps)，同目錄保存 19 份原始 OXML、bootstrap OXML、每條命令狀態及輸出 SHA-256。兩組共 38 條程序執行的 error level 均為 0。
- [引擎環境](../validation/oracle-environment.json)：本機 `spssengine.exe` 檔案與產品版本均為 **30.0.0.0.0**；Windows NT 10.0.26200.0；引擎 SHA-256 `9094ae0ba4addda87c7ca1ff75ef16633341e9950592aefe2813cb12862ce52e`。詳細 Python 版本在各組 `metadata.json`。
- [初始 540 欄位報告](../validation/parity-report-initial-540.json) 保留，回歸測試核對它們仍存在、oracle 值未變且仍通過。[群標選項修正前報告](../validation/parity-report-before-label-option.json) 保留 1,049 通過、195 失敗的歷史結果。

SPSS 設定：英文輸出、`THREADS=1`、無權重、無篩選、無分割檔案。獨立數值庫：NumPy 2.5.4、pandas 3.0.6、SciPy 1.18.1、scikit-learn 1.9.1、statsmodels 0.15.0。每次重跑報告會重新記錄套件版本與獨立引擎 SHA-256。

## 資料與容差

[資料產生程式](../validation/generate_fixture.py) 僅用 Python 標準函式庫，固定 `random.Random(20261012)`，產生 60 列、10 欄，CSV 浮點數保留 10 位小數。兩邊讀入相同字串；SPSS `DATA LIST` 每欄明確指定 `F20.10`。

- [reference.csv](../tests/fixtures/reference.csv)：`x/y/z`、三組 `group`、二元 `binary`、`paired_a/paired_b`、`item1/item2/item3`。資料不完全共線，二元模型沒有完全分離。SHA-256 `52bb3f79113244c1ec53382a214cd5caeb79244dd1daac7f8f8cb60074da86ac`。
- [reference_missing.csv](../tests/fixtures/reference_missing.csv)：相同 60 列，在資料列（從 1 開始）2/x、3/y、6/z、9/paired_a、12/paired_b、15/item2 設為系統缺失。用來核對 available-case、pairwise 及 listwise 的不同有效樣本數。SHA-256 `56c8499d530c04491afd78b6438edbad14262c630cd0becb4783d7311d96a873`。

來源是 OMS OXML 的 `number` 屬性，通常約 14 位有效數字，**不是只含顯示小數位的文字，也不是內部二進位浮點數的逐位 dump**。比較不預先四捨五入；PCA 不作事後符號翻轉，群集不作事後群標排列。

| 欄位類型 | 固定通過條件 |
|---|---|
| 連續數值 | `abs(actual - expected) <= 1e-10 + 1e-8 * abs(expected)` |
| p 值與尾機率 | `abs(actual - expected) <= 1e-7 * abs(expected)`，絕對容差為 0，避免極小 p 值被寬鬆絕對容差掩蓋 |
| 個數、整數 df、等級和、群 ID | 精確相等；Welch 的非整數 df 採連續數值容差 |

全部已比對欄位的最大絕對誤差為 `4.77485e-12`，來自線性迴歸。容差沒有因差異而調寬。未檢查位元完全相同。

## 通過範圍

下表欄位數為「完整資料／含缺失資料」，只對列出的欄位及選項標記通過。完整規格以 JSON、`.sps` 及 `compare.py` 為準。

| 實作 | 欄位數 | 已測內容與必要選項 | 最大絕對誤差 |
|---|---:|---|---:|
| descriptive | 45 / 45 | x/y/z 的 N、mean、SD、variance、min/max/sum、偏態、超額峰態、SE、平均 CI、median、Q25/Q75；available-case、95% CI、Weibull `(n+1)p`，SPSS EXAMINE HAVERAGE | 7.29e-14 |
| frequencies | 20 / 20 | group/binary 各類別 frequency、percent、valid percent、cumulative valid percent | 3.34e-13 |
| crosstabs | 28 / 28 | group × binary 的 observed/expected、列與欄百分比、Pearson χ²/df/p、Cramér V | 4.13e-13 |
| ttest_one | 20 / 20 | x/y 對 0.25 的 N、mean、SD、SE、t/df/雙尾 p、差值與 95% CI | 1.73e-13 |
| ttest_independent | 24 / 24 | y 按 binary=0/1 分組；組摘要、以平均數為中心的 Levene、等變異及 Welch 兩列的 t/df/p/差值/SE/CI | 3.42e-13 |
| ttest_paired | 9 / 9 | paired_a−paired_b 的 N、差值mean/SD/SE、t/df/p/CI | 4.83e-14 |
| anova | 21 / 21 | y 按三組 group；組別 N/mean/SD、SS/df/MS、F/p、Levene F/p | 2.71e-12 |
| correlation | 15 / 15 | x/y/z 三對 Pearson r/p/N 及 95% Fisher CI；pairwise、SPSS BIAS(FALSE) | 3.56e-14 |
| linear_regression | 33 / 33 | y ~ intercept+x+z，ENTER、listwise；B/SE/β/t/p/CI、R²、adjusted R²、residual SE、F/p、ANOVA SS/df/MS | 4.78e-12 |
| logistic_regression | 33 / 33 | binary 高值=事件、intercept+x+z、ENTER/listwise；B/SE/Wald/df/p/OR/OR CI、−2LL、pseudo R²、LR/df/p/N、cut=.5 分類次數 | 4.13e-13 |
| reliability | 16 / 16 | 三個 item、listwise；N、item 數、raw/standardized α，刪項後 mean/variance、corrected item-total r、α | 5.64e-14 |
| pca | 21 / 21 | 三個 item 的相關矩陣、2 成分、listwise、無 rotation；初始 eigenvalues/%/累積%、原符號 loadings、初始/抽取 communalities | 5.12e-13 |
| mann_whitney | 8 / 8 | y 按 binary；各組 N/mean rank/rank sum、min U、漸近雙尾 p；continuity=no、有效 N=60/59 | 3.63e-13 |
| wilcoxon | 6 / 6 | 配對有效 N、零差數、正/負 rank sum、z、漸近雙尾 p；continuity=no；SPSS 語法成對順序明確對齊 | 1.69e-14 |
| kruskal | 9 / 9 | y 按 group=1/2/3；各組 N/mean rank、H/df/漸近 p | 2.63e-13 |
| factor | 13 / 13 | 三 item、相關矩陣、PAF、1 factor、無 rotation、listwise；最多 100 次、共同性 tolerance=1e-6；loadings、initial SMC/extraction communalities、KMO/Bartlett χ²/df/p | 2.71e-13 |
| hierarchical | 237 / 229 | x/z、無標準化、between-groups average linkage、平方歐氏距離、3 群、label_order=native；每次合併距離和兩個原始 case 代表、每列群 ID | 5.02e-14 |
| kmeans | 69 / 67 | x/z、無標準化、3 群、前 3 個完整個案初始中心、最多 300 次、label_order=native；各群中心、N、每列群 ID | 3.02e-14 |

總計：1,244 passed，0 failed。`tests/test_parity.py` 的 39 項測試通過：36 個方法/fixture 組合、2 個原始 oracle 完整性檢查、1 個初始 540 欄位保存檢查。測試固定預期比較欄位數，避免縮小範圍後仍顯示通過。正式專案 `.venv` 的完整測試另有 62 項通過（39 parity、18 engine、4 store、1 MCP），`pip check` 通過；62 是程式測試數，1,244 是其中對照的數值欄位数。

## 找到的差異及處理

**群 ID 是結果呈現的一部分。** 原本獨立引擎把群中心依字典順序排序後編號；SPSS 的群順序不同，即使兩者分組相同，直接比對群 ID 與同 ID 的中心仍有 195 個失敗欄位。歷史失敗報告保留原值。現在引擎提供明確 `label_order='native'`：K-means 保留擬合時中心編號；階層群集按群內最小原始 case 編號排列。驗證規格採此選項後逐欄通過，比較器沒有事後排列。既有 `label_order='centroid'` 預設仍不與本報告的 SPSS 群 ID 對齊。

**K-means 的預設與收斂流程尚未證明一致。** 本案例 SPSS 指定 `NOINITIAL KMEANS(NOUPDATE) CONVERGE(0)`，独立引擎明確取前 k 個完整個案；獨立引擎的 Lloyd 停止規則仍不同，未比較 iteration history 或存回的距離。兩份資料最後群別和中心一致，不能據此推論任意資料都一致。預設 k-means++、多次初始解及標準化也未涵蓋。

**估計法要明確指定。** Logistic 的 SPSS 係數收斂設定為 BCON=1e-10、LCON=0、ITERATE=100；獨立引擎為其明確數值實作。此處核對最終欄位，沒有核對每次迭代或宣稱兩套收斂判準相同。PAF 只驗證單因素與共同性 tolerance=1e-6。

**文件語法需要實機確認。** 本機 SPSS 30 的 Pearson CI 可執行語法為 `/CI=BIAS(FALSE) CILEVEL(95)`；曾嘗試的 suboption 等號寫法無法執行，最終基準已改為本機實測有效的括號寫法。資料與語法不因獨立結果而調整以隱藏數值差異。

## 尚未驗證

以下皆標記 **untested**，不得從上表推論相容：

- 權重（頻數、非整數或模型權重）、user-missing、字串類別、空類別、所有資料型態、不同語系與排序；目前 missing fixture 只測系統缺失。次數與交叉表的分類欄本身沒有缺失。
- 常數、近常數、极端尺度、N 很小、病態或奇異矩陣、完全/準完全分離、離群值、全缺失；數值穩定性與失敗時的警告文字。
- 有 ties/零差的非參數邊界、小樣本 exact/Monte Carlo、其他連續性修正；此組連續資料沒有特意建立這些條件。
- 其他 quantile 定義、bootstrap CI、非 Pearson 相關、所有交叉表檢定與殘差、t-test/ANOVA effect sizes、ANOVA post hoc、多因子 ANOVA、重複量測。
- categorical predictors/contrasts、stepwise、交互作用、無截距與更多模型、殘差/預測/影響量、logistic 的其他統計與迭代歷程。
- 多因素 PAF、所有 rotation（包括 varimax）、因子分數、其他抽取法、Heywood cases、重複 eigenvalues 的方向。
- 其他距離/linkage、距離 ties、所有 K-means 初始化/更新/停止模式、不同 k/seed、不同資料順序、群距離輸出。
- 小數顯示、顯著性標記、表格標籤/版面/完整欄位集合、plot renderer、圖形像素、SPV 或所有匯出格式；數值相符不代表畫面相同。
- 其他 SPSS build、作業系統、CPU/BLAS/數值套件版本；348 命令中未在此表列出的算法及選項。

## 重跑方式

在已安裝專案與相依套件的虛擬環境，從專案根目錄執行：

```powershell
python validation/compare.py
python -m pytest tests/test_parity.py -q -p no:cacheprovider
```

這兩個命令只讀已保存的 SPSS 數值，不啟動 SPSS。`compare.py` 會重建當次 JSON 報告，若有失敗欄位會以非零 exit code 結束；不會覆寫兩份歷史 baseline。

需重建 oracle 的開發者，在另外授權的 SPSS 30 Windows 安裝上使用：

```powershell
python validation/generate_fixture.py
& 'C:\Program Files\IBM\SPSS Statistics\Python3\python.exe' validation/run_spss_oracle.py --fixture reference
& 'C:\Program Files\IBM\SPSS Statistics\Python3\python.exe' validation/run_spss_oracle.py --fixture reference_missing
python validation/compare.py
```

Oracle 程式只接受兩個內建合成 fixture 名稱，會啟動並停止自己的引擎。`.sps` 內的 OMS 目的路徑記錄原始環境的絕對位置；跨機時用產生程式重新建立正確路徑，不應直接執行仍指向舊電腦的輸出位置。重建前先保留既有基準，變更 SPSS build 或資料雜湊後應作新的比較與審查。
