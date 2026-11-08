# R backend for the StatStudio meta-analysis methods.
#   meta_binary        -> meta::metabin (+ metafor::confint for the tau^2 Q-profile interval)
#   meta_regression    -> metafor::rma (REML/DL, Knapp-Hartung)
#   bayes_meta_binary  -> rjags / JAGS binomial-normal hierarchical model
#   tsa_binary         -> RTSA (R implementation of the Copenhagen Trial Unit TSA software)
# Usage: Rscript meta_backend.R request.json result.json
# The result uses the same table schema as src/statstudio/meta.py so that clients render it unchanged.
suppressPackageStartupMessages(library(jsonlite))
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2) stop("usage: Rscript meta_backend.R request.json result.json")
req <- fromJSON(args[1], simplifyVector = TRUE)
method <- req$method; o <- req$options
d <- as.data.frame(req$data, stringsAsFactors = FALSE)
d$study <- as.character(d$study)
tbl <- function(title, columns, rows) list(title = title, columns = columns, rows = rows)
nz <- function(x) if (is.null(x) || length(x) == 0 || (length(x) == 1 && is.na(x))) NA else unname(x)
versions <- function(...) { p <- c(...); v <- lapply(p, function(x) as.character(packageVersion(x))); names(v) <- p; c(list(R = R.version.string), v) }
double_zero <- function(d) (d$e1 == 0 & d$e2 == 0) | (d$e1 == d$n1 & d$e2 == d$n2)

# ---------------------------------------------------------------------------------------------------------- meta_binary
run_meta_binary <- function(d, o) {
  suppressPackageStartupMessages({library(meta); library(metafor)})
  measure <- o$measure; incr <- as.numeric(o$cc); conf <- as.numeric(o$confidence); mt <- o$tau2_method; lab <- measure
  pred_df_method <- if (identical(o$prediction_df, "k-2")) "k-2" else "k-1"; pred_method <- if (pred_df_method == "k-2") "HTS" else "V"
  warnings <- list(); dz <- double_zero(d); du <- d[!dz, ]
  if (any(dz)) warnings[[length(warnings) + 1]] <- paste0("兩組皆無事件（或皆為事件）的研究無法估計效應，已排除於反變異數合併之外：", paste(d$study[dz], collapse = ", "))
  if (nrow(du) < 1) stop("沒有可估計的研究。")
  m <- metabin(e1, n1, e2, n2, data = du, studlab = study, sm = measure, method = "Inverse", method.tau = mt, random = TRUE, common = TRUE,
               method.random.ci = "classic", incr = incr, method.incr = "only0", prediction = TRUE, method.predict = pred_method, level = conf, level.ma = conf, level.predict = conf)
  k <- m$k; pred_df <- if (k >= 3) (if (pred_df_method == "k-2") k - 2 else k - 1) else NA; zero <- with(du, e1 == 0 | e1 == n1 | e2 == 0 | e2 == n2)
  if (any(zero)) warnings[[length(warnings) + 1]] <- paste0("對含零格的研究四格各加 ", incr, " 作連續性校正：", paste(du$study[zero], collapse = ", "), "。Peto 與 MH 估計不使用此校正。")
  wc <- m$w.common / sum(m$w.common) * 100; wr <- m$w.random / sum(m$w.random) * 100
  est <- vector("list", nrow(d)); j <- 0
  for (i in seq_len(nrow(d))) {
    if (!dz[i]) { j <- j + 1
      est[[i]] <- list(d$study[i], d$e1[i], d$n1[i], d$e2[i], d$n2[i], exp(m$TE[j]), exp(m$lower[j]), exp(m$upper[j]), m$TE[j], m$seTE[j], wc[j], wr[j], if (zero[j]) incr else 0, "yes")
    } else est[[i]] <- list(d$study[i], d$e1[i], d$n1[i], d$e2[i], d$n2[i], NA, NA, NA, NA, NA, NA, NA, 0, "no (not estimable)")
  }
  pooled <- list(
    list("Common effect (inverse variance)", k, exp(m$TE.common), exp(m$lower.common), exp(m$upper.common), m$TE.common, m$seTE.common, m$statistic.common, m$pval.common, "z"),
    list(paste0("Random effects (inverse variance, ", mt, ")"), k, exp(m$TE.random), exp(m$lower.random), exp(m$upper.random), m$TE.random, m$seTE.random, m$statistic.random, m$pval.random, "z"))
  if (k >= 2) { hk <- update(m, method.random.ci = "HK")
    pooled[[length(pooled) + 1]] <- list(paste0("Random effects, Hartung–Knapp CI (", mt, ")"), k, exp(hk$TE.random), exp(hk$lower.random), exp(hk$upper.random), hk$TE.random, hk$seTE.random, hk$statistic.random, hk$pval.random, paste0("t(", k - 1, ")")) }
  if (measure == "OR") {
    pe <- tryCatch(metabin(e1, n1, e2, n2, data = du, studlab = study, sm = "OR", method = "Peto", level = conf, level.ma = conf), error = function(e) NULL)
    if (!is.null(pe) && is.finite(pe$TE.common)) pooled[[length(pooled) + 1]] <- list("Peto common-effect OR (no continuity correction)", pe$k, exp(pe$TE.common), exp(pe$lower.common), exp(pe$upper.common), pe$TE.common, pe$seTE.common, pe$statistic.common, pe$pval.common, "z")
    mh <- tryCatch(metabin(e1, n1, e2, n2, data = du, studlab = study, sm = "OR", method = "MH", incr = 0, method.incr = "only0", MH.exact = TRUE, level = conf, level.ma = conf), error = function(e) NULL)
    if (!is.null(mh) && is.finite(mh$TE.common)) pooled[[length(pooled) + 1]] <- list("Mantel–Haenszel common-effect OR (no continuity correction)", mh$k, exp(mh$TE.common), exp(mh$lower.common), exp(mh$upper.common), mh$TE.common, mh$seTE.common, mh$statistic.common, mh$pval.common, "z")
  }
  ci <- c(NA, NA)
  if (k >= 3) ci <- tryCatch({ cc <- confint(rma(yi = m$TE, sei = m$seTE, method = mt), level = conf * 100)$random; c(cc["tau^2", "ci.lb"], cc["tau^2", "ci.ub"]) }, error = function(e) c(NA, NA))
  het <- list(list(m$tau2, ci[1], ci[2], sqrt(m$tau2), if (k >= 2) m$I2 * 100 else NA, if (k >= 2) m$H else NA, m$Q, m$df.Q, if (k >= 2) m$pval.Q else NA,
                   if (k >= 3) exp(m$lower.predict) else NA, if (k >= 3) exp(m$upper.predict) else NA, if (k >= 2) m$H^2 else NA, pred_df))
  tables <- list(
    tbl("Study estimates", c("Study", "Events (exp)", "N (exp)", "Events (ctrl)", "N (ctrl)", lab, paste(lab, "lower"), paste(lab, "upper"), paste("log", lab), "SE", "Weight common %", "Weight random %", "Continuity correction", "Pooled"), est),
    tbl("Pooled estimates", c("Model", "k", lab, paste(lab, "lower"), paste(lab, "upper"), paste("log", lab), "SE", "Test statistic", "p", "Reference distribution"), pooled),
    tbl("Heterogeneity", c("tau²", "tau² lower (Q-profile)", "tau² upper (Q-profile)", "tau", "I² %", "H", "Q", "df", "p (Q)", paste0("Prediction interval lower (", lab, ")"), paste0("Prediction interval upper (", lab, ")"), "H²", "Prediction interval df"), het))
  if (k >= 3) { eg <- tryCatch(metabias(m, method.bias = "Egger", k.min = 3), error = function(e) NULL)
    if (!is.null(eg)) tables[[length(tables) + 1]] <- tbl("Small-study effects (Egger regression)", c("k", "Intercept", "SE", "t", "df", "p", "Note"),
                                                          list(list(k, unname(eg$estimate[1]), unname(eg$estimate[2]), unname(eg$statistic), k - 2, unname(eg$p.value), if (k < 10) "k < 10：Egger 檢定效力不足，僅供參考" else ""))) }
  tables[[length(tables) + 1]] <- tbl("Event totals", c("Arm", "Events", "N", "Proportion"), list(list("Experimental", sum(d$e1), sum(d$n1), sum(d$e1) / sum(d$n1)), list("Control", sum(d$e2), sum(d$n2), sum(d$e2) / sum(d$n2))))
  if (!is.null(d$subgroup)) {
    sg <- du$subgroup; keep <- !is.na(sg)
    if (any(!keep)) warnings[[length(warnings) + 1]] <- "子群欄位含缺失值的研究不納入子群分析。"
    ds <- du[keep, ]; ds$subgroup <- as.character(ds$subgroup)
    ms <- metabin(e1, n1, e2, n2, data = ds, studlab = study, sm = measure, method = "Inverse", method.tau = mt, random = TRUE, common = FALSE, method.random.ci = "classic",
                  incr = incr, method.incr = "only0", level = conf, level.ma = conf, subgroup = subgroup, tau.common = FALSE)
    rows <- lapply(seq_along(ms$subgroup.levels), function(i) list(as.character(ms$subgroup.levels[i]), ms$k.w[i], exp(ms$TE.random.w[i]), exp(ms$lower.random.w[i]), exp(ms$upper.random.w[i]), ms$tau2.w[i], if (ms$k.w[i] >= 2) ms$I2.w[i] * 100 else NA, ms$Q.w[i], ms$k.w[i] - 1, if (ms$k.w[i] >= 2) ms$pval.Q.w[i] else NA))
    if (length(ms$subgroup.levels) >= 2) rows[[length(rows) + 1]] <- list("Test for subgroup differences (random effects)", NA, NA, NA, NA, NA, NA, ms$Q.b.random, ms$df.Q.b.random, ms$pval.Q.b.random)
    tables[[length(tables) + 1]] <- tbl("Subgroups", c("Subgroup", "k", lab, paste(lab, "lower"), paste(lab, "upper"), "tau²", "I² %", "Q", "df", "p"), rows)
    if (any(ms$k.w == 1)) warnings[[length(warnings) + 1]] <- "至少一個子群只有 1 篇研究；子群差異檢定不具參考價值。"
  }
  warnings[[length(warnings) + 1]] <- paste0("計算由 R meta ", packageVersion("meta"), " / metafor ", packageVersion("metafor"), " 執行（metabin, method = Inverse, method.incr = only0；metafor confint 求 tau² Q-profile 區間）。I² 與 Q 在研究數少時不穩定；子群與 Egger 檢定為探索性。")
  list(tables = tables, warnings = warnings,
       charts = list(list(kind = "scatter", title = "Funnel plot data (log effect vs standard error)", x = as.list(unname(m$TE)), y = as.list(unname(m$seTE)), x_label = paste("log", lab), y_label = "Standard error")),
       details = list(k_pooled = k, k_input = nrow(d), measure = measure, tau2_method = mt, continuity_correction = incr, double_zero_excluded = as.list(d$study[dz]),
                      prediction_interval = list(df_method = pred_df_method, df = pred_df, method_predict = pred_method, se = "classic random-effects pooled SE", minimum_k = 3),
                      heterogeneity_method = "q", heterogeneity_definition = "R meta: H² = Q/(k-1); I² = max(0, (Q-df)/Q)*100"),
       software = versions("meta", "metafor"))
}

# ---------------------------------------------------------------------------------------------------------- meta_regression
run_meta_regression <- function(d, o) {
  suppressPackageStartupMessages(library(metafor))
  measure <- o$measure; incr <- as.numeric(o$cc); conf <- as.numeric(o$confidence); mt <- o$tau2_method; kh <- identical(o$knapp_hartung, "yes"); mod_name <- o$moderator_name
  warnings <- list(); dz <- double_zero(d); x <- suppressWarnings(as.numeric(d$moderator)); keep <- !dz & is.finite(x)
  if (any(!keep)) warnings[[length(warnings) + 1]] <- paste0(sum(!keep), " 篇研究因效應不可估計或調節變數缺失而未納入迴歸。")
  du <- d[keep, ]; du$x <- x[keep]; k <- nrow(du)
  if (k < 4) stop("單變量統合迴歸至少需要 4 篇可用研究；研究數少於 10 時結果僅供探索。")
  if (sd(du$x) == 0) stop("調節變數為常數。")
  es <- escalc(measure = measure, ai = e1, n1i = n1, ci = e2, n2i = n2, data = du, add = incr, to = "only0")
  ctrl <- list(threshold = 1e-12, maxiter = 1000)
  f <- rma(yi, vi, mods = ~ x, data = es, method = mt, test = if (kh) "knha" else "z", level = conf * 100, control = ctrl)
  f0 <- rma(yi, vi, data = es, method = mt, control = ctrl)
  dist <- if (kh) paste0("t(", k - 2, ")") else "z"
  coef_rows <- lapply(1:2, function(j) list(c("Intercept", mod_name)[j], as.numeric(f$beta[j]), as.numeric(f$se[j]), as.numeric(f$ci.lb[j]), as.numeric(f$ci.ub[j]), as.numeric(f$zval[j]), dist, as.numeric(f$pval[j]), exp(as.numeric(f$beta[j]))))
  w <- weights(f)
  r2 <- if (f0$tau2 > 0) max(0, 1 - f$tau2 / f0$tau2) * 100 else NA
  tables <- list(
    tbl("Meta-regression coefficients", c("Term", "Estimate (log scale)", "SE", paste0("Lower ", round(conf * 100), "% CI"), paste0("Upper ", round(conf * 100), "% CI"), "Statistic", "Reference distribution", "p", "exp(estimate)"), coef_rows),
    tbl("Meta-regression heterogeneity", c("k", "tau² residual", "tau² (no moderator)", "R² %", "Q_E (residual)", "df", "p (Q_E)", "Test of moderator", "p (moderator)"), list(list(k, f$tau2, f0$tau2, r2, f$QE, k - 2, f$QEp, f$QM, f$QMp))),
    tbl("Studies in regression", c("Study", "Moderator", "log effect", "SE", "Weight %"), lapply(seq_len(k), function(i) list(du$study[i], du$x[i], as.numeric(es$yi[i]), sqrt(as.numeric(es$vi[i])), as.numeric(w[i])))))
  if (k < 10) warnings[[length(warnings) + 1]] <- paste0("僅 ", k, " 篇研究：統合迴歸為探索性（Cochrane 建議每個共變量至少 10 篇），切勿據此宣稱顯著調節效應。")
  warnings[[length(warnings) + 1]] <- paste0("計算由 R metafor ", packageVersion("metafor"), " 執行（rma, method = ", mt, ", test = ", if (kh) "knha" else "z", "）。")
  list(tables = tables, warnings = warnings,
       charts = list(list(kind = "scatter", title = paste0("Bubble data: ", mod_name, " vs log effect"), x = as.list(du$x), y = as.list(as.numeric(es$yi)), x_label = mod_name, y_label = "log effect")),
       details = list(k_used = k, tau2_method = mt, knapp_hartung = o$knapp_hartung), software = versions("metafor"))
}

# ---------------------------------------------------------------------------------------------------------- bayes_meta_binary
re_model <- "model {
  for (i in 1:k) { r0[i] ~ dbin(p0[i], n0[i]); r1[i] ~ dbin(p1[i], n1[i]); logit(p0[i]) <- mu[i]; logit(p1[i]) <- mu[i] + delta[i]
    delta[i] ~ dnorm(d, prec); mu[i] ~ dnorm(0, 1 / (sd_mu * sd_mu)) }
  d ~ dnorm(0, 1 / (sd_d * sd_d)); tau ~ dnorm(0, 1 / (hn * hn)) T(0, ); prec <- 1 / (tau * tau) }"
fe_model <- "model {
  for (i in 1:k) { r0[i] ~ dbin(p0[i], n0[i]); r1[i] ~ dbin(p1[i], n1[i]); logit(p0[i]) <- mu[i]; logit(p1[i]) <- mu[i] + d
    mu[i] ~ dnorm(0, 1 / (sd_mu * sd_mu)) }
  d ~ dnorm(0, 1 / (sd_d * sd_d)) }"
run_bayes <- function(d, o) {
  suppressPackageStartupMessages({library(rjags); library(coda)}); load.module("dic")
  model <- o$model; sd_d <- as.numeric(o$prior_effect_sd); hn <- as.numeric(o$prior_tau_scale); sd_mu <- as.numeric(o$prior_baseline_sd)
  chains <- as.integer(o$chains); iters <- as.integer(o$iterations); burn <- as.integer(o$burnin); seed <- as.integer(o$seed); conf <- as.numeric(o$confidence)
  if (nrow(d) < 2) stop("貝氏統合分析至少需要 2 篇研究。")
  set.seed(seed); seeds <- sample.int(1e6, chains)
  dat <- list(k = nrow(d), r1 = d$e1, n1 = d$n1, r0 = d$e2, n0 = d$n2, sd_d = sd_d, sd_mu = sd_mu); if (model == "random") dat$hn <- hn
  jm <- jags.model(textConnection(if (model == "random") re_model else fe_model), data = dat, n.chains = chains, n.adapt = burn, quiet = TRUE,
                   inits = lapply(seeds, function(s) list(.RNG.name = "base::Mersenne-Twister", .RNG.seed = s)))
  vars <- c("d", "mu", "deviance", if (model == "random") c("tau", "delta"))
  s <- coda.samples(jm, vars, n.iter = iters, progress.bar = "none"); mat <- as.matrix(s)
  dd <- mat[, "d"]; ors <- exp(dd); lo_q <- (1 - conf) / 2; hi_q <- (1 + conf) / 2
  summ <- function(x) list(median(x), mean(x), sd(x), unname(quantile(x, lo_q)), unname(quantile(x, hi_q)))
  rh <- function(v) if (chains >= 2) unname(gelman.diag(s[, v, drop = FALSE], multivariate = FALSE)$psrf[1, 1]) else NA
  ess <- function(v) unname(effectiveSize(s[, v, drop = FALSE]))
  rows <- list(c(list("log OR (d)"), summ(dd), list(rh("d"), ess("d"))), c(list("OR = exp(d)"), summ(ors), list(rh("d"), ess("d"))))
  if (model == "random") { tau <- mat[, "tau"]; pred <- exp(dd + rnorm(length(dd)) * tau)
    rows[[3]] <- c(list("tau (between-study SD, log OR)"), summ(tau), list(rh("tau"), ess("tau"))); rows[[4]] <- c(list("Predicted OR in a new study"), summ(pred), list(NA, NA)) }
  probs <- lapply(c(1, 0.9, 0.8, 0.75), function(t) list(paste0("OR < ", format(t)), mean(ors < t))); probs[[5]] <- list("OR > 1 (harm)", mean(ors > 1)); probs[[6]] <- list("OR > 1.1", mean(ors > 1.1))
  mu_bar <- colMeans(mat[, grep("^mu\\[", colnames(mat)), drop = FALSE])
  if (model == "random") { dm <- mat[, grep("^delta\\[", colnames(mat)), drop = FALSE]; delta_bar <- colMeans(dm); delta_sd <- apply(dm, 2, sd) } else { delta_bar <- rep(mean(dd), nrow(d)); delta_sd <- rep(sd(dd), nrow(d)) }
  dbar <- mean(mat[, "deviance"])
  dhat <- -2 * (sum(dbinom(d$e2, d$n2, plogis(mu_bar), log = TRUE)) + sum(dbinom(d$e1, d$n1, plogis(mu_bar + delta_bar), log = TRUE)))
  shr <- lapply(seq_len(nrow(d)), function(i) list(d$study[i], unname(delta_bar[i]), unname(delta_sd[i]), exp(unname(delta_bar[i]))))
  thin <- function(x, n) x[round(seq(1, length(x), length.out = min(n, length(x))))]
  warnings <- list(paste0("計算由 R rjags ", packageVersion("rjags"), "（JAGS ", jags.version(), "）執行：二項分布概似、Gibbs／slice 取樣；兩組皆零事件的研究仍納入。先驗為弱資訊性，請以敏感度分析檢查。DIC 以研究層級參數為焦點（Spiegelhalter 2002）。"))
  if (!is.na(rh("d")) && rh("d") > 1.05) warnings[[length(warnings) + 1]] <- "R-hat > 1.05：鏈未充分收斂，請增加 iterations 或 burnin。"
  list(tables = list(
         tbl("Posterior summary", c("Parameter", "Median", "Mean", "SD", paste0(lo_q * 100, "%"), paste0(hi_q * 100, "%"), "R-hat (split)", "ESS (coda)"), rows),
         tbl("Posterior probabilities", c("Statement", "Probability"), probs),
         tbl("Model fit", c("Model", "Dbar", "D(theta-bar)", "pD", "DIC"), list(list(model, dbar, dhat, dbar - dhat, 2 * dbar - dhat))),
         tbl("Study-specific (shrunken) log OR", c("Study", "Posterior mean", "Posterior SD", "OR"), shr)),
       warnings = warnings,
       charts = list(list(kind = "histogram", title = "Posterior of OR", values = as.list(thin(ors, 20000)), bins = 60, x_label = "OR", y_label = "Posterior density")),
       details = list(model = model, chains = chains, iterations_per_chain = iters, burnin = burn, seed = seed,
                      priors = list(d = sprintf("normal(0, sd=%g)", sd_d), tau = if (model == "random") sprintf("half-normal(scale=%g)", hn) else NA, mu_i = sprintf("normal(0, sd=%g)", sd_mu)),
                      likelihood = "binomial (logit link), study-specific baseline, exchangeable log OR", sampler = paste0("JAGS ", jags.version(), " via rjags (Gibbs / slice sampling)"), k = nrow(d),
                      posterior_draws_d = as.list(unname(thin(dd, 4000)))),
       software = c(versions("rjags", "coda"), list(JAGS = as.character(jags.version()))))
}

# ---------------------------------------------------------------------------------------------------------- tsa_binary
run_tsa <- function(d, o) {
  suppressPackageStartupMessages({library(RTSA); library(meta)})
  if (!identical(o$tau2_method, "DL")) stop("RTSA 只支援 DerSimonian–Laird tau²（tau2_method = DL）。")
  if (abs(as.numeric(o$cc) - 0.5) > 1e-12) stop("RTSA 的零格校正固定為 0.5（cc = 0.5）。")
  alpha <- as.numeric(o$alpha); power <- as.numeric(o$power)
  if (!is.null(d$order)) { ord <- suppressWarnings(as.numeric(d$order)); if (any(is.na(ord))) stop("排序欄位含缺失值。"); d <- d[order(ord), ] }
  dz <- double_zero(d); du <- d[!dz, ]; k <- nrow(du)
  if (k < 2) stop("至少需要 2 篇可估計的研究。")
  pC <- if (as.numeric(o$control_risk) == 0) sum(d$e2) / sum(d$n2) else as.numeric(o$control_risk)
  if (!(pC > 0 && pC < 1)) stop("對照組事件比例必須介於 0 與 1。")
  if (as.numeric(o$rrr) == 0) {
    m <- metabin(e1, n1, e2, n2, data = du, studlab = study, sm = "OR", method = "Inverse", method.tau = "DL", incr = 0.5, method.incr = "only0")
    mc <- exp(m$TE.random); pE <- mc * pC / (1 - pC + mc * pC); rrr <- 1 - pE / pC; src <- "pooled random-effects estimate (converted from OR at the control event proportion)"
  } else { rrr <- as.numeric(o$rrr); pE <- pC * (1 - rrr); mc <- (pE / (1 - pE)) / (pC / (1 - pC)); src <- "user-specified" }
  if (!(rrr > 0 && rrr < 1)) stop("相對風險下降 (RRR) 必須介於 0 與 1（有效益方向）。")
  df <- data.frame(study = du$study, eI = du$e1, nI = du$n1, eC = du$e2, nC = du$n2, stringsAsFactors = FALSE)
  res <- suppressWarnings(RTSA(type = "analysis", data = df, outcome = "OR", mc = mc, pC = pC, side = 2, alpha = alpha, beta = 1 - power, es_alpha = "esOF", futility = "none",
                               weights = "IV", re_method = "DL", random_adj = "D2", power_adj = FALSE, zero_adj = 0.5))
  rdf <- res$results$results_df; he <- res$results$metaanalysis$hete_results$hete_est
  ris <- res$results$RIS; haris <- if (is.numeric(res$results$HARIS) && length(res$results$HARIS) == 1) res$results$HARIS else ris
  bnd <- rdf$upper[1:k]; bnd[!is.na(bnd) & bnd >= 20] <- NA; cumN <- cumsum(df$nI + df$nC); zr <- rdf$z_random[1:k]; za <- qnorm(1 - alpha / 2)
  rows <- lapply(1:k, function(i) {
    later <- bnd[i:k]; later <- later[!is.na(later)]; ref <- if (length(later)) min(later) else 20
    list(df$study[i], cumN[i], rdf$sma_timing[i], rdf$outcome_random[i], rdf$naiveCIrandom_lower[i], rdf$naiveCIrandom_upper[i], zr[i], if (is.na(bnd[i])) NA else bnd[i],
         if (!is.na(zr[i]) && abs(zr[i]) >= ref) "yes" else "no", if (!is.na(zr[i]) && abs(zr[i]) >= za) "yes" else "no") })
  grid <- seq(0.05, 1, by = 0.05)
  bg <- tryCatch(boundaries(timing = grid, alpha = alpha, beta = 1 - power, side = 2, es_alpha = "esOF", futility = "none", type = "design")$alpha_ubound[seq_along(grid)], error = function(e) rep(NA, length(grid)))
  bg[!is.na(bg) & bg >= 20] <- NA
  warnings <- list(paste0("計算由 R RTSA ", packageVersion("RTSA"), " 執行（哥本哈根試驗中心 TSA 軟體的 R 版）：只計算效益／危害監測邊界，未計算無效邊界；資訊分數很小時 RTSA 不回報邊界（> 8）。RRR 若取自合併估計屬事後假設，請同時報告預設 RRR 的結果。"))
  if (any(dz)) warnings[[length(warnings) + 1]] <- paste0("TSA 排除兩組皆零（或皆全）事件的研究：", paste(d$study[dz], collapse = "、"), "（TSA 軟體慣例，不計入累積資訊量）。")
  list(tables = list(
         tbl("Required information size", c("Control event proportion", "Anticipated RRR", "RRR source", "Intervention event proportion", "alpha (two-sided)", "power", "RIS (no heterogeneity adjustment)", "D² (diversity)", "Diversity-adjusted RIS", "Accrued participants", "Accrued / RIS", "tau²", "I² %"),
             list(list(pC, rrr, src, pE, alpha, power, ris, he$D.2, haris, res$results$AIS, res$results$AIS / haris, he$tau2, he$I.2 * 100))),
         tbl("Cumulative Z-curve", c("Study added", "Cumulative N", "Information fraction", "Cumulative OR", "Lower 95% CI", "Upper 95% CI", "Cumulative Z", "O'Brien–Fleming boundary (Lan–DeMets)", "Crossed monitoring boundary", "Conventional |Z| ≥ z(alpha/2)"), rows)),
       warnings = warnings, charts = list(),
       details = list(k = nrow(d), k_analysed = k, excluded_studies = as.list(d$study[dz]), boundary = "Lan–DeMets alpha-spending, O'Brien–Fleming-type, two-sided, efficacy/harm only (no futility boundaries); RTSA",
                      ris = haris, d2 = he$D.2, boundary_curve = list(t = as.list(grid), z = as.list(bg))),
       software = versions("RTSA", "meta"))
}

out <- switch(method,
  meta_binary = run_meta_binary(d, o), meta_regression = run_meta_regression(d, o), bayes_meta_binary = run_bayes(d, o), tsa_binary = run_tsa(d, o),
  stop(paste("unknown method", method)))
write_json(out, args[2], auto_unbox = TRUE, digits = NA, null = "null", na = "null")
