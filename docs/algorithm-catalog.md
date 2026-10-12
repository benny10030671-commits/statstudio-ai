# StatStudio AI：SPSS 30 算法、語法與一致性研究目錄

研究日期：2026-10-12。產品方向：**可在多台電腦獨立執行的統計工具；SPSS 只作開發時的對照基準，不是產品執行依賴。**

本文件記錄盤點階段對本機安裝物與 IBM 官方 30 版文件的觀察，以及獨立重建所需的驗證。**348 是找到的命令宣告數，並非 348 個已實作算法。本目錄不宣稱任何一項已達到 SPSS 完全一致。** 其後已進行實際 SPSS 30 數值對照；可重現的通過欄位、選項與未測邊界記錄於 [數值驗證報告](validation.md)。本目錄的「待測」表示整條命令的完整選項與邊界未經全面驗證，不能代替該報告。

## 1. 範圍、證據與狀態

本機唯讀來源：`C:\Program Files\IBM\SPSS Statistics\syntax_xml\*.xml`。完整機讀資料在同目錄 `command-catalog.json`，逐檔保留 SHA-256、命令原名、namespace、宣告屬性、Subcommand/Parameter/EnumValue 階層及順序。

| 盤點階段觀察 | 結果 |
|---|---:|
| XML 檔 / 解析成功 | 348 / 348 |
| Subcommand | 2,236 |
| Parameter | 7,481 |
| EnumValue | 4,908 |
| XML namespace 種類 | 3（包括無 namespace） |
| 部分行為經 IBM 30 文件核對的命令 | 21 |
| 盤點階段 SPSS 結果對照測試 | 0（後續實測見 [驗證報告](validation.md)） |

分類統計：model 119, data 107, basic 23, system 50, output 49。分類是研究整理，與 IBM 的 Base / Advanced / Regression 等授權套件不是同一件事。XML 存在不能證明本機授權允許執行。

| 標記 | 精確含義 |
|---|---|
| 發現 | 在指定本機 XML 中觀察到宣告 |
| 文件核對 | 此命令的部分行為與所列 IBM 30 文件核對；並非完整參數或公式核對 |
| 待測 | 整條命令的完整選項與邊界尚未全面驗證；部分數值欄位的後續結果另見驗證報告 |

觀察：`EXSMOOTH.xml` 的 `Name` 有兩個尾端空白，`TABLES.xml` 有一個；機讀資料同時保留原始值和去尾端空白後的名稱。解析器按 element local-name 處理不同 namespace，沒有把空參數群當成完整文法。

限制：XML 是語法宣告，不含完整公式、數值穩定技巧、執行時預設與所有合法組合。盤點階段未反編譯統計 DLL、未讀取使用者資料、未啟動 SPSS；後續 oracle 僅由自有引擎分析人工合成資料。IBM 的完整 Algorithms PDF 連結已由官方入口確認，但全文取得時 HTTP 403；以下只對已取得的官方 30 版頁面作有限核對，未以 31/32 版或舊版算法文件取代 30 版證據。參見 [IBM 30 文件入口](https://www.ibm.com/support/pages/ibm-spss-statistics-30-documentation)。

## 2. 獨立重建要達到的相容性

「算法一樣」需拆成四個可檢驗層次：

1. **分析語義**：同一批有效個案、變數型別、排序、權重、缺失值、虛擬變數/參考組、選項與預設。
2. **數值**：估計量、標準誤、檢定量、自由度、p 值、信賴區間、殘差/預測值與收斂狀態。
3. **結果結構**：相同表格與行列、相同分類編碼/群標、有效 N、警告與註腳。數學等價的符號翻轉/群標重排不等於呈現一致。
4. **呈現**：小數位、顯著性標記、空白/缺失符號、中文標籤、圖形尺度、匯出欄位與順序。數值相符不能自動推論圖表像素或 `.spv` 檔案格式相同。

建議每次執行儲存獨立的分析規格 JSON，包含資料摘要/雜湊、選取變數、缺失與權重政策、明確選項、數值庫版本、seed、警告和原始未四捨五入結果。自然語言 AI 只負責產生/解釋此規格，不以語言模型直接算統計或自行填補不存在的分析结果。

SPSS 對照 fixture 應保存：合成或已授權小型資料、明確 `.sps`、SPSS 完整 build、作業系統/語系、輸出設定、擷取到的 raw 值與顯示值、未完成/錯誤輸出。正常產品工作流程不需要這些 SPSS 元件。

數值閾值須逐字段宣告。例如先以 `abs(a-b) <= atol + rtol*abs(b)` 報告差異，整數 N/df/類別編碼則精確比較；不得先四捨五入再說一致。極小 p 值應比較 log-p 或尾機率誤差。對超出閾值的結果保留差異，不把容忍度調大來隱藏錯誤。位元相同、數值相符、顯示相符應分開標示。

## 3. 已核對的實作陷阱

以下為盤點階段文件核對的具體差異；後續已測的有限案例列於 [驗證報告](validation.md)，尚未涵蓋全部邊界。

| 位置 | IBM 30 文檔支持的行為 | 對獨立實作的影響 |
|---|---|---|
| `REGRESSION /MISSING` | 預設 listwise；可選 pairwise、均值代補和 user-missing 納入 | 不能使用一套全域 `dropna` 規則替代所有程序。S02 |
| `CORRELATIONS /MISSING` | 預設 pairwise；每對相關可有不同 N | 相關矩陣的 N 必須逐格保留；不應直接使用迴歸相同有效樣本。S13 |
| `DESCRIPTIVES` | MISSING=VARIABLE 預設；不提供 median/mode | 每個變數各自排除缺失；使用者若要中位數需另一程序，不能說完全複製 DESCRIPTIVES。S31、S32 |
| `PARTIAL CORR` | pairwise 模式下，df 基於底層零階相關的最小樣本數 | 一般資料庫或線性代數函式不會代處理此規則。S14 |
| `T-TEST` | 預設按分析排除缺失；CI 預設 .95；分組 cutpoint 為 `<` 與 `>=` | 需固定配對順序、差值方向與有效樣本。S06、S07 |
| `EXAMINE /PERCENTILES` | HAVERAGE 採 `(w+1)p` 位置；另有 WAVERAGE、ROUND、EMPIRICAL、AEMPIRICAL | 不可無條件套用數值庫預設 quantile。端點與分數權重仍需專門 fixture。S08 |
| `FREQUENCIES /STATISTICS` | 缺失預設排除；多重眾數顯示最小值 | 語法頁說第一個，使用說明明確說最小值；不要預設取第一個出現的值。S03、S33 |
| `WEIGHT` | 是 replication 語義；各程序對分數權重可能不同；非正/缺失權重不參與程序 | `freq_weights`、`var_weights`、sampling weights 不得混用。S09 |
| `CROSSTABS /METHOD` | 預設漸近；exact/MC 為另一模式；METHOD 的分數權重先四捨五入 | 一般 chi-square 和 exact/Monte Carlo 不可互換；seed和抽樣量須顯式。S10 |
| `UNIANOVA` | Type III SS 為預設；也有 I、II、IV | 非平衡/缺格資料用預設 type-I 的 ANOVA 會不同。S11 |
| `LOGISTIC REGRESSION /CRITERIA` | BCON=.001、ITERATE=20、LCON=0；任一生效停止條件達成便停止 | 不能以函式庫 optimizer 的預設 tolerance/maxiter 宣稱同結果。S15 |
| `FACTOR /EXTRACTION` | 未指定採 PC；顯式 EXTRACTION 而省略 ROTATION 時不旋轉；CRITERIA 位置影響哪個階段 | 預設 PCA、主軸因子與共同因子不能混稱同算法。生成語法與規格均需明確。S04 |
| `FACTOR /CRITERIA` | 萃取=.001、旋轉=.0001、迭代=25、Kaiser normalization 為預設 | 收斂條件與旋轉正規化須逐項對齐；矩陣比較還要保留軸序/符號。S05 |
| `CLUSTER` | 預設 between-groups average linkage 與平方歐氏距離 | 不能使用常見的 Euclidean + Ward 或單鏈預設取代。S16、S17 |
| `QUICK CLUSTER` | 預設2群、MXITER=10、CONVERGE=0、KMEANS(NOUPDATE) | 不能直接把 sklearn `KMeans` 預設當作 SPSS；初值算法亦不同。S18–S20 |
| `QUICK CLUSTER /CONVERGE` | 閾值 = 指定比例 × 初始中心最小距離；NOINITIAL 取前 n 個完整個案 | 此閾值與 inertia 相對改善不同；要保留輸入資料順序。S19 |
| `QUICK CLUSTER /PRINT ANOVA` | 所列 F 檢定是描述用，不適合直接作群差異推論 | AI 解釋層必須標示限制，不自動產生因果/顯著群差結論。S21 |
| `BOOTSTRAP` | 非整數權重與多重插補有限制，使用 listwise 樣本 | Bootstrap 不是任意統計量外面套一次 generic resample。S12 |
| legacy `NPAR TESTS M-W` | ties採平均rank，U取較小者；文檔描述總N≤40計exact | generic庫的auto門檻可能不同；continuity correction與exact ties仍待測。S36、S37 |
| OMS/輸出語言 | OATTRS 可保留語言不變 `text_eng`；XVERSION 指定 schema | oracle 以固定 schema 和語言不變欄位擷取，產品顯示中文標籤另處理。S22、S23 |

## 4. 常用程序的算法規格與待驗證清單

下列公式是獨立實作的標準數學規格/候選，不是對 IBM 二進位逐指令還原的聲明。任何未被本輪官方頁面核對的預設、邊界和數值技巧一律待測。

### 4.1 描述統計、分布與交叉表

相關命令：`FREQUENCIES`、`DESCRIPTIVES`、`EXAMINE`、`MEANS`、`CROSSTABS`、`CTABLES`、`SUMMARIZE`。

- 無權重樣本平均 `mean = sum(x)/n`；樣本變異數 `s² = sum((x-mean)²)/(n-1)`；標準誤 `s/sqrt(n)`。實作用穩定累積避免大偏移/小變異的消去誤差，但穩定算法本身不證明與 SPSS 位元相同。
- 需分清 `n=0/1`、所有值相同、±∞/非数值、極大/極小值；不能讓 JSON 輸出 NaN/Infinity 代替有意義的缺失及警告。
- 偏態/峰態：S34 已確認使用 normal=0 的 excess kurtosis；finite-sample correction 與標準誤公式尚待核對。未校正的第三/四中心矩不應直接冠上 SPSS 同名指標。需特別測 n=2/3/4 和常數列。
- 中位數/百分位：EXAMINE 的方法已在 S08 核對；FREQUENCIES 的 GROUPED、ties、分數權重須另驗。不能假設每個 SPSS 程序使用同一 percentile 定義。
- 次數表要分總百分比與有效百分比，缺失是否顯示、累積百分比基數、值標籤順序和數字/字串類別順序。
- 交叉表候選 Pearson `X² = Σ(O-E)²/E`、`E_ij = row_i*col_j/N`；df、空列/空欄、2×2 continuity correction、likelihood ratio、Fisher 雙尾規則、Cramér V、調整殘差須分欄實作和驗證。

最低 fixture：奇/偶樣本、重複值、至少兩眾數、空類別、system missing+user missing、分數/零/负權重、列標籤含中文、2×2稀疏表、3×4表、只剩1個有效類別。

### 4.2 t 檢定、ANOVA 與相關

相關命令：`T-TEST`、`ONEWAY`、`UNIANOVA`、`CORRELATIONS`、`NONPAR CORR`、`PARTIAL CORR`、`NPTESTS`。

- 單樣本 t 候選：`t=(mean-mu0)/(s/sqrt(n))`, `df=n-1`；配對檢定對每對完整的差值做此式，配對方向必須固定。
- 獨立樣本須分 pooled/equal variance 與 Welch：Welch 分母 `sqrt(s1²/n1+s2²/n2)`，自由度採 Welch–Satterthwaite；兩條結果同時存在時不能擅自刪去其中之一。
- Levene/Brown–Forsythe 的中心定義（mean/median/trimmed）要明確；不同中心可能導致不同 p 值。效果量 standardizer 和小樣本校正也要固定。
- 一因子 ANOVA：`F=MS_between/MS_within`；還需 Welch、Brown–Forsythe、線性對比、多重比較與效果量。多因子 UNIANOVA 預設 Type III，不可與簡單一因子公式混用。S11。
- Pearson `r` 與 t 轉換候選 `t=r*sqrt((n-2)/(1-r²))`；CI 方法與單/雙尾要明確，|r|=1與常數變數必須處理。Spearman tie ranks、Kendall ties/精確 p 規則屬另一組算法，不只替換相關係數。

最低 fixture：不等組大小、不等變異、缺失分布不一致、配對不完整、常數組、完美相關、ties、非平衡2×3因子設計、缺格設計；比較 N、df、effect size、CI 與 p，不只比較 mean。

Mann–Whitney 的特別對照：S36 規定平均ties秩、顯示較小 U；W按較小mean-rank的組，mean-rank平手則用分組對話中最後一組。但 S37 又簡寫 W為smaller group的rank sum，存在官方用語歧義，應設不等組大小且mean-rank排序相反的資料測試。S37 描述 N≤40 的exact規則；本輪沒有核對 exact ties 與continuity correction，不能直接採某函式庫 `auto` 當作相容。`NPTESTS` 與legacy `NPAR TESTS` 是不同介面，S38對group排序/測量層級有明文要求。

### 4.3 線性迴歸

相關命令：`REGRESSION`、`WLS`、`2SLS`、`LINEAR`、`LINEAR_RIDGE`、`LINEAR_LASSO`、`LINEAR_ELASTIC_NET`。

標準最小平方法模型 `y = Xβ + ε`；滿秩情況的解在數學上為 `(X'X)^-1 X'y`，實作候選應優先穩定 QR/SVD 求解而不是直接反矩陣。是否與 SPSS 的秩判定、tolerance 和欄位移除相同，仍需測試。

需記錄截距、變數/欄位順序、虛擬變數編碼、N、SSE/MSE、R²與調整R²、係數/標準化β、SE/t/df/p/CI、係數共變異矩陣、共線性診斷、預測/殘差/影響量。`REGWGT` 和全域 `WEIGHT` 的語義必須分开驗證。

最容易漏掉的情況：共線/近奇異、n≤p、完全擬合、no-intercept 的總平方和與 R² 定義、pairwise 非正定相關矩陣、user-missing include、stepwise 的進出條件和 ties。S02 核對了缺失模式；S25 顯示 ORIGIN 會影響描述統計的基準，故 no-intercept 不是只刪去一欄截距。

第一批實作應限定明確的 ENTER 線性迴歸設定；逐步選擇、WLS、2SLS和正則化分別建立測試，不能因同屬線性模型就套用一致聲明。

### 4.4 邏輯斯迴歸與其他廣義模型

相關命令：`LOGISTIC REGRESSION`、`NOMREG`、`PLUM`、`GENLIN`、`GENLINMIXED`、`MIXED`、`PROBIT`。

二元 logit 候選 `p=1/(1+exp(-Xβ))`，最大化 Bernoulli log-likelihood；實作需使用穩定 logistic/logaddexp。需記錄事件編碼、參考類別、對比編碼、截距、權重、起始係數、Hessian/資訊矩陣、更新規則、step halving 與停止條件。

S15 已核對 SPSS 的 BCON/LCON/ITERATE；尚未核對完整數值更新算法。即使用相同 likelihood，Newton、IRLS、BFGS 在有限迭代、分離資料或不同停止條件下可能輸出不同係數/警告。

輸出項目：係數、SE、Wald、df、p、Exp(B)/OR CI、-2LL、模型比較、分類表、pseudo-R²、迭代歷史、收斂/分離警告。NOMREG、PLUM、GENLIN、混合模型的 link/distribution、參考類別、門檻、積分/近似、ML/REML、共變異結構與 df 方法需逐項另外規格化。

最低 fixture：正常收斂、稀有事件、完全/準完全分離、單一事件值、缺失類別、類別參考組不同、近共線、超大線性預測值；不收斂必須明確回報，不能默默顯示最後係數為成功。

### 4.5 因子、主成分與信度

相關命令：`FACTOR`、`RELIABILITY`、`CATPCA`、`PRINCALS`、`HOMALS`。

PCA 候選對相關/共變異矩陣分解特徵值與向量，載荷依指定尺度建立；共同因子 PAF/ML/ULS/GLS 含共同性與誤差估計，不能以 PCA 代替。S04 已核對可選方法。

FACTOR 需固定相關/共變異矩陣、缺失策略、共同性初值、萃取因子數或 eigenvalue 規則、旋轉方法、Kaiser normalization、收斂。S05 的預設為 extraction .001 / rotation .0001 / 25次，CRITERIA 位置本身也會影響運算。

S35 補充：只指定 VARIABLES 時預設 PC+varimax；即使 ANALYSIS 只選其中幾個變數，預設listwise可能仍按 VARIABLES 的完整列表決定有效個案，故「結果用同一組變數」不必然代表同一批樣本。

結果比較至少含初始 eigenvalues、萃取共同性、解釋變異、未旋轉/旋轉載荷、pattern/structure/factor correlation、KMO、Bartlett、factor-score 係數。S24 對輸出組件有明確說明。特徵向量符號與軸順序可能在數學上任意；需先作數學對齊診斷，再獨立檢查 SPSS 的符號/順序呈現規則。

信度候選 Cronbach alpha `k/(k-1)*(1-sum(var(item))/var(sum(items)))`；需区分 raw/standardized alpha、缺失剔除、反向題是否由使用者指定、item-total 是否扣除該題、alpha-if-deleted、ICC 模型/型態/一致性與 CI。不能自動猜測反向題後仍声称同一分析。

最低 fixture：明確雙因子資料、重根、singular correlation、單一因子、Heywood case、常數題、負相關題、listwise/pairwise、旋轉前後符號、不同因子分數法。

### 4.6 群集

相關命令：`QUICK CLUSTER`、`CLUSTER`、`TWOSTEP CLUSTER`、`PROXIMITIES`。

K-means 的一般目標是群內平方距離和；但結果由初始化、更新時機、收斂判定、空群處理與最後分類決定。SPSS 30 的批次更新、10次上限及以初始中心距離決定閾值，已由 S18–S20 核對。不得把預設 k-means++、多次 restart、一般 inertia tolerance 當作同一設定。

S30 描述最後還會再分類並更新最終群均值，需同時驗證用於分類的中心與最終中心/存回距離。先以顯式初始中心建立基本一致性，再研究自動中心選擇的全流程；`NOINITIAL` 模式與資料順序相关。

階層群集要固定距離是否平方、標準化、linkage 更新、ties打破規則、樹狀圖縮放和葉序；預設是 BAVERAGE + squared Euclidean。Ward 的不同庫版本/定義不可直接以名稱判相同。TWOSTEP 的預群集、距離、BIC/AIC、自動群數和資料順序尚未核對。

最低 fixture：顯式中心、重複點、距離ties、空群、k>unique points、變數尺度不同、亂序、缺失pairwise、停止在最大迭代。數值比較需保留群 ID 和可選 permutation-aligned 診斷兩份，不能只對齊後藏掉標籤差異。

### 4.7 圖表、表格與匯出

相關命令：`GRAPH`、`GGRAPH`、`CTABLES`、`OUTPUT EXPORT`、`OMS`、`OUTPUT MODIFY`、`WORKBOOK EXPORT`。

產品應以同一份未四捨五入統計結果生成表格與圖，不在呈現層重算。每個 cell 保留 `value`、`display`、`format`、`unit`、`missing_reason`、`footnote_ids`；每個 table 保留穩定 ID、row/column dimension、labels、排序、N 基數與分析選項。

圖形另需規格：histogram bin edges/閉區間規則、百分比基數、boxplot 四分位/whisker/outlier 規則、缺失/權重、軸範圍、誤差棒 CI/SE/SD、資料點排序/抖動seed。不同繪圖庫的預設會不同，須顯式設定和對照；本輪未分析 IBM chart renderer。

Oracle 可用 OMS OXML/SAV 擷取結構，S22、S23 支持此用途。產品自身輸出 HTML/CSV/JSON/圖片等開放格式；是否需要 `.spv` 匯入/寫出是另一個未實作規格。S26 指出 OMS 和 OUTPUT EXPORT 的格式/版面功能有差異；兩者輸出不能假設完全互換。

## 5. 跨程序共通控制

| 控制 | 必須保存/驗證 |
|---|---|
| 資料字典 | numeric/string、measurement level、value labels、格式、日期基準、編碼 |
| 缺失 | system-missing 與每變數 user-missing 規則；有效值0不是缺失 |
| 權重 | replication/analytic/sampling 類型、分數處理、零/負/缺失、加權N与實際行數 |
| 篩選/分組 | FILTER、SELECT IF、SPLIT FILE、資料排序、TEMPORARY 的有效範圍 |
| 隨機 | RNG算法+seed/狀態，不只是同一个整數；S26 的 MTINDEX/SEED 區別需遵守 |
| 估計 | 初值、迭代上限、收斂量/尺度、矩陣秩判定、ties、step-halving |
| 浮點 | dtype、數值庫/BLAS版本、執行緒；跨機器按明確容差檢查 |
| 呈現 | locale、decimal separator、missing標記、p格式、有效位數、表格註腳 |
| 警告 | 空樣本、不收斂、分離、奇異矩陣、超出方法範圍，不靜默降級 |

Bootstrap 和多重插補有不同的有效樣本與合併規則，S12、S27 已顯示部分限制；不能把它們視為對所有程序透明的裝飾選項。

## 6. 未解問題與下一輪研究

1. 取得並逐章核對 SPSS 30 Algorithms 全文；当前未具備完整公式/數值細節的證據。公開方法可以用獨立程式實作，但不能補造未確認的 SPSS 內部行為。
2. 固定本機 SPSS 精確 build、修補/選配模組與授權可執行範圍；S28 證明版本差異可能涉及輸出/語法行為。
3. 首批每一程序建立含正常與退化資料的合成 fixture，擷取 raw 值、顯示值、警告，形成可在無SPSS電腦執行的已保存基準。
4. 對偏態/峰態、weighted quantile、Fisher雙尾、Levene中心、WLS、缺失pairwise、logistic分離、FACTOR符號、群集ties、圖形四分位進行專門邊界實驗。
5. XML 與語法文件可能不一致；完整解析器還需處理 abbreviation、命令別名、子命令順序、變數列表、macro/轉換、字串與執行狀態，不可直接由 XML 自動斷言合法。
6. 每個功能的支援狀態必須獨立於發現目錄。對未實作或未通過的選項，在 AI 規格驗證層明確拒絕或標待測，不改用近似算法後聲稱相同。

優先驗證順序：先做無權重/無user-missing的描述統計、次數表、t檢定、Pearson、OLS；接續2×2/多維交叉表、ANOVA、信度；再驗證logistic收斂、PCA/varimax、明確初始中心K-means和階層群集；最後擴展權重、特殊缺失、exact/Monte Carlo、PAF/ML、stepwise及進階模型。這是研究與驗收排序，不代表目前支援範圍。

## 7. 可重現的目錄生成

生成器：工作區 `work/catalog-research/build_catalog.py`，只使用 Python 標準函式庫。它僅讀本機 XML，輸出本文件與 JSON；不執行 SPSS。研究來源及文字模板在同一工作目錄。重新生成：

```powershell
python work/catalog-research/build_catalog.py --source 'C:\Program Files\IBM\SPSS Statistics\syntax_xml' --output outputs/statstudio-ai/docs
```

驗證了348檔均可解析、正規化名稱唯一、所有2236個參數群均保留，並以 SHA-256 保存檔案身分。這些驗證只針對盤點完整性，不是統計結果測試。

本次manifest SHA-256：`fba6eccc699e1506f96933ef2e6d2162adf9f2a83123554bff86f77d94d91f34`。計算方式見 JSON 的 `manifest_definition`。

## 8. 官方來源

以下各來源均指向 SPSS Statistics 30，取用日期 2026-10-12；只轉述必要行為與建立測試問題，未附原文手冊。`S29` 為待取得全文的來源，不能視為公式已核對。

- **S01** [IBM SPSS Statistics 30 Documentation](https://www.ibm.com/support/pages/ibm-spss-statistics-30-documentation)：官方文件入口，含 Algorithms 與 Command Syntax Reference；未將新版文檔混作30版（已讀入口頁）
- **S02** [MISSING Subcommand (REGRESSION command)](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=regression-missing-subcommand-command)：listwise/pairwise/meansubstitution 與 user-missing（官方頁面可檢索內容）
- **S03** [STATISTICS subcommand (FREQUENCIES command)](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=frequencies-statistics-subcommand-command)：統計量選擇與眾數多解規則（官方頁面可檢索內容）
- **S04** [EXTRACTION Subcommand (FACTOR command)](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=factor-extraction-subcommand-command)：PC/PAF/ML/ULS 等方法、子命令順序與省略旋轉行為（官方頁面可檢索內容）
- **S05** [CRITERIA Subcommand (FACTOR command)](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=factor-criteria-subcommand-command)：因子數、Kaiser 正規化、萃取/旋轉收斂與迭代預設（官方頁面可檢索內容）
- **S06** [T-TEST](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=reference-t-test)：單樣本、獨立、配對；MISSING=ANALYSIS 與信賴區間預設（官方頁面可檢索內容）
- **S07** [Independent-Samples T-Test Define Groups](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=test-independent-samples-t-define-groups)：指定兩組與 cutpoint 的界線規則（官方頁面可檢索內容）
- **S08** [PERCENTILES Subcommand (EXAMINE command)](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=examine-percentiles-subcommand-command)：HAVERAGE/WAVERAGE/ROUND/EMPIRICAL/AEMPIRICAL 的位置定義（官方頁面可檢索內容）
- **S09** [Overview (WEIGHT command)](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=weight-overview-command)：replication 權重、非整數、零/负/缺失權重、session 持續性（官方頁面可檢索內容）
- **S10** [METHOD subcommand (CROSSTABS command)](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=crosstabs-method-subcommand-command)：漸近/exact/Monte Carlo，METHOD 對權重四捨五入（官方頁面可檢索內容）
- **S11** [GLM Univariate Analysis](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=features-glm-univariate-analysis)：Type I/II/III/IV SS，III 預設，WLS 與輸出範圍（官方頁面可檢索內容）
- **S12** [Procedures that support bootstrapping](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=bootstrapping-procedures-that-support)：不支援非整數權重/多重插補、強制 listwise 的限制（官方頁面可檢索內容）
- **S13** [CORRELATIONS](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=reference-correlations)：Pearson、pairwise 預設、雙尾預設、CI method（官方頁面可檢索內容）
- **S14** [Partial Correlations Options](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=correlations-partial-options)：pairwise 部分相關 df 使用最小底層相關樣本數（官方頁面可檢索內容）
- **S15** [CRITERIA Subcommand (LOGISTIC REGRESSION command)](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=regression-criteria-subcommand-logistic-command)：BCON=.001、ITERATE=20、LCON=0 與停止條件（官方頁面可檢索內容）
- **S16** [METHOD Subcommand (CLUSTER command)](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=cluster-method-subcommand-command)：階層群集方法、預設 between-groups average linkage（官方頁面可檢索內容）
- **S17** [Example (CLUSTER command)](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=cluster-example-command)：預設平方歐氏距離、樹狀圖、群集成員輸出（官方頁面可檢索內容）
- **S18** [QUICK CLUSTER](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=reference-quick-cluster)：預設2群、max_iter=10、converge=0、listwise、NOUPDATE（官方頁面可檢索內容）
- **S19** [CRITERIA Subcommand (QUICK CLUSTER command)](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=cluster-criteria-subcommand-quick-command)：well-separated 初值、NOINITIAL=前n完整個案、停止閾值尺度（官方頁面可檢索內容）
- **S20** [METHOD Subcommand (QUICK CLUSTER command)](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=cluster-method-subcommand-quick-command)：逐次/批次更新與CLASSIFY差異（官方頁面可檢索內容）
- **S21** [PRINT Subcommand (QUICK CLUSTER command)](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=cluster-print-subcommand-quick-command)：群集ANOVA僅描述，群數和中心報表（官方頁面可檢索內容）
- **S22** [OUTFILE Keyword (OMS command)](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=command-outfile-keyword-oms)：OXML/SAV擷取方式，僅用在oracle（官方頁面可檢索內容）
- **S23** [OATTRS and XVERSION Subcommands (SET command)](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=set-oattrs-xversion-subcommands-command)：OXML schema版本與語言不變標籤text_eng（官方頁面可檢索內容）
- **S24** [PRINT Subcommand (FACTOR command)](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=factor-print-subcommand-command)：初始/萃取/旋轉矩陣、KMO/Bartlett與輸出排序（官方頁面可檢索內容）
- **S25** [DESCRIPTIVES Subcommand (REGRESSION command)](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=regression-descriptives-subcommand-command)：預設不顯示，ORIGIN時以0均值基準計算統計（官方頁面可檢索內容）
- **S26** [Programming and Data Management for IBM SPSS Statistics: A Guide for IBM SPSS Statistics and SAS Users](https://www.ibm.com/docs/SSLVMB_30.0.0/pdf/IBM_SPSS_Statistics_Data_Management_SAS.pdf)：MTINDEX 與 RNG=MT；OMS與OUTPUT EXPORT的格式差異（官方PDF可檢索段落；未核對全文）
- **S27** [Overview (MULTIPLE IMPUTATION command)](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=imputation-overview-multiple-command)：AUTO/monotone/FCS，分類/連續變數與插補資料集（官方頁面可檢索內容）
- **S28** [IBM SPSS Statistics 30.0 Fix List](https://www.ibm.com/support/pages/ibm-spss-statistics-300-fix-list-1)：版本修補會影響輸出與語法提示，須固定build版本（官方頁面可檢索內容）
- **S29** [IBM SPSS Statistics Algorithms](https://www.ibm.com/docs/SSLVMB_30.0.0/pdf/IBM_SPSS_Statistics_Algorithms.pdf)：待補讀公式、數值技巧與特殊情況；不可視為已完成算法核對（官方入口連結已確認，全文HTTP 403）
- **S30** [Overview (QUICK CLUSTER command)](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=cluster-overview-quick-command)：選中心、迭代、最後分類與最終中心更新的四段流程（官方頁面可檢索內容）
- **S31** [DESCRIPTIVES](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=reference-descriptives)：MISSING=VARIABLE 預設；統計量列表（官方頁面可檢索內容）
- **S32** [STATISTICS Subcommand (DESCRIPTIVES command)](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=descriptives-statistics-subcommand-command)：預設mean/SD/min/max；不支援median/mode，非法統計量導致不執行（官方頁面可檢索內容）
- **S33** [Frequencies Statistics](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=frequencies-statistics)：多眾數報最小值；樣本變異數分母n-1（官方頁面可檢索內容）
- **S34** [Descriptives Options](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=descriptives-options)：樣本變異數和excess kurtosis定義，未含有限樣本偏誤校正公式（官方頁面可檢索內容）
- **S35** [Overview (FACTOR command)](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=factor-overview-command)：最小語法PC+varimax、子命令順序、VARIABLES與ANALYSIS的缺失基數差異（官方頁面可檢索內容）
- **S36** [Two-Independent-Samples Test Types](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=tests-two-independent-samples-test-types)：Mann–Whitney ties平均rank、較小U、W與mean-rank的規則（官方頁面可檢索內容）
- **S37** [M-W Subcommand (NPAR TESTS command)](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=tests-m-w-subcommand-npar-command)：legacy M-W exact/normal樣本數條件；W用語與其他官方頁有歧義待測（官方頁面可檢索內容）
- **S38** [INDEPENDENT Subcommand (NPTESTS command)](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=nptests-independent-subcommand-command)：group依升序定義、兩組/多組自動選檢定、measurement level條件（官方頁面可檢索內容）

## 9. 完整命令與參數群索引

所有條目均為本機「發現」。表內「文件核對」只表示部分行為核對；「待測」表示整條命令完整選項與邊界未全面驗證。部分實作的逐欄數值對照結果另見 [驗證報告](validation.md)。完整 Parameter/EnumValue 与來源雜湊見 JSON。

### basic（23）

| 命令 | 本機 XML | 參數群（Subcommand） | 文件狀態 / 結果驗證 |
|---|---|---|---|
| `ANOVA` | `ANOVA.xml` | GLOBAL_PARAMS, VARIABLES, COVARIATES, MAXORDERS, METHOD, STATISTICS, MISSING | 待測 / 待測 |
| `CODEBOOK` | `CODEBOOK.xml` | VARINFO, FILEINFO, STATISTICS, OPTIONS | 待測 / 待測 |
| `CORRELATIONS` | `CORRELATIONS.xml` | GLOBAL_PARAMS, VARIABLES, MISSING, PRINT, MATRIX, STATISTICS, CI | 文件核對 / 待測 |
| `CROSSTABS` | `CROSSTABS.xml` | GLOBAL_PARAMS, TABLES, MISSING, WRITE, FORMAT, COUNT, CELLS, STATISTICS, METHOD, BARCHART, HIDESMALLCOUNTS, SHOWDIM | 文件核對 / 待測 |
| `CSDESCRIPTIVES` | `CSDESCRIPTIVES.xml` | PLAN, JOINTPROB, SUMMARY, MEAN, SUM, RATIO, STATISTICS, SUBPOP, MISSING | 待測 / 待測 |
| `CSTABULATE` | `CSTABULATE.xml` | PLAN, JOINTPROB, TABLES, CELLS, STATISTICS, TEST, SUBPOP, MISSING | 待測 / 待測 |
| `DESCRIPTIVES` | `DESCRIPTIVES.xml` | GLOBAL_PARAMS, MISSING, SAVE, STATISTICS, SORT | 文件核對 / 待測 |
| `EXAMINE` | `EXAMINE.xml` | GLOBAL_PARAMS, COMPARE, TOTAL, NOTOTAL, ID, PERCENTILES, PLOT, STATISTICS, CINTERVAL, MESTIMATORS, MISSING | 文件核對 / 待測 |
| `FLEISS MULTIRATER KAPPA` | `FLEISS MULTIRATER KAPPA.xml` | GLOBAL_PARAMS, MISSING, CRITERIA, PRINT | 待測 / 待測 |
| `FREQUENCIES` | `FREQUENCIES.xml` | GLOBAL_PARAMS, FORMAT, MISSING, BARCHART, PIECHART, HISTOGRAM, GROUPED, NTILES, PERCENTILES, STATISTICS, ORDER | 文件核對 / 待測 |
| `MEANS` | `MEANS.xml` | GLOBAL_PARAMS, MISSING, CELLS, STATISTICS | 待測 / 待測 |
| `MULT RESPONSE` | `MULT RESPONSE.xml` | GROUPS, VARIABLES, FREQUENCIES, TABLES, MISSING, FORMAT, BASE, CELLS | 待測 / 待測 |
| `NONPAR CORR` | `NONPAR CORR.xml` | GLOBAL_PARAMS, VARIABLES, PRINT, SAMPLE, MISSING, MATRIX, CI | 待測 / 待測 |
| `NPAR TESTS` | `NPAR TESTS.xml` | GLOBAL_PARAMS, CHISQUARE, EXPECTED, K-S, RUNS, BINOMIAL, MCNEMAR, SIGN, WILCOXON, MH, COCHRAN, FRIEDMAN, KENDALL, M-W, M-W, W-W, MOSES, K-W, J-T, MEDIAN, MISSING, SAMPLE, STATISTICS, METHOD, KS_SIM | 文件核對 / 待測 |
| `NPTESTS` | `NPTESTS.xml` | MISSING, CRITERIA, ONESAMPLE TEST, INDEPENDENT, RELATED TEST | 文件核對 / 待測 |
| `ONEWAY` | `ONEWAY.xml` | GLOBAL_PARAMS, CRITERIA, POLYNOMIAL, CONTRAST, POSTHOC, RANGES, STATISTICS, PLOT MEANS, MISSING, MATRIX, TEMPLATE, ES | 待測 / 待測 |
| `PARTIAL CORR` | `PARTIAL CORR.xml` | GOLBAL_PARAMS, VARIABLES, SIGNIFICANCE, STATISTICS, FORMAT, MISSING, MATRIX | 文件核對 / 待測 |
| `PROPORTIONS` | `PROPORTIONS.xml` | MISSING, CRITERIA, SUCCESS, ONESAMPLE, PAIREDSAMPLES, INDEPENDENTSAMPLES | 待測 / 待測 |
| `RATIO STATISTICS` | `RATIO STATISTICS.xml` | GLOBAL_PARAMS, MISSING, OUTFILE, PRINT | 待測 / 待測 |
| `RELIABILITY` | `RELIABILITY.xml` | GLOBAL_PARAMS, VARIABLES, SCALE, MODEL, STATISTICS, SUMMARY, ICC, METHOD, MISSING, MATRIX | 待測 / 待測 |
| `SUMMARIZE` | `SUMMARIZE.xml` | GLOBAL_PARAMS, TABLES, TITLE, FOOTNOTE, CELLS, MISSING, FORMAT, STATISTICS | 待測 / 待測 |
| `T-TEST` | `T-TEST.xml` | GLOBAL_PARAMS, TESTVAL, VARIABLE, VARIABLES, MISSING, CRITERIA, ES | 文件核對 / 待測 |
| `WEIGHTED KAPPA` | `WEIGHTED KAPPA.xml` | GLOBAL_PARAMS, MISSING, CRITERIA, PRINT | 待測 / 待測 |

### model（119）

| 命令 | 本機 XML | 參數群（Subcommand） | 文件狀態 / 結果驗證 |
|---|---|---|---|
| `2SLS` | `2SLS.xml` | GLOBAL_PARAMS, EQUATION, INSTRUMENTS, ENDOGENOUS, CONSTANT, NOCONSTANT, PRINT, SAVE, APPLY | 待測 / 待測 |
| `ACF` | `ACF.xml` | GLOBAL_PARAMS, DIFF, SDIFF, NOLOG, LN, SEASONAL, MXAUTO, SERROR, PACF, APPLY, PERIOD | 待測 / 待測 |
| `AIM` | `AIM.xml` | CATEGORICAL, CONTINUOUS, CRITERIA, MISSING, PLOT | 待測 / 待測 |
| `ALSCAL` | `ALSCAL.xml` | GLOBAL_PARAMS, FILE, INPUT, SHAPE, LEVEL, CONDITION, MODEL, METHOD, CRITERIA, PRINT, PLOT, OUTFILE, MATRIX | 待測 / 待測 |
| `ANACOR` | `ANACOR.xml` | GLOBAL_PARAMS, DIMENSION, NORMALIZATION, VARIANCES, PRINT, PLOT, MATRIX | 待測 / 待測 |
| `AREG` | `AREG.xml` | GLOBAL_PARAMS, METHOD, CONSTANT, NOCONSTANT, RHO, MXITER, APPLY | 待測 / 待測 |
| `ARIMA` | `ARIMA.xml` | GLOBAL_PARAMS, MODEL, P, D, Q, SP, SD, SQ, AR, MA, SAR, SMA, REG, CON, MXITER, MXLAMB, SSQPCT, PAREPS, CINPCT, APPLY, FORECAST | 待測 / 待測 |
| `BAYES ANOVA` | `BAYES ANOVA.xml` | GLOBAL_PARAMS, CRITERIA, DESIGN, INFERENCE, ESTBF, PRIOR, PLOT | 待測 / 待測 |
| `BAYES CORRELATION` | `BAYES CORRELATION.xml` | MISSING , CRITERIA , INFERENCE, ESTBF | 待測 / 待測 |
| `BAYES INDEPENDENT` | `BAYES INDEPENDENT.xml` | MISSING , CRITERIA , INFERENCE, ESTBF, PRIOR | 待測 / 待測 |
| `BAYES LOGLINEAR` | `BAYES LOGLINEAR.xml` | CRITERIA , INFERENCE, TABLE, ESTBF, PRINT | 待測 / 待測 |
| `BAYES ONESAMPLE` | `BAYES ONESAMPLE.xml` | MISSING , CRITERIA, INFERENCE, DATA, PRIOR | 待測 / 待測 |
| `BAYES REGRESSION` | `BAYES REGRESSION.xml` | GLOBAL_PARAMS, CRITERIA, DESIGN, INFERENCE, ESTBF, PRIOR, PREDICT, SAVE, OUTFILE, PLOT, FTEST | 待測 / 待測 |
| `BAYES RELATED` | `BAYES RELATED.xml` | MISSING , CRITERIA , INFERENCE, PAIR, PRIOR | 待測 / 待測 |
| `BAYES REPEATED` | `BAYES REPEATED.xml` | CRITERIA, INFERENCE, DESIGN, ESTBF, PLOT | 待測 / 待測 |
| `BOOTSTRAP` | `BOOTSTRAP.xml` | SAMPLING, VARIABLES, CRITERIA, MISSING | 文件核對 / 待測 |
| `CATPCA` | `CATPCA.xml` | GLOBAL_PARAMS, ANALYSIS, DISCRETIZATION, MISSING, SUPPLEMENTARY, CONFIGURATION, DIMENSION, NORMALIZATION, MAXITER, CRITITER, PRINT, PLOT, SAVE, OUTFILE, ROTATION, RESAMPLE | 待測 / 待測 |
| `CATREG` | `CATREG.xml` | GLOBAL_PARAMS, ANALYSIS, DISCRETIZATION, MISSING, SUPPLEMENTARY, INITIAL, MAXITER, CRITITER, REGULARIZATION, RESAMPLE, PRINT, PLOT, SAVE, OUTFILE | 待測 / 待測 |
| `CCF` | `CCF.xml` | GLOBAL_PARAMS, DIFF, SDIFF, PERIOD, NOLOG, LN, SEASONAL, MXCROSS, APPLY | 待測 / 待測 |
| `CLUSTER` | `CLUSTER.xml` | MISSING, MEASURE, METHOD, SAVE, PRINT, PLOT, MATRIX, ID | 文件核對 / 待測 |
| `CNLR` | `CNLR.xml` | FILE, OUTFILE, PRED, SAVE, CRITERIA, BOUNDS, LOSS, BOOTSTRAP | 待測 / 待測 |
| `CONJOINT` | `CONJOINT.xml` | GLOBAL_PARAMS, DATA, SEQUENCE, RANK, SCORE, SUBJECT, FACTORS, PRINT, UTILITY, PLOT | 待測 / 待測 |
| `CORRESPONDENCE` | `CORRESPONDENCE.xml` | GLOBAL_PARAMS, TABLE, SUPPLEMENTARY, EQUAL, MEASURE, STANDARDIZE, DIMENSIONS, NORMALIZATION, PRINT, PLOT, OUTFILE | 待測 / 待測 |
| `COXREG` | `COXREG.xml` | GLOBAL_PARAMS, STATUS, STRATA, CATEGORICAL, CONTRAST, METHOD, MISSING, PRINT, CRITERIA, PLOT, PATTERN, OUTFILE, SAVE, EXTERNAL | 待測 / 待測 |
| `CSCOXREG` | `CSCOXREG.xml` | GLOBAL_PARAMS, VARIABLES, PLAN, JOINTPROB, MODEL, CUSTOM, CRITERIA, STATISTICS, TEST, TESTASSUMPTIONS, DOMAIN, MISSING, SURVIVALMETHOD, PRINT, SAVE, PLOT, PATTERN, OUTFILE | 待測 / 待測 |
| `CSGLM` | `CSGLM.xml` | GLOBAL_PARAMS, PLAN, JOINTPROB, MODEL, INTERCEPT, CUSTOM, EMMEANS, CRITERIA, STATISTICS, TEST, DOMAIN, MISSING, PRINT, SAVE, OUTFILE | 待測 / 待測 |
| `CSLOGISTIC` | `CSLOGISTIC.xml` | GLOBAL_PARAMS, PLAN, JOINTPROB, MODEL, INTERCEPT, CUSTOM, ODDSRATIOS, CRITERIA, STATISTICS, TEST, DOMAIN, MISSING, PRINT, SAVE, OUTFILE | 待測 / 待測 |
| `CSORDINAL` | `CSORDINAL.xml` | GLOBAL_PARAMS, PLAN, JOINTPROB, MODEL, LINK, CUSTOM, ODDSRATIOS, CRITERIA, STATISTICS, NONPARALLEL, TEST, DOMAIN, MISSING, PRINT, SAVE, OUTFILE | 待測 / 待測 |
| `CURVEFIT` | `CURVEFIT.xml` | GLOBAL_PARAMS, VARIABLES, MODEL, CIN, UPPERBOUND, CONSTANT, NOCONSTANT, PLOT, ID, PRINT, SAVE, APPLY, TEMPLATE | 待測 / 待測 |
| `DCR` | `DCR.xml` | GLOBAL_PARAMS, MAXITER, DISSIMILARITY, POWERDISSIMILARITY, NORM, CRITERIA, PRINT | 待測 / 待測 |
| `DETECTANOMALY` | `DETECTANOMALY.xml` | VARIABLES, HANDLEMISSING, CRITERIA, SAVE, OUTFILE, PRINT | 待測 / 待測 |
| `DISCRIMINANT` | `DISCRIMINANT.xml` | GLOBAL_PARAMS, GROUPS, VARIABLES, SELECT, ANALYSIS, OUTFILE, METHOD, TOLERANCE, MAXSTEPS, FIN, FOUT, PIN, POUT, VIN, FUNCTIONS, PRIORS, SAVE, ANALYSIS, MISSING, MATRIX, HISTORY, ROTATE, CLASSIFY, STATISTICS, PLOT | 待測 / 待測 |
| `DMCLUSTER` | `DMCLUSTER.xml` | CATEGORICAL, CONTINUOUS, CRITERIA, DISTANCE, HANDLENOISE, INFILE, MEMALLOCATE, MISSING, NOSTANDARDIZE, NUMCLUSTERS, OUTFILE, PRINT, SAVE, VIEWMODEL | 待測 / 待測 |
| `DMLOGISTIC` | `DMLOGISTIC.xml` | GLOBAL_PARAMS, CATEGORICAL, CONTRAST, METHOD, SELECT, NOORIGIN, ORIGIN, ID, PRINT, CRITERIA, CLASSPLOT, MISSING, CASEWISE, SAVE, OUTFILE, EXTERNAL | 待測 / 待測 |
| `DMROC` | `DMROC.xml` | GLOBAL_PARAMS, MISSING, CRITERIA, PLOT, PRINT | 待測 / 待測 |
| `DMTREE` | `DMTREE.xml` | GLOBAL_PARAMS, TREE, DEPCATEGORIES, PRINT, GAIN, PLOT, RULES, SAVE, METHOD, GROWTHLIMIT, VALIDATION, CHAID, CRT, QUEST, COSTS, PRIORS, SCORES, PROFITS, INFLUENCE, OUTFILE, MISSING, TARGETRESPONSE | 待測 / 待測 |
| `EXSMOOTH` | `EXSMOOTH.xml` | GLOBAL_PARAMS, MODEL, PERIOD, SEASFACT, ALPHA, GAMMA, DELTA, PHI, INITIAL, APPLY | 待測 / 待測 |
| `FACTOR` | `FACTOR.xml` | GLOBAL_PARAMS, MISSING, MATRIX, METHOD, SELECT, ANALYSIS, PRINT, PLOT, DIAGONAL, FORMAT, CRITERIA, EXTRACTION, ROTATION, SAVE | 文件核對 / 待測 |
| `FIT` | `FIT.xml` | GLOBAL_PARAMS, OBS, DFE, DFH | 待測 / 待測 |
| `GENLIN` | `GENLIN.xml` | GLOBAL_PARAMS, MODEL, CRITERIA, REPEATED, EMMEANS, MISSING, PRINT, SAVE, OUTFILE | 待測 / 待測 |
| `GENLINMIXED` | `GENLINMIXED.xml` | DATA_STRUCTURE, FIELDS, TARGET_OPTIONS, FIXED, RANDOM, BUILD_OPTIONS, EMMEANS, EMMEANS_OPTIONS, OUTFILE, SAVE | 待測 / 待測 |
| `GENLOG` | `GENLOG.xml` | GLOBAL_PARAMS, CSTRUCTURE, GRESID, GLOR, MODEL, CRITERIA, PRINT, PLOT, SAVE, MISSING, DESIGN | 待測 / 待測 |
| `GLM` | `GLM.xml` | GLOBAL_PARAMS, WSFACTOR, MEASURE, WSDESIGN, RANDOM, REGWGT, METHOD, INTERCEPT, MISSING, CRITERIA, PRINT, PLOT, TEST, LMATRIX, CONTRAST, MMATRIX, KMATRIX, POSTHOC, EEMEANS, ROBUST, SAVE, OUTFILE, DESIGN, MBPDESIGN, BPDESIGN, FDESIGN, RANDOM, EMMEANS | 待測 / 待測 |
| `HILOGLINEAR` | `HILOGLINEAR.xml` | GLOBAL_PARAMS, METHOD, MAXORDER, CRITERIA, CWEIGHT, PRINT, PLOT, MISSING, DESIGN | 待測 / 待測 |
| `HOMALS` | `HOMALS.xml` | GLOBAL_PARAMS, ANALYSIS, NOBSERVATIONS, DIMENSION, MAXITER, CONVERGENCE, PRINT, PLOT, SAVE, MATRIX | 待測 / 待測 |
| `KM` | `KM.xml` | GLOBAL_PARAMS, STATUS, STRATA, PLOT, ID, PRINT, PERCENTILES, TEST, COMPARE, TREND, SAVE | 待測 / 待測 |
| `KNN` | `KNN.xml` | GLOBAL_PARAMS, EXCEPT, CASELABELS, FOCALCASES, RESCALE, PARTITION, MODEL, CRITERIA, CROSSVALIDATION, MISSING, VIEWMODEL, PRINT, SAVE, OUTFILE | 待測 / 待測 |
| `KRR` | `KRR.xml` | GLOBAL_PARAMS, CRITERIA, KERNEL, CROSSVALID, PRINT, PLOT, SAVE | 待測 / 待測 |
| `LINEAR` | `LINEAR.xml` | FIELDS, BUILD_OPTIONS, ENSEMBLES, OUTFILE, SAVE | 待測 / 待測 |
| `LINEAR_ELASTIC_NET` | `LINEAR_ELASTIC_NET.xml` | GLOBAL_PARAMS, MODE, RATIO, ALPHA, CRITERIA, PARTITION, PRINT, PLOT, SAVE | 待測 / 待測 |
| `LINEAR_LASSO` | `LINEAR_LASSO.xml` | GLOBAL_PARAMS, MODE, ALPHA, CRITERIA, PARTITION, PRINT, PLOT, SAVE | 待測 / 待測 |
| `LINEAR_RIDGE` | `LINEAR_RIDGE.xml` | GLOBAL_PARAMS, MODE, ALPHA, CRITERIA, PARTITION, PRINT, PLOT, SAVE | 待測 / 待測 |
| `LOGISTIC REGRESSION` | `LOGISTIC REGRESSION.xml` | GLOBAL_PARAMS, CATEGORICAL, CONTRAST, METHOD, SELECT, NOORIGIN, ORIGIN, ID, PRINT, CRITERIA, CLASSPLOT, MISSING, CASEWISE, SAVE, OUTFILE, EXTERNAL | 文件核對 / 待測 |
| `LOGLINEAR` | `LOGLINEAR.xml` | GLOBAL_PARAMS, CWEIGHT, GRESID, CONTRAST, CRITERIA, PRINT, PLOT, MISSING, DESIGN | 待測 / 待測 |
| `MANOVA` | `MANOVA.xml` | GLOBAL_PARAMS, WSFACTORS, WSDESIGN, TRANSFORM, MEASURE, RENAME, ERROR, CONTRAST, PARTITION, METHOD, PRINT, NOPRINT, OMEANS, PMEANS, RESIDUALS, POWER, CINTERVAL, PCOMPS, PLOT, DISCRIM, MISSING, MATRIX, ANALYSIS, DESIGN | 待測 / 待測 |
| `META BINARY` | `META BINARY.xml` | CRITERIA, DATA, ANALYSIS, INFERENCE, CONTRAST, BIAS, TRIMFILL, PRINT, SAVE, OUTFILE, FORESTPLOT, CUMFORESTPLOT, BUBBLEPLOT, FUNNELPLOT, GALBRAITHPLOT, LABBEPLOT | 待測 / 待測 |
| `META CONTINUOUS` | `META CONTINUOUS.xml` | CRITERIA, DATA, ANALYSIS, INFERENCE, CONTRAST, BIAS, TRIMFILL, PRINT, SAVE, OUTFILE, FORESTPLOT, CUMFORESTPLOT, BUBBLEPLOT, FUNNELPLOT, GALBRAITHPLOT | 待測 / 待測 |
| `META ES BINARY` | `META ES BINARY.xml` | CRITERIA, DATA, ANALYSIS, INFERENCE, CONTRAST, BIAS, TRIMFILL, PRINT, SAVE, OUTFILE, FORESTPLOT, CUMFORESTPLOT, BUBBLEPLOT, FUNNELPLOT, GALBRAITHPLOT | 待測 / 待測 |
| `META ES CONTINUOUS` | `META ES CONTINUOUS.xml` | CRITERIA, DATA, ANALYSIS, INFERENCE, CONTRAST, BIAS, TRIMFILL, PRINT, SAVE, OUTFILE, FORESTPLOT, CUMFORESTPLOT, BUBBLEPLOT, FUNNELPLOT, GALBRAITHPLOT | 待測 / 待測 |
| `META REGRESSION` | `META REGRESSION.xml` | GLOBAL_PARAMS, CRITERIA, DATA, INFERENCE, PRINT, SAVE, BUBBLEPLOT | 待測 / 待測 |
| `MIXED` | `MIXED.xml` | GLOBAL_PARAMS, CRITERIA, EMMEANS, FIXED, METHOD, MISSING, PRINT, RANDOM, REGWGT, REPEATED, SAVE, TEST, OUTFILE | 待測 / 待測 |
| `MLP` | `MLP.xml` | GLOBAL_PARAMS, EXCEPT, RESCALE, PARTITION, ARCHITECTURE, CRITERIA, STOPPINGRULES, MISSING, PRINT, PLOT, OUTFILE, SAVE | 待測 / 待測 |
| `MODEL PROGRAM` | `MODEL PROGRAM.xml` | 無宣告 | 待測 / 待測 |
| `MULTIPLE CORRESPONDENCE` | `MULTIPLE CORRESPONDENCE.xml` | VARIABLES, ANALYSIS, DISCRETIZATION, MISSING, SUPPLEMENTARY, CONFIGURATION, DIMENSION, NORMALIZATION, MAXITER, CRITITER, PRINT, PLOT, SAVE, OUTFILE | 待測 / 待測 |
| `MULTIPLE IMPUTATION` | `MULTIPLE IMPUTATION.xml` | IMPUTE, CONSTRAINTS, MISSINGSUMMARIES, IMPUTATIONSUMMARIES, ANALYSISWEIGHT, OUTFILE | 文件核對 / 待測 |
| `MVA` | `MVA.xml` | GLOBAL_PARAMS, CATEGORICAL, MAXCAT, ID, NOUNIVARIATE, TTEST, CROSSTAB, MISMATCH, DPATTERN, MPATTERN, TPATTERN, LISTWISE, PAIRWISE, EM, REGRESSION | 待測 / 待測 |
| `NAIVEBAYES` | `NAIVEBAYES.xml` | GLOBAL_PARAMS, EXCEPT, FORCE, TRAININGSAMPLE, SUBSET, CRITERIA, MISSING, PRINT, SAVE, OUTFILE | 待測 / 待測 |
| `NLR` | `NLR.xml` | FILE, OUTFILE, PRED, SAVE, CRITERIA | 待測 / 待測 |
| `NOMREG` | `NOMREG.xml` | GLOBAL_PARAMS, CRITERIA, FULLFACTORIAL, INTERCEPT, MISSING, MODEL, STEPWISE, OUTFILE, PRINT, SAVE, SCALE, SUBPOP, TEST | 待測 / 待測 |
| `OVERALS` | `OVERALS.xml` | GLOBAL_PARAMS, VARIABLES, ANALYSIS, SETS, NOBSERVATIONS, DIMENSION, INITIAL, MAXITER, CONVERGENCE, PRINT, PLOT, SAVE, MATRIX | 待測 / 待測 |
| `PACF` | `PACF.xml` | GLOBAL_PARAMS, DIFF, SDIFF, PERIOD, NOLOG, LN, SEASONAL, MXAUTO, APPLY | 待測 / 待測 |
| `PLS` | `PLS.xml` | GLOBAL_PARAMS, ID, MODEL, OUTDATASET, CRITERIA | 待測 / 待測 |
| `PLUM` | `PLUM.xml` | GLOBAL_PARAMS, CRITERIA, LINK, LOCATION, MISSING, PRINT, SAVE, SCALE, TEST | 待測 / 待測 |
| `POWER MEANS INDEPENDENT` | `POWER MEANS INDEPENDENT.xml` | PARAMETERS, PRECISION, PLOT | 待測 / 待測 |
| `POWER MEANS ONESAMPLE` | `POWER MEANS ONESAMPLE.xml` | PARAMETERS, PRECISION, PLOT | 待測 / 待測 |
| `POWER MEANS RELATED` | `POWER MEANS RELATED.xml` | PARAMETERS, PRECISION, PLOT | 待測 / 待測 |
| `POWER ONEWAY ANOVA` | `POWER ONEWAY ANOVA.xml` | PARAMETERS, CONTRAST, PLOT | 待測 / 待測 |
| `POWER PARTIALCORR` | `POWER PARTIALCORR.xml` | PARAMETERS, PRECISION, PLOT | 待測 / 待測 |
| `POWER PEARSON ONESAMPLE` | `POWER PEARSON ONESAMPLE.xml` | PARAMETERS, PRECISION, PLOT | 待測 / 待測 |
| `POWER PROPORTIONS INDEPENDENT` | `POWER PROPORTIONS INDEPENDENT.xml` | PARAMETERS, PRECISION, PLOT | 待測 / 待測 |
| `POWER PROPORTIONS ONESAMPLE` | `POWER PROPORTIONS ONESAMPLE.xml` | PARAMETERS, PRECISION, PLOT | 待測 / 待測 |
| `POWER PROPORTIONS RELATED` | `POWER PROPORTIONS RELATED.xml` | PARAMETERS, PRECISION, PLOT | 待測 / 待測 |
| `POWER SPEARMAN ONESAMPLE` | `POWER SPEARMAN ONESAMPLE.xml` | PARAMETERS, PRECISION, PLOT | 待測 / 待測 |
| `POWER UNIVARIATE LINEAR` | `POWER UNIVARIATE LINEAR.xml` | PARAMETERS, PLOT | 待測 / 待測 |
| `PREDICT` | `PREDICT.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `PREFSCAL` | `PREFSCAL.xml` | GLOBAL_PARAMS, INPUT, PROXIMITIES, WEIGHTS, INITIAL, CONDITION, TRANSFORMATION, MODEL, RESTRICTIONS, PENALTY, CRITERIA, PRINT, PLOT, OPTIONS, OUTFILE | 待測 / 待測 |
| `PRINCALS` | `PRINCALS.xml` | GLOBAL_PARAMS, ANALYSIS, NOBSERVATIONS, DIMENSION, MAXITER, CONVERGENCE, PRINT, PLOT, SAVE, MATRIX | 待測 / 待測 |
| `PROBIT` | `PROBIT.xml` | GLOBAL_PARAMS, MODEL, LOG, CRITERIA, NATRES, PRINT, MISSING | 待測 / 待測 |
| `PROXIMITIES` | `PROXIMITIES.xml` | VIEW, STANDARDIZE, MEASURE, PRINT, ID, MISSING, MATRIX | 待測 / 待測 |
| `PROXIMITY MAPPING` | `PROXIMITY MAPPING.xml` | SOURCEID, DATA, WEIGHTS, OBJECTID, INITIAL, CONDITION, TRANSFORMATIONS, MODEL, FIXED, ATTRIBUTES, PROPERTIES, CRITERIA, PRINT, PLOT, SAVE | 待測 / 待測 |
| `PROXSCAL` | `PROXSCAL.xml` | TABLE, SHAPE, INITIAL, WEIGHTS, CONDITION, TRANSFORMATION, PROXIMITIES, MODEL, RESTRICTIONS, ACCELERATION, CRITERIA, PRINT, PLOT, OUTFILE, MATRIX | 待測 / 待測 |
| `QUANTILE REGRESSION` | `QUANTILE REGRESSION.xml` | GLOBAL_PARAMS, CRITERIA, MISSING, MODEL, SAVE, PREDICT_EFFECTS, PREDICTION_TABLES, PREDICTION_LINES, PRINT, PLOT, OUTFILE, EXTERNAL | 待測 / 待測 |
| `QUICK CLUSTER` | `QUICK CLUSTER.xml` | GLOBAL_PARAMS, MISSING, FILE, INITIAL, CRITERIA, METHOD, PRINT, OUTFILE, SAVE | 文件核對 / 待測 |
| `RBF` | `RBF.xml` | GLOBAL_PARAMS, EXCEPT, RESCALE, PARTITION, ARCHITECTURE, CRITERIA, MISSING, PRINT, PLOT, SAVE, OUTFILE | 待測 / 待測 |
| `REGRESSION` | `REGRESSION.xml` | GLOBAL_PARAMS, MATRIX, VARIABLES, DESCRIPTIVES, SELECT, MISSING, REGWGT, STATISTICS, CRITERIA, NOORIGIN, ORIGIN, DEPENDENT, METHOD, RESIDUALS, CASEWISE, SCATTERPLOT, PARTIALPLOT, OUTFILE, SAVE, TEMPLATE | 文件核對 / 待測 |
| `RESPONSE RATE` | `RESPONSE RATE.xml` | VARIABLES, MINRATE, MAXCOUNT | 待測 / 待測 |
| `ROC ANALYSIS` | `ROC ANALYSIS.xml` | GLOBAL_PARAMS, MISSING, CRITERIA, DESIGN, PLOT, PRINT | 待測 / 待測 |
| `ROC` | `ROC.xml` | GLOBAL_PARAMS, MISSING, CRITERIA, PLOT, PRINT | 待測 / 待測 |
| `SEASON` | `SEASON.xml` | GLOBAL_PARAMS, MODEL, MA, PERIOD, APPLY | 待測 / 待測 |
| `SELECTPRED` | `SELECTPRED.xml` | GLOBAL_PARAMS, EXCEPT, SCREENING, CRITERIA, MISSING, PRINT, PLOT | 待測 / 待測 |
| `SIMPLAN CREATE` | `SIMPLAN CREATE.xml` | GLOBAL_PARAMS, MODEL, TARGETOPTS, SIMINPUT, FIXEDINPUT, CORRELATIONS, CONTINGENCY, AUTOFIT, STOPCRITERIA, MISSING, VALUELABELS, PLAN | 待測 / 待測 |
| `SIMPLAN VIEW` | `SIMPLAN VIEW.xml` | PLAN | 待測 / 待測 |
| `SIMRUN` | `SIMRUN.xml` | PLAN, CRITERIA, DISTRIBUTION, SCATTERPLOT, BOXPLOT, TORNADO, PRINT, OPTIONS, OUTFILE | 待測 / 待測 |
| `SPATIAL ASSOCIATION RULES` | `SPATIAL ASSOCIATION RULES.xml` | MAPSPEC, AUTOBINNING, AGGREGATION, DATASET, RULEGENERATION, MODELTABLES, MAPOUTPUT, WORDCLOUD, RULESTABLE, SAVE | 待測 / 待測 |
| `SPATIAL TEMPORAL PREDICTION` | `SPATIAL TEMPORAL PREDICTION.xml` | MAPSPEC, AGGREGATION, DATASET, TIMEFIELDS, MODELBUILDING, MODELTABLES, MAPOUTPUT, SAVE | 待測 / 待測 |
| `SPECTRA` | `SPECTRA.xml` | GLOBAL_PARAMS, CENTER, CROSS, WINDOW, PLOT, SAVE, APPLY | 待測 / 待測 |
| `SURVIVAL` | `SURVIVAL.xml` | GLOBAL_PARAMS, INTERVAL, STATUS, PLOTS, PRINT, COMPARE, CALCULATE, MISSING, WRITE | 待測 / 待測 |
| `SURVREG AFT` | `SURVREG AFT.xml` | GLOBAL_PARAMS, CRITERIA, MODEL, STATUS, ESTIMATION, PRINT, RESIDUALPLOT, FUNCTIONPLOT, PREDICT, OUTFILE | 待測 / 待測 |
| `SURVREG RECURRENT` | `SURVREG RECURRENT.xml` | GLOBAL_PARAMS, CRITERIA, MODEL, STATUS, ESTIMATION, PRINT, FUNCTIONPLOT, PREDICT, OUTFILE | 待測 / 待測 |
| `TCM ANALYSIS` | `TCM ANALYSIS.xml` | MODELSYSTEM, EXPRESSIONS, SCENARIOPERIOD, SCENARIO, SCENARIOGROUP, TARGETLIST, OPTIONS | 待測 / 待測 |
| `TCM APPLY` | `TCM APPLY.xml` | MODELSYSTEM, OPTIONS, TARGETFILTER, SERIESFILTER, FILTEREDOUTPUT, SYSTEMOUTPUT, SAVE, OUTFILE, PASSPROTECT | 待測 / 待測 |
| `TCM MODEL` | `TCM MODEL.xml` | DATASETTINGS, DATAFILTER, BUILDOPTIONS, TARGETFILTER, SERIESFILTER, FILTEREDOUTPUT, SYSTEMOUTPUT, SAVE, OUTFILE, PASSPROTECT, FIELDSGROUP, FIELDS | 待測 / 待測 |
| `TREE` | `TREE.xml` | GLOBAL_PARAMS, TREE, DEPCATEGORIES, PRINT, GAIN, PLOT, RULES, SAVE, METHOD, GROWTHLIMIT, VALIDATION, CHAID, CRT, QUEST, COSTS, PRIORS, SCORES, PROFITS, INFLUENCE, OUTFILE, MISSING, TARGETRESPONSE | 待測 / 待測 |
| `TSAPPLY` | `TSAPPLY.xml` | MODELSUMMARY, MODELSTATISTICS, MODELDETAILS, SERIESPLOT, OUTPUTFILTER, SAVE, AUXILIARY, MISSING, MODEL | 待測 / 待測 |
| `TSMODEL` | `TSMODEL.xml` | MODELSUMMARY, MODELSTATISTICS, MODELDETAILS, SERIESPLOT, OUTPUTFILTER, SAVE, AUXILIARY, MISSING, MODEL, EXPERTMODELER, EXSMOOTH, ARIMA, TRANSFERFUNCTION, AUTOOUTLIER, OUTLIER | 待測 / 待測 |
| `TWOSTEP CLUSTER` | `TWOSTEP CLUSTER.xml` | CATEGORICAL, CONTINUOUS, CRITERIA, DISTANCE, HANDLENOISE, INFILE, MEMALLOCATE, MISSING, NOSTANDARDIZE, NUMCLUSTERS, OUTFILE, PRINT, SAVE, VIEWMODEL | 待測 / 待測 |
| `UNIANOVA` | `UNIANOVA.xml` | GLOBAL_PARAMS, RANDOM, REGWGT, METHOD, INTERCEPT, MISSING, CRITERIA, PRINT, PLOT, TEST, LMATRIX, KMATRIX, CONTRAST, POSTHOC, EMMEANS, ROBUST, SAVE, OUTFILE, DESIGN, MBPDESIGN, BPDESIGN, FDESIGN | 文件核對 / 待測 |
| `VARCOMP` | `VARCOMP.xml` | GLOBAL_PARAMS, RANDOM, METHOD, INTERCEPT, MISSING, REGWGT, CRITERIA, PRINT, OUTFILE, DESIGN | 待測 / 待測 |
| `WLS` | `WLS.xml` | GLOBAL_PARAMS, SOURCE, DELTA, WEIGHT, CONSTANT, NOCONSTANT, PRINT, SAVE, APPLY, POWER | 待測 / 待測 |

### output（49）

| 命令 | 本機 XML | 參數群（Subcommand） | 文件狀態 / 結果驗證 |
|---|---|---|---|
| `BEGIN GPL` | `BEGIN GPL.xml` | 無宣告 | 待測 / 待測 |
| `BEGIN GRAPHSRV` | `BEGIN GRAPHSRV.xml` | 無宣告 | 待測 / 待測 |
| `BEGIN STATJSON` | `BEGIN STATJSON.xml` | 無宣告 | 待測 / 待測 |
| `CASEPLOT` | `CASEPLOT.xml` | GLOBAL_PARAMS, DIFF, SDIFF, PERIOD, NOLOG, LN, ID, MARK, SPLIT, APPLY, FORMAT | 待測 / 待測 |
| `CTABLES` | `CTABLES.xml` | FORMAT, VLABELS, MRSETS, SMISSING, PCOMPUTE, PPROPERTIES, TABLE, SLABELS, CLABELS, CATEGORIES, TITLES, SIGTEST, COMPARETEST, HIDESMALLCOUNTS, CRITERIA, WEIGHT | 待測 / 待測 |
| `DISPLAY` | `DISPLAY.xml` | GLOBAL_PARAMS, VARIABLES | 待測 / 待測 |
| `DMTABLES` | `DMTABLES.xml` | FORMAT, VLABELS, MRSETS, SMISSING, PCOMPUTE, PPROPERTIES, TABLE, SLABELS, CLABELS, CATEGORIES, TITLES, SIGTEST, COMPARETEST | 待測 / 待測 |
| `ECHO` | `ECHO.xml` | 無宣告 | 待測 / 待測 |
| `GGRAPH` | `GGRAPH.xml` | GRAPHDATASET, GRAPHSPEC, FITLINE, STYLE, COLORCYCLE, FRAME, GRIDLINES | 待測 / 待測 |
| `GRAPH` | `GRAPH.xml` | TITLE, SUBTITLE, FOOTNOTE, BAR, LINE, PIE, PARETO, HILO, HISTOGRAM, SCATTERPLOT, ERRORBAR, PANEL, INTERVAL, TEMPLATE, MISSING | 待測 / 待測 |
| `IGRAPH` | `IGRAPH.xml` | Y, X1, X2, YLENGTH, X1LENGTH, CATORDER, COLOR, REFLINE, STYLE, NORMALIZE, SIZE, CLUSTER, SUMMARYVAR, PANEL, POINTLABEL, CASELABEL, COORDINATE, EFFECT, TITLE, SUBTITLE, CAPTION, VIEWNAME, CHARTLOOK, SCATTER, BAR, PIE, BOX, LINE, AREA, ERRORBAR, HISTOGRAM, FITLINE, SPIKE, FORMAT, STACK | 待測 / 待測 |
| `LIST` | `LIST.xml` | GLOBAL_PARAMS, VARIABLES, FORMAT, CASES | 待測 / 待測 |
| `OLAP CUBES` | `OLAP CUBES.xml` | GLOBAL_PARAMS, CELLS, CREATE, TITLE, HIDESMALLCOUNTS | 待測 / 待測 |
| `OMS` | `OMS.xml` | SELECT, IF, EXCEPTIF, DESTINATION, COLUMNS, TAG, NOWARN | 文件核對 / 待測 |
| `OMSEND` | `OMSEND.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `OMSINFO` | `OMSINFO.xml` | 無宣告 | 待測 / 待測 |
| `OMSLOG` | `OMSLOG.xml` | GLOBAL_PARAMS, APPEND, FORMAT | 待測 / 待測 |
| `OUTPUT ACTIVATE` | `OUTPUT ACTIVATE.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `OUTPUT CLOSE` | `OUTPUT CLOSE.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `OUTPUT CREATE` | `OUTPUT CREATE.xml` | SPEC | 待測 / 待測 |
| `OUTPUT DISPLAY` | `OUTPUT DISPLAY.xml` | 無宣告 | 待測 / 待測 |
| `OUTPUT EXPORT` | `OUTPUT EXPORT.xml` | GLOBAL_PARAMS, CONTENTS, DOC, HTML, PDF, PPT, TEXT, XLS, XLSX, XLSM, BMP, EMF, EPS, JPG, PNG, SVG, TIF | 文件核對 / 待測 |
| `OUTPUT MODIFY` | `OUTPUT MODIFY.xml` | GLOBAL_PARAMS, SELECT, IF, DELETEOBJECT, INDEXING, OBJECTPROPERTIES, TABLE, TABLECELLS, GRAPHS, TEXTS, REPORT | 待測 / 待測 |
| `OUTPUT NAME` | `OUTPUT NAME.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `OUTPUT NEW` | `OUTPUT NEW.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `OUTPUT OPEN` | `OUTPUT OPEN.xml` | GLOBAL_PARAMS, LOCK | 待測 / 待測 |
| `OUTPUT SAVE` | `OUTPUT SAVE.xml` | GLOBAL_PARAMS, PASSPROTECT | 待測 / 待測 |
| `PLANCARDS` | `PLANCARDS.xml` | FACTORS, FORMAT, TITLE, FOOTER, OUTFILE | 待測 / 待測 |
| `PPLOT` | `PPLOT.xml` | GLOBAL_PARAMS, VARIABLES, DISTRIBUTION, FRACTION, TIES, NOSTANDARDIZE, STANDARDIZE, TYPE, PLOT, DIFF, SDIFF, PERIOD, NOLOG, LN, APPLY, TEMPLATE | 待測 / 待測 |
| `PRINT EJECT` | `PRINT EJECT.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `PRINT FORMATS` | `PRINT FORMATS.xml` | 無宣告 | 待測 / 待測 |
| `PRINT SPACE` | `PRINT SPACE.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `PRINT` | `PRINT.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `PROCEDURE OUTPUT` | `PROCEDURE OUTPUT.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `RELATIONSHIP MAP` | `RELATIONSHIP MAP.xml` | GLOBAL_PARAMS, MISSING, OPTIONS | 待測 / 待測 |
| `REPORT` | `REPORT.xml` | FORMAT, OUTFILE, STRING, VARIABLES, MISSING, TITLE, FOOTNOTE, BREAK, SUMMARY | 待測 / 待測 |
| `SPATIAL MAPSPEC` | `SPATIAL MAPSPEC.xml` | MAPPROJECTION, MAP, DATA, SPECFILE | 待測 / 待測 |
| `SPCHART` | `SPCHART.xml` | TEMPLATE, TITLE, SUBTITLE, FOOTNOTE, XR, XS, IR, I, NP, P, C, U, CPCHART, STATISTICS, RULES, ID, CAPSIGMA, SPAN, CONFORM, NONCONFORM, SIGMAS, MINSAMPLE, LSL, USL, TARGET, MISSING, NORMAL, REFERENCE | 待測 / 待測 |
| `SUBTITLE` | `SUBTITLE.xml` | 無宣告 | 待測 / 待測 |
| `TABLES` | `TABLES.xml` | AUTOLABEL , FORMAT, TITLE, CAPTION, OBSERVATION, MDGROUP, PTOTAL, FTOTAL, MISSING, BASE, GBASE, TABLE, STATISTICS , SORT, CORNER | 待測 / 待測 |
| `TDISPLAY` | `TDISPLAY.xml` | GLOBAL_PARAMS, TYPE | 待測 / 待測 |
| `TITLE` | `TITLE.xml` | 無宣告 | 待測 / 待測 |
| `TSHOW` | `TSHOW.xml` | 無宣告 | 待測 / 待測 |
| `TSPLOT` | `TSPLOT.xml` | GLOBAL_PARAMS, DIFF, SDIFF, PERIOD, NOLOG, LN, ID, MARK, SPLIT, APPLY, FORMAT | 待測 / 待測 |
| `VGRAPH` | `VGRAPH.xml` | GRAPHDATASET, GRAPHSPEC | 待測 / 待測 |
| `WORKBOOK EXPORT` | `WORKBOOK EXPORT.xml` | GLOBAL_PARAMS, CONTENTS, DOC, HTML, PDF, PPT, TEXT, XLS, XLSX, XLSM, BMP, EMF, EPS, JPG, PNG, TIF | 待測 / 待測 |
| `WORKBOOK MODIFY` | `WORKBOOK MODIFY.xml` | GLOBAL_PARAMS, SELECT, IF, DELETEOBJECT, INDEXING, OBJECTPROPERTIES, TABLE, TABLECELLS, GRAPHS, TEXTS, REPORT | 待測 / 待測 |
| `WORKBOOK SAVE` | `WORKBOOK SAVE.xml` | GLOBAL_PARAMS, PASSPROTECT | 待測 / 待測 |
| `XGRAPH` | `XGRAPH.xml` | GLOBAL_PARAMS, BIN, DISPLAY, DISTRIBUTION, COORDINATE, ERRORBAR, MISSING, PANEL, TEMPLATE, TITLES | 待測 / 待測 |

### data（107）

| 命令 | 本機 XML | 參數群（Subcommand） | 文件狀態 / 結果驗證 |
|---|---|---|---|
| `ADD DOCUMENT` | `ADD DOCUMENT.xml` | 無宣告 | 待測 / 待測 |
| `ADD FILES` | `ADD FILES.xml` | GLOBAL_PARAMS, RENAME, IN, FILE, BY, MAP, KEEP, DROP, FIRST, LAST | 待測 / 待測 |
| `ADD VALUE LABELS` | `ADD VALUE LABELS.xml` | 無宣告 | 待測 / 待測 |
| `ADP` | `ADP.xml` | FIELDS, PREPDATETIME, SCREENING, ADJUSTLEVEL, OUTLIERHANDLING, REPLACEMISSING, REORDERNOMINAL, RESCALE, TRANSFORM, CRITERIA, OUTFILE | 待測 / 待測 |
| `AGGREGATE` | `AGGREGATE.xml` | GLOBAL_PARAMS, SPEC_PARAMS, OUTFILE, MISSING, DOCUMENT, PRESORTED, BREAK | 待測 / 待測 |
| `ALTER TYPE` | `ALTER TYPE.xml` | GLOBAL_PARAMS, PRINT | 待測 / 待測 |
| `APPLY DICTIONARY` | `APPLY DICTIONARY.xml` | GLOBAL_PARAMS, FROM, SOURCE VARIABLES, TARGET VARIABLES, NEWVARS, FILEINFO, VARINFO | 待測 / 待測 |
| `AUTORECODE` | `AUTORECODE.xml` | GLOBAL_PARAMS, INTO, BLANK, GROUP, APPLY, SAVE, DESCENDING, PRINT | 待測 / 待測 |
| `BEGIN DATA` | `BEGIN DATA.xml` | 無宣告 | 待測 / 待測 |
| `BLDATMAN` | `BLDATMAN.xml` | GLOBAL_PARAMS, CRITERIA, PRINT, PLOT | 待測 / 待測 |
| `CACHE` | `CACHE.xml` | 無宣告 | 待測 / 待測 |
| `CASESTOVARS` | `CASESTOVARS.xml` | ID, FIXED, AUTOFIX, VIND, COUNT, RENAME, SEPARATOR, INDEX, GROUPBY, DROP | 待測 / 待測 |
| `CLEAR TRANSFORMATIONS` | `CLEAR TRANSFORMATIONS.xml` | 無宣告 | 待測 / 待測 |
| `COMPARE DATASETS` | `COMPARE DATASETS.xml` | COMPDATASET, VARIABLES , CASEID, SAVE, OUTPUT | 待測 / 待測 |
| `COMPUTE` | `COMPUTE.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `COUNT` | `COUNT.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `CREATE` | `CREATE.xml` | GLOBAL_PARAMS, SPEC_PARAMS | 待測 / 待測 |
| `CSPLAN ANALYSIS` | `CSPLAN ANALYSIS.xml` | PLAN, PLANVARS, SRSESTIMATOR, PRINT, DESIGN, ESTIMATOR, POPSIZE, INCLPROB | 待測 / 待測 |
| `CSPLAN SAMPLE` | `CSPLAN SAMPLE.xml` | PLAN, PLANVARS, PRINT, DESIGN, METHOD, MOS, SIZE, RATE, STAGEVARS, (空) | 待測 / 待測 |
| `CSPLAN VIEW` | `CSPLAN VIEW.xml` | PLAN, PRINT | 待測 / 待測 |
| `CSSELECT` | `CSSELECT.xml` | PLAN, CRITERIA, CLASSMISSING, DATA, SAMPLEFILE, JOINTPROB, SELECTRULE, PRINT | 待測 / 待測 |
| `DATA LIST` | `DATA LIST.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `DATAFILE ATTRIBUTE` | `DATAFILE ATTRIBUTE.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `DATASET ACTIVATE` | `DATASET ACTIVATE.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `DATASET CLOSE` | `DATASET CLOSE.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `DATASET COPY` | `DATASET COPY.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `DATASET DECLARE` | `DATASET DECLARE.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `DATASET DISPLAY` | `DATASET DISPLAY.xml` | 無宣告 | 待測 / 待測 |
| `DATASET NAME` | `DATASET NAME.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `DATE` | `DATE.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `DELETE VARIABLES` | `DELETE VARIABLES.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `DOCUMENT` | `DOCUMENT.xml` | 無宣告 | 待測 / 待測 |
| `DROP DOCUMENTS` | `DROP DOCUMENTS.xml` | 無宣告 | 待測 / 待測 |
| `EXPORT` | `EXPORT.xml` | GLOBAL_PARAMS, TYPE, UNSELECTED, KEEP, DROP, RENAME, MAP, DIGITS | 待測 / 待測 |
| `FILE HANDLE` | `FILE HANDLE.xml` | NAME, MODE, RECFORM, LRECL, ENCODING | 待測 / 待測 |
| `FILE LABEL` | `FILE LABEL.xml` | 無宣告 | 待測 / 待測 |
| `FILE TYPE` | `FILE TYPE.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `FILTER` | `FILTER.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `FLIP` | `FLIP.xml` | GLOBAL_PARAMS, NEWNAMES | 待測 / 待測 |
| `FORMATS` | `FORMATS.xml` | 無宣告 | 待測 / 待測 |
| `GET CAPTURE` | `GET CAPTURE.xml` | GLOBAL_PARAMS, CONNECT, PASSWORD, SERVER, DATABASE, SQL, UNENCRYPTED, LOGIN | 待測 / 待測 |
| `GET DATA` | `GET DATA.xml` | TYPE, FILE, CONNECT, UNENCRYPTED, ENCRYPTED, SQL, ASSUMEDSTRWIDTH, SHEET, CELLRANGE, READNAMES, ARRANGEMENT, FIRSTCASE, DELCASE, FIXCASE, IMPORTCASE, DELIMITERS, QUALIFIER, VARIABLES, ENCODING, LEADINGSPACES, MULTIPLESPACES, HIDDEN, TRAILINGSPACES, DATATYPEMIN, MAP | 待測 / 待測 |
| `GET SAS` | `GET SAS.xml` | (空), FORMATS, ENCODING | 待測 / 待測 |
| `GET STATA` | `GET STATA.xml` | (空), ENCODING | 待測 / 待測 |
| `GET TRANSLATE` | `GET TRANSLATE.xml` | GLOBAL_PARAMS, TYPE, FIELDNAMES, RANGE, KEEP, DROP, MAP | 待測 / 待測 |
| `GET` | `GET.xml` | GLOBAL_PARAMS, KEEP, DROP, RENAME, MAP | 待測 / 待測 |
| `GETCOGNOS` | `GETCOGNOS.xml` | MODE, CONNECTION, Location, IMPORT, FILTER, PARAMETERS | 待測 / 待測 |
| `GETTM1` | `GETTM1.xml` | CONNECTION, VIEW, RENAME | 待測 / 待測 |
| `IF` | `IF.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `IMPORT` | `IMPORT.xml` | GLOBAL_PARAMS, TYPE, KEEP, DROP, RENAME, MAP | 待測 / 待測 |
| `INPUT PROGRAM` | `INPUT PROGRAM.xml` | 無宣告 | 待測 / 待測 |
| `KEYED DATA LIST` | `KEYED DATA LIST.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `LEAVE` | `LEAVE.xml` | 無宣告 | 待測 / 待測 |
| `MATCH FILES` | `MATCH FILES.xml` | GLOBAL_PARAMS, TABLE, RENAME, IN, FILE, BY, MAP, KEEP, DROP, FIRST, LAST | 待測 / 待測 |
| `MATRIX DATA` | `MATRIX DATA.xml` | GLOBAL_PARAMS, FILE, FORMAT, SPLIT, FACTORS, CELLS, N, CONTENTS | 待測 / 待測 |
| `MCONVERT` | `MCONVERT.xml` | MATRIX, REPLACE, APPEND | 待測 / 待測 |
| `MISSING VALUES` | `MISSING VALUES.xml` | GLOBAL_PARAMS, SPEC_PARAMS | 待測 / 待測 |
| `MRSETS` | `MRSETS.xml` | MDGROUP, MCGROUP, DELETE, DISPLAY | 待測 / 待測 |
| `N OF CASES` | `N OF CASES.xml` | 無宣告 | 待測 / 待測 |
| `NEW FILE` | `NEW FILE.xml` | 無宣告 | 待測 / 待測 |
| `NUMERIC` | `NUMERIC.xml` | 無宣告 | 待測 / 待測 |
| `OPTIMAL BINNING` | `OPTIMAL BINNING.xml` | VARIABLES, CRITERIA, MISSING, OUTFILE, PRINT | 待測 / 待測 |
| `ORTHOPLAN` | `ORTHOPLAN.xml` | FACTORS, REPLACE, OUTFILE, MINIMUM, HOLDOUT, MIXHOLD | 待測 / 待測 |
| `POINT` | `POINT.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `RANK` | `RANK.xml` | GLOBAL_PARAMS, TIES, FRACTION, PRINT, MISSING, RANK, NTILES, NORMAL, PERCENT, RFRACTION, PROPORTION, N, SAVAGE | 待測 / 待測 |
| `RECODE` | `RECODE.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `RECORD TYPE` | `RECORD TYPE.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `RENAME VARIABLES` | `RENAME VARIABLES.xml` | 無宣告 | 待測 / 待測 |
| `REPEATING DATA` | `REPEATING DATA.xml` | GLOBAL_PARAMS, ENCODING, STARTS, OCCURS, LENGTH, CONTINUED, ID, TABLE, NOTABLE, DATA | 待測 / 待測 |
| `REREAD` | `REREAD.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `RMV` | `RMV.xml` | GLOBAL_PARAMS, SPEC_PARAMS | 待測 / 待測 |
| `SAMPLE` | `SAMPLE.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `SAVE CODEPAGE` | `SAVE CODEPAGE.xml` | OUTFILE, UNSELECTED, KEEP, DROP, PASSPROTECT, ENCODING | 待測 / 待測 |
| `SAVE DATA COLLECTION` | `SAVE DATA COLLECTION.xml` | OUTFILE, METADATA, UNSELECTED, KEEP, DROP, MAP | 待測 / 待測 |
| `SAVE TRANSLATE` | `SAVE TRANSLATE.xml` | OUTFILE, CONNECT, ENCRYPTED, UNENCRYPTED, TYPE, VERSION, ENCODING, FIELDNAMES, CELLS, TEXTOPTIONS, EDITION, PLATFORM, VALFILE, TABLE, SQL, APPEND, REPLACE, RENAME, KEEP, DROP, UNSELECTED, MISSING, COMPRESSED, UNCOMPRESSED, MAP, BULKLOADING, ODBCOPTIONS, EXCELOPTIONS | 待測 / 待測 |
| `SAVE` | `SAVE.xml` | GLOBAL_PARAMS, VERSION, UNSELECTED, KEEP, DROP, RENAME, MAP, COMPRESSED, UNCOMPRESSED, ZCOMPRESSED, NAMES, PERMISSIONS, PASSPROTECT | 待測 / 待測 |
| `SAVETM1` | `SAVETM1.xml` | CONNECTION, CUBE, MAPPINGS | 待測 / 待測 |
| `SELECT IF` | `SELECT IF.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `SHIFT VALUES` | `SHIFT VALUES.xml` | GLOBAL_PARAMS, VARIABLE | 待測 / 待測 |
| `SORT CASES` | `SORT CASES.xml` | GLOBAL_PARAMS, OUTFILE, PASSPROTECT | 待測 / 待測 |
| `SORT VARIABLES` | `SORT VARIABLES.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `SPLIT FILE` | `SPLIT FILE.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `STAR JOIN` | `STAR JOIN.xml` | SELECT, FROM, JOIN, OUTFILE, PASSPROTECT | 待測 / 待測 |
| `STRING` | `STRING.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `SYSFILE INFO` | `SYSFILE INFO.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `TEMPORARY` | `TEMPORARY.xml` | 無宣告 | 待測 / 待測 |
| `TMS BEGIN` | `TMS BEGIN.xml` | DESTINATION | 待測 / 待測 |
| `TMS END` | `TMS END.xml` | PRINT | 待測 / 待測 |
| `TMS IMPORT` | `TMS IMPORT.xml` | INFILE, SAVE, OUTFILE | 待測 / 待測 |
| `TMS MERGE` | `TMS MERGE.xml` | DESTINATION, TRANSFORMATIONS, MODEL, PRINT | 待測 / 待測 |
| `UPDATE` | `UPDATE.xml` | GLOBAL_PARAMS, RENAME, IN, FILE, BY, MAP, KEEP, DROP | 待測 / 待測 |
| `USE` | `USE.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `VALIDATEDATA` | `VALIDATEDATA.xml` | GLOBAL_PARAMS, VARCHECKS, IDCHECKS, CASECHECKS, RULESUMMARIES, CASEREPORT, SAVE | 待測 / 待測 |
| `VALUE LABELS` | `VALUE LABELS.xml` | 無宣告 | 待測 / 待測 |
| `VARIABLE ALIGNMENT` | `VARIABLE ALIGNMENT.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `VARIABLE ATTRIBUTE` | `VARIABLE ATTRIBUTE.xml` | GLOBAL_PARAMS, VARIABLES | 待測 / 待測 |
| `VARIABLE LABELS` | `VARIABLE LABELS.xml` | 無宣告 | 待測 / 待測 |
| `VARIABLE LEVEL` | `VARIABLE LEVEL.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `VARIABLE ROLE` | `VARIABLE ROLE.xml` | INPUT, TARGET, BOTH, NONE, PARTITION, SPLIT | 待測 / 待測 |
| `VARIABLE WIDTH` | `VARIABLE WIDTH.xml` | 無宣告 | 待測 / 待測 |
| `VARSTOCASES` | `VARSTOCASES.xml` | MAKE, INDEX, ID, NULL, COUNT, KEEP, DROP | 待測 / 待測 |
| `VECTOR` | `VECTOR.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `VERIFY` | `VERIFY.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `WEIGHT` | `WEIGHT.xml` | GLOBAL_PARAMS | 文件核對 / 待測 |
| `WRITE FORMATS` | `WRITE FORMATS.xml` | 無宣告 | 待測 / 待測 |
| `WRITE` | `WRITE.xml` | GLOBAL_PARAMS, 1, 2 | 待測 / 待測 |
| `XSAVE` | `XSAVE.xml` | GLOBAL_PARAMS, KEEP, DROP, RENAME, MAP, COMPRESSED, UNCOMPRESSED, ZCOMPRESSED, PERMISSIONS | 待測 / 待測 |

### system（50）

| 命令 | 本機 XML | 參數群（Subcommand） | 文件狀態 / 結果驗證 |
|---|---|---|---|
| `BEGIN EXPR` | `BEGIN EXPR.xml` | OUTFILE | 待測 / 待測 |
| `BEGIN PROGRAM` | `BEGIN PROGRAM.xml` | 無宣告 | 待測 / 待測 |
| `BREAK` | `BREAK.xml` | 無宣告 | 待測 / 待測 |
| `CD` | `CD.xml` | 無宣告 | 待測 / 待測 |
| `CLEAR TIME PROGRAM` | `CLEAR TIME PROGRAM.xml` | 無宣告 | 待測 / 待測 |
| `COMMENT` | `COMMENT.xml` | 無宣告 | 待測 / 待測 |
| `DEFINE` | `DEFINE.xml` | 無宣告 | 待測 / 待測 |
| `DERIVATIVES` | `DERIVATIVES.xml` | 無宣告 | 待測 / 待測 |
| `DO IF` | `DO IF.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `DO REPEAT` | `DO REPEAT.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `ELSE IF` | `ELSE IF.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `ELSE` | `ELSE.xml` | 無宣告 | 待測 / 待測 |
| `END CASE` | `END CASE.xml` | 無宣告 | 待測 / 待測 |
| `END EXPR` | `END EXPR.xml` | 無宣告 | 待測 / 待測 |
| `END FILE TYPE` | `END FILE TYPE.xml` | 無宣告 | 待測 / 待測 |
| `END FILE` | `END FILE.xml` | 無宣告 | 待測 / 待測 |
| `END IF` | `END IF.xml` | 無宣告 | 待測 / 待測 |
| `END INPUT PROGRAM` | `END INPUT PROGRAM.xml` | 無宣告 | 待測 / 待測 |
| `END LOOP` | `END LOOP.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `END MATRIX` | `END MATRIX.xml` | 無宣告 | 待測 / 待測 |
| `END PROGRAM` | `END PROGRAM.xml` | 無宣告 | 待測 / 待測 |
| `END REPEAT` | `END REPEAT.xml` | 無宣告 | 待測 / 待測 |
| `ERASE` | `ERASE.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `EXECUTE` | `EXECUTE.xml` | 無宣告 | 待測 / 待測 |
| `EXTENSION` | `EXTENSION.xml` | GLOBAL_PARAMS, SPECIFICATION | 待測 / 待測 |
| `FINISH` | `FINISH.xml` | 無宣告 | 待測 / 待測 |
| `HOST` | `HOST.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `INCLUDE` | `INCLUDE.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `INSERT EXEC` | `INSERT EXEC.xml` | SUCCESS, FAILURE, CLEAR | 待測 / 待測 |
| `INSERT HIDDEN` | `INSERT HIDDEN.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `INSERT` | `INSERT.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `LOOP` | `LOOP.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `MATRIX` | `MATRIX.xml` | 無宣告 | 待測 / 待測 |
| `MODEL CLOSE` | `MODEL CLOSE.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `MODEL HANDLE` | `MODEL HANDLE.xml` | GLOBAL_PARAMS, OPTIONS, MAP | 待測 / 待測 |
| `MODEL LIST` | `MODEL LIST.xml` | 無宣告 | 待測 / 待測 |
| `MODEL NAME` | `MODEL NAME.xml` | 無宣告 | 待測 / 待測 |
| `PERMISSIONS` | `PERMISSIONS.xml` | GLOBAL_PARAMS, PERMISSIONS | 待測 / 待測 |
| `PRESERVE` | `PRESERVE.xml` | 無宣告 | 待測 / 待測 |
| `READ MODEL` | `READ MODEL.xml` | GLOBAL_PARAMS, KEEP, DROP, TYPE, TSET | 待測 / 待測 |
| `REPOSITORY ATTRIBUTES` | `REPOSITORY ATTRIBUTES.xml` | GLOBAL_PARAMS, SECURITY | 待測 / 待測 |
| `REPOSITORY CONNECT` | `REPOSITORY CONNECT.xml` | SERVER, LOGIN | 待測 / 待測 |
| `REPOSITORY COPY` | `REPOSITORY COPY.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `RESTORE` | `RESTORE.xml` | 無宣告 | 待測 / 待測 |
| `SAVE MODEL` | `SAVE MODEL.xml` | GLOBAL_PARAMS, KEEP, DROP, TYPE | 待測 / 待測 |
| `SCRIPT` | `SCRIPT.xml` | GLOBAL_PARAMS | 待測 / 待測 |
| `SET` | `SET.xml` | GLOBAL_PARAMS, AUTORECOVERY, WORKSPACE, FORMAT, CTEMPLATE, TLOOK, ONUMBERS, OVARS, TFIT, TNUMBERS, TVARS, RNG, SEED, MTINDEX, EPOCH, ERRORS, RESULTS, PRINTBACK, MESSAGES, MEXPAND, MPRINT, MNEST, MITERATE, BLANKS, UNDEFINED, MXWARNS, MXLOOPS, MXERRS, BLOCK, BOX, CCA, CCB, CCC, CCD, CCE, DECIMAL, CACHE, HEADER, LENGTH, WIDTH, SMALL, OLANG, DEFOLANG, SCALEMIN, SORT, LOCALE, THREADS, PXTWARNS, MCACHE, UNICODE, FUZZBITS, MIOUTPUT, ZCOMPRESSION, XVERSION, OATTRS, DIGITGROUPING, REPDEFER, CMPTRANS, MDISPLAY, BASETEXTDIRECTION, SUMMARY, LEADZERO | 文件核對 / 待測 |
| `SHOW` | `SHOW.xml` | GLOBAL_PARAMS, ALL, AUTORECOVERY, BLANKS, BOX, BLOCK, CC, CCA, CCB, CCC, CCD, CCE, CACHE, CTEMPLATE, DIGITGROUPING, DECIMAL, DEFOLANG, DIRECTORY, ENVIRONMENT, EPOCH, ERRORS, EXTPATHS, FILTER, FORMAT, FOOTNOTE, HEADER, LENGTH, LICENSE, LOCALE, MESSAGES, MEXPAND, MITERATE, MNEST, MPRINT, MXERRS, MXLOOPS, MXWARNS, N, OATTRS, OLANG, ONUMBERS, OVARS, PLUGINS, PRINTBACK, PXTWARNS, REPDEFER, RESULTS, SCALEMIN, SCOMPRESSION, SEED, SIGLESS, SMALL, SORT, SYSMIS, TFIT, TLOOK, TMSRECORDING, TNUMBERS, TVARS, UNDEFINED, UNICODE, VERSION, WEIGHT, WIDTH, WORKSPACE, XVERSION, $VARS, FUZZBITS, MIOUTPUT, HANDLES, ZCOMPRESSION, CMPTRANS, SPLIT, RNG, MDISPLAY, LEADZERO | 待測 / 待測 |
| `TIME PROGRAM` | `TIME PROGRAM.xml` | 無宣告 | 待測 / 待測 |
| `TSET` | `TSET.xml` | GLOBAL_PARAMS, PRINT, NEWVAR, MXAUTO, MXCROSS, MXNEWVARS, MXPREDICT, MISSING, CIN, TOLER, CNVERGE, ACFSE, PERIOD, ID, CONSTANT, NOCONSTANT, DEFAULT | 待測 / 待測 |

