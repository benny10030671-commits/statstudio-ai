# 獨立統計引擎：實作與一致性規格

版本範圍：本文件對應 `src/statstudio/engine.py` 的 18 種分析方法。這些程序使用獨立 Python 實作與開源數值套件，執行不需 IBM SPSS。它們不是由 IBM 二進位程式反編譯還原的原始碼，也不代表已完整複製 SPSS。SPSS 程序與官方文件的清單見 [algorithm-catalog.md](algorithm-catalog.md)。

**驗證分兩層**：`tests/test_engine.py` 驗證已知解析解、資料處理邊界與輸出契約；另外的 SPSS oracle 比較才是特定資料、選項與欄位的一致性證據。通過前者不等於通過後者。引擎每個結果均保留 `parity_status: unverified`，避免把少數樣本上的通過誤當成全面相容。使用者應查看獨立的 parity 報告及其涵蓋範圍。

## 輸入與結果契約

```python
from statstudio.engine import METHODS, analyze
result = analyze(df, "ttest_independent", {
    "variables": ["score"], "group": "treatment", "confidence": .95,
    "variance": "both"
})
```

`METHODS` 提供方法 ID、繁體中文標籤、欄位角色與可用參數；UI 與 AI 工具都應讀取此清單。`analyze` 回傳 `title`、`tables`、`charts`、`warnings`、`details`。每張表有固定長度的欄名與列；數值保留 float64 精度，未預先四捨五入。無定義或溢位的數值以 JSON `null` 表示；不輸出非標準的 NaN/Infinity。不同分析各自回傳有效 N／缺失處理說明，並保留實際生效的完整選項。

共同規則：

- 只把真正的 NA 視為缺失值。數字 999 等使用者自訂缺失碼不會自行猜測；呼叫端必須先明確轉換。
- `weights`、`user_missing`、`split_file` 或任何未宣告選項都會被拒絕。權重、複雜抽樣、插補、多重比較校正及 SPSS 語法解析尚未實作。
- 數值程序不會把文字自動轉為數字；∞ 會被拒絕。對常數／奇異矩陣等無法估計的輸入，回傳錯誤或明列該統計量為空值，不偽造有限結果。
- 類別按原始數值或文字排序；不套用 SPSS 值標籤或依語系定序。文字與數字混用的類別欄位會被拒絕。每個類別欄位上限 100 類，每次最多 50 個變數。
- 全部檢定預設雙尾；ANOVA 的 F、卡方與其他 omnibus 檢定使用對應分布右尾。未提供單尾選項。
- `confidence` 預設 .95，必須介於 0 與 1。回傳兩個 CI 端點，不混同信賴區間與預測區間。
- 引擎不修改原始 DataFrame，不自行儲存資料，不連線到遠端，不自動刪除離群值。

## 已實作的方法

下列公式中，n 是有效樣本數，s² 使用 n−1 分母；α=1−confidence。方法名稱是 API 的固定識別碼。

### 1. 描述統計 `descriptive`

角色 `variables`。`missing=available`（逐變數排除）或 `listwise`。輸出 N、排除數、平均數、樣本 SD／變異數、平均數 SE、最小／最大、總和、中位數、Q25／Q75、偏態、超額峰度及平均數 t 信賴區間。

- mean=Σx/n，s²=Σ(x−mean)²/(n−1)，SE=s/√n。
- 平均數 CI = mean ± t(1−α/2,n−1)×SE。
- 令 m_j=Σ(x−mean)^j/n。調整偏態 G1=√[n(n−1)]/(n−2) × m3/m2^(3/2)。n≤2 或變異為零時不定義。
- 超額峰度 G2=(n−1)/[(n−2)(n−3)] × [(n+1)(m4/m2²−3)+6]。n≤3 或變異為零時不定義。
- `quantile=weibull` 預設，排序位置 h=(n+1)p；`linear` 為 h=1+(n−1)p；`hazen` 為 h=np+.5。位置以 1 起算，在相鄰排序值間線性插值，超出端點範圍則取最小／最大值。NumPy 的方法清單及定義見 [quantile 官方文件](https://numpy.org/doc/stable/reference/generated/numpy.quantile.html)。

SPSS 對照：普通 SD／偏態／峰度可對照 DESCRIPTIVES。SPSS DESCRIPTIVES 本身不提供這裡額外列出的中位數及四分位數；SPSS EXAMINE `HAVERAGE` 文檔的無權重位置式為 (n+1)p，因此提供 Weibull 選項。不同程序及有權重情境仍需另驗。偏態採用 [SciPy bias=False 定義](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.skew.html)。

### 2. 次數分配 `frequencies`

角色 `variables`。每一有效值的次數為 n_v，`Percent=100 n_v/n_input`，`Valid percent=100 n_v/n_valid`；累積百分比只累加有效類別。缺失列保留總百分比，沒有有效百分比／累積有效百分比。未提供眾數、加權、合併類別或自訂顯示順序。

### 3. 交叉表 `crosstabs`

角色 `x,y`，對兩欄 listwise。輸出觀察 O、期望 E、列百分比、欄百分比。E_ij = row_i×column_j/n；Pearson χ²=Σ(O−E)²/E，自由度 (r−1)(c−1)。Cramér V=√[χ²/(n×min(r−1,c−1))]。2×2 同時提供 Yates 校正卡方與 Fisher 雙尾精確檢定，其表中統計量是 odds ratio。出現 E<5 即提示近似限制。未提供分層、CMH、風險比、殘差 z 或多重反應交叉表。

### 4–6. t 檢定

所有差值 CI 都是 d±t_critical×SE；p=2 P(T_df≥|t|)。標準誤為零則拒絕檢定。

| 方法 | 角色與選項 | 計算 |
|---|---|---|
| `ttest_one` | variables，test_value 預設 0 | d=mean−μ0，SE=s/√n，df=n−1；逐變數排除缺失 |
| `ttest_independent` | variables,group；variance=both/pooled/welch，預設 both | d=mean1−mean2；組別按原始值排序；每個受測變數與 group 排除缺失 |
| `ttest_paired` | x,y | 對完整配對差值 x−y 進行 one-sample t，df=n_pairs−1 |

合併變異數 sp²=[(n1−1)s1²+(n2−1)s2²]/(n1+n2−2)，SE²=sp²(1/n1+1/n2)，df=n1+n2−2。Welch SE²=s1²/n1+s2²/n2；df=(s1²/n1+s2²/n2)² / [(s1²/n1)²/(n1−1)+(s2²/n2)²/(n2−1)]。獨立樣本另提供以**組平均數**為中心的 Levene F；不自動依 Levene 的 p 替使用者挑選變異數假設。SciPy 的 [t-test 參考](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_ind.html) 可交叉核對公式與尾向。

### 7. 單因子 ANOVA `anova`

角色 variables,group；每組至少 2 個有效值。SS_between=Σn_g(mean_g−grand_mean)²，SS_within=ΣΣ(x−mean_g)²。F=[SS_between/(k−1)]/[SS_within/(n−k)]。輸出三列 ANOVA、各組 N/mean/SD、Levene（平均中心）、η²=SS_between/SS_total、ω²=[SS_between−(k−1)MS_within]/[SS_total+MS_within]。ω² 是估計值，可為負數，不強制截為零。未提供 Welch ANOVA、事後比較、對比、GLM 或重複量數設計。

### 8. 相關 `correlation`

角色 variables，`coefficient=pearson`（預設）/spearman/kendall；`missing=pairwise` 預設，可改 listwise。矩陣旁另列每對 N、係數、雙尾 p。

- Pearson 為中心化向量的內積除以兩者離差平方和平方根；使用 SciPy `pearsonr` 的雙尾抽樣分布。n>3 時提供 Fisher z 信賴區間。
- Spearman 對平均等級求 Pearson，採 SciPy 的漸近 p；沒有精確置換。
- Kendall 為 τ-b，明確設定 `method=asymptotic`。
- 只有兩個完整配對且各自非定值時，仍列 ±1 係數，但不列推論 p 或 CI；常數／不足兩對則列空值。

相關不是因果，沒有控制共變數，也沒有做多重檢定修正。

### 9. OLS 線性迴歸 `linear_regression`

角色 target,predictors；predictors 目前僅接受數值，截距 `intercept=yes` 預設。選中所有欄位 listwise；要求完整樣本數大於所估參數數（含截距）且設計矩陣滿秩。透過 statsmodels OLS 的一般非穩健共變異估計。

β̂ 最小化 ||y−Xβ||²，係數共變異估計 MSE(X'X)^−1，t=β̂/SE；CI 使用 residual df 的 t 分布。標準化 β 為 B×SD_x/SD_y。輸出 R²、adjusted R²、殘差標準誤、F、ANOVA SS、AIC、BIC、係數與殘差對預測值圖。無截距時使用未中心化 total SS；不應直接與含截距模型的 R² 相比。

未實作 stepwise、缺失值插補、類別 dummy 編碼、交互作用、加權最小平方法、穩健標準誤、個別預測 CI 及 SPSS 容忍度剔除規則。高條件數會提示；秩不足直接拒絕，不以偽逆輸出不可識別係數。

### 10. 二元 Logit `logistic_regression`

角色 target,predictors。事件 `event=last` 預設，將兩種有效類別排序後最後者編為 1；`first` 可反轉。結果列出每個原始類別的 0/1 編碼。文字排序採 Python Unicode 次序，不保證與 SPSS 語系排序相同。

P(y=1|x)=1/[1+exp(−Xβ)]。最大化 Bernoulli log likelihood，statsmodels Newton solver，tol=1e−8、max_iter=100 預設（可調）。強制截距。Wald χ²=(B/SE)²、df=1；OR=exp(B)，OR CI=exp(B±z_critical SE)。似然比檢定對照僅截距模型；列 −2LL、Cox–Snell、Nagelkerke、McFadden pseudo-R² 和 cutoff=.5 分類表。[statsmodels Logit API](https://www.statsmodels.org/stable/generated/statsmodels.discrete.discrete_model.Logit.html) 是執行入口。

完全分離、資訊矩陣失敗或未收斂會拒絕結果。這不是完全分離的完备數學偵測器；近乎分離仍可能需要專業檢查。未提供 Firth、penalty、stepwise、類別 predictor contrasts、Hosmer–Lemeshow。SPSS 的迭代預設與停止門檻不同，係數相近不代表演算法路徑相同。

### 11. PCA `pca`

角色 variables；components=2；matrix=correlation（預設）/covariance；rotation=none（預設）/varimax。listwise，非定值，對稱特徵分解 R=VΛV'（或樣本共變異矩陣），特徵值降冪；負的微小浮點特徵值截為 0。未旋轉負荷量 L=V_k√Λ_k；共同性 h_i²=ΣL_ij²；解釋變異比 λ_j/trace(matrix)。

每個成分最大絕對負荷量的符號固定為正，僅作穩定呈現；不代表 SPSS 的符號慣例。沒有成分分數、Bartlett scoring、Kaiser>1 自動選取或 parallel analysis。

### 12. 主軸因素 `factor`

角色 variables；factors=1、rotation=none、max_iter=100、tolerance=1e−6。要求 n>p、相關矩陣滿秩，模型自由度 ((p−k)²−p−k)/2≥0。

初始共同性 SMC_i=1−1/(R^−1)_ii。每一步將 R 對角替換為前次 h²，抽取前 k 個正特徵值，L=V√Λ，以 ΣL² 更新 h²，最大絕對共同性差低於 tolerance 則停止。出現 h²>1+tolerance（Heywood）、非正抽取特徵值或不收斂即拒絕。另列 KMO（零對角相關平方和／相關與偏相關平方和）與 Bartlett 近似 −[n−1−(2p+5)/6]ln|R|，df=p(p−1)/2。

SPSS `FACTOR` 預設抽取方法是 principal components；本方法則明確主軸 PAF。不能以預設 FACTOR 結果驗證這個方法。尚未有 ML、ULS、GLS、alpha extraction、oblique rotation 或因素分數。

PCA 與 PAF 的 varimax 都先以每列 √共同性做 Kaiser normalization，SVD 更新正交旋轉矩陣以最大化 varimax criterion；停止上限 1000、相對 criterion 差 1e−8，停止後還原列尺度並固定符號。此停止規則與 SPSS 不同，旋轉排序也需容許置換後比較。

### 13. K-means `kmeans`

角色 variables（允許單一數值欄）；clusters=3、standardize=yes、seed=42、max_iter=300。可選使用原始單位。標準化使用樣本 SD（ddof=1）。採 [scikit-learn KMeans](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html)，Lloyd、tol=1e−4；回傳 inertia、迭代數、原始單位群中心與原始資料列號。群編號依群中心字典序重新編碼，以便重複顯示。

`initialization=kmeans++` 預設仍是 k-means++、20 次起始解。可選 `initialization=first`，以**前 k 個完整個案**作初始中心，只執行 1 次起始解；`details.initial_data_rows` 與 `initial_centers_original_units` 保留實際選中原始列與中心。缺失個案先排除。第一批中心若重複則拒絕，不自行找另一列替換。first 沒有隨機初始化，seed 不影響此初始化選取。兩種初始化的最終非空群數若少於 k 都拒絕報表，避免空群平均數造成偽結果。

`label_order=centroid` 預設依中心字典序編號；`native` 保留 KMeans 內部 cluster label+1，因此 first 初始化可保留其中心槽位順序。選項只改輸出編號，不改分群或距離。對照 SPSS 時應在分析前指定並記錄編號規則，不能看到結果後才任意重命名而宣称原始表一致。

Lloyd 停止條件為群別不再改變，或全部中心位移平方和 ≤ tol × 各特徵母體變異數的平均值；最大迭代限制也會終止。這是本機 scikit-learn 1.9.1 `_tolerance` / `_kmeans_single_lloyd` 的程式行為。提前停止後最後一次分派可能改變群別，模型中心尚未更新成新群別的算術平均；本工具保留**實際模型中心**，使表、inertia 與模型預測一致，並以 `final_centers_are_assignment_means=false` 和報表警告明示。標準化時 inertia 以標準化單位計算，中心表則還原成原始單位。

**已知不等價 SPSS QUICK CLUSTER 預設**：初始化、中心更新、停止規則、尺度與編號不同。first 可測試 SPSS NOINITIAL 使用前 k 個完整個案的初始化情境，卻沒有複製其後續全部更新與收斂規則。固定種子只保證相同環境／版本的重現性，並不保證 SPSS 的分群。若要完全對齊，需要另實作 QUICK CLUSTER 的各選項與初始化順序，不能僅修改 seed。

### 14. 階層分群 `hierarchical`

角色 variables（允許單一數值欄）；clusters=3、standardize=yes；linkage=ward（預設）/average/complete/single；distance=euclidean（預設）/sqeuclidean。SciPy `linkage` 後 `cut_tree` 切成指定群數；輸出每一步左右節點、距離、個案數以及最終群別。節點 0..n−1 指排除缺失後的順序，可用 `details.retained_data_rows` 映射回原資料列。

average 取兩群間所有個案對距離的平均。`sqeuclidean` 會**先計算每個個案對的距離平方，再平均**；不是把平均歐氏距離整體平方。示例 0、2、10：先合併 0 與 2，最後平均平方距離為 (100+64)/2=82，非 ((10+8)/2)²=81。

Ward 必須選 euclidean，否則明確拒絕；不能把平方歐氏距離直接餵入 Ward 的連結公式造成重複平方。Ward height 是 SciPy 的 linkage distance，不能逕稱為原始組內平方和增量。這項約束和各連結定義見 [SciPy linkage 官方文件](https://docs.scipy.org/doc/scipy/reference/generated/scipy.cluster.hierarchy.linkage.html)。

上限 5000 個完整個案，因距離矩陣需 O(n²) 記憶體。相同距離的合併順序、Ward 距離尺度與 SPSS cluster agglomeration coefficient 仍需另驗。SPSS CLUSTER 預設 BAVERAGE / squared Euclidean，本工具可以 `linkage=average,distance=sqeuclidean,standardize=no` 對照未標準化情境；本工具原預設維持 ward/euclidean，不會因增加選項而改變舊設定的意義。

`label_order=centroid` 依群中心字典序編號；可選 `native`，依各群最早出現的原始個案列號升序編號。此設定用來對照 SPSS 個案群號，兩種選項的 partition 完全相同。結果的 `cluster_label_rule` 保留具體規則，不把群號本身當成連續數值或品質高低順序。

### 15. 信度 `reliability`

角色 variables，listwise，至少兩題且各題非定值。Cronbach α=k/(k−1)×[1−Σs_j²/s_total²]。標準化 α 先用各題樣本 SD 標準化後使用同公式。校正項目總分相關為該題與其餘題總和的 Pearson；刪題 α 重新套用剩餘題。剩一題時 α 空值。沒有自動反向題處理；必須先依問卷定義轉碼。總分變異為零則拒絕，負 α 保留並提示。

### 16–18. 非參數程序

| 方法 | 實作與限制 |
|---|---|
| `mann_whitney` | x,group；恰兩組。平均等級同分，列第一組 U1、第二組 U2=n1n2−U1、min U。明確 `method=asymptotic`，同分校正，continuity=yes 預設可關閉。沒有小樣本 exact。 |
| `wilcoxon` | x,y；完整配對差 x−y，zero_method=wilcox（排除零差值），同分用平均等級。雙尾常態近似，continuity=no 預設。列正／負 rank sum、兩者較小者 W、z、p。 |
| `kruskal` | x,group；至少兩組。平均等級、同分校正 H，以 k−1 自由度卡方右尾計 p；沒有事後兩兩比較。 |

Mann–Whitney 近似分布的校正定義見 [SciPy 官方 API](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mannwhitneyu.html)。SPSS 不同命令與樣本大小的 exact／asymptotic 規則不一定相同，不能使用 SciPy auto 而宣稱相容。Wilcoxon 浮點相減誤差會影響同分判定；本實作不任意四捨五入差值。

## 輸出呈現的相容範圍

報表是繁體中文標題配英文欄名，為了與統計輸出核對；不是 SPSS Viewer、Pivot Table Editor 或 Chart Editor 的複製品。圖表目前為直方圖、長條圖與散點圖的資料規格，畫面由客戶端呈現。PCA 陡坡呈現使用長條特徵值圖。未重建 SPV、OMS 的全部表型、SPSS number formats、小數位與科學記號規則、模板、信賴帶、圖形語法、全部表註及缺失值腳註。因此數字欄位通過 parity，也不能推論版面／表型完全一致。

## 邊界測試

`tests/test_engine.py` 包含：樣本變異與偏峰態解析值、缺失百分比分母、未支援選項拒絕、文字及無限值拒絕、常數 t 檢定、數值類別排序、Welch 自由度、成對缺失遮罩、pairwise/listwise N 差異、OLS 已知投影與秩不足、Logit 正反事件編碼及分離、PCA trace/共同性、相同題目 α=1、全同值與全零差值秩檢定、average 平方距離先平方後平均、Ward 非歐氏拒絕、first 初始化的完整個案列與重複中心、提前停止後中心/inertia 一致、群編號選項不改 partition，以及全部 18 方法的矩形 JSON 輸出和原資料不變。

這些測試檢查數學與程式行為，不證明任何未測試的資料、選項、作業系統、BLAS 版本或 SPSS 程序之間完全一致。對外標記相容時，必須列出資料 hash、SPSS 版本、完整 syntax、本工具版本與選項、精確比較欄位及絕對／相對容許誤差。
