# Installs the R packages used by the *_r meta-analysis methods (meta, metafor, rjags, RTSA, jsonlite, coda).
# JAGS itself (the sampler behind rjags) is a separate program: https://mcmc-jags.sourceforge.io
# Usage: Rscript install_packages.R   (or: python -m statstudio install-r-packages)
pkgs <- c("jsonlite", "coda", "meta", "metafor", "rjags", "RTSA")
repo <- "https://cloud.r-project.org"
missing <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) {
  cat("Installing:", paste(missing, collapse = ", "), "\n")
  install.packages(missing, repos = repo, quiet = TRUE)
} else {
  cat("All R packages already installed.\n")
}
for (p in pkgs) {
  ok <- requireNamespace(p, quietly = TRUE)
  cat(sprintf("  %-9s %s\n", p, if (ok) as.character(utils::packageVersion(p)) else "MISSING"))
}
jags <- tryCatch({ suppressPackageStartupMessages(library(rjags)); as.character(rjags::jags.version()) }, error = function(e) NULL)
if (is.null(jags)) {
  cat("JAGS not found. Install JAGS 4.x from https://mcmc-jags.sourceforge.io and re-run this script.\n")
} else {
  cat(sprintf("  JAGS      %s\n", jags))
}
