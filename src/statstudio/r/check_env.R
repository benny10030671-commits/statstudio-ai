# Prints one JSON line describing the R environment used by the *_r meta-analysis methods.
pkgs <- c("meta", "metafor", "rjags", "RTSA", "jsonlite", "coda")
versions <- lapply(pkgs, function(p) if (requireNamespace(p, quietly = TRUE)) as.character(utils::packageVersion(p)) else NULL)
names(versions) <- pkgs
jags <- tryCatch({ suppressPackageStartupMessages(library(rjags)); as.character(rjags::jags.version()) }, error = function(e) NULL)
out <- list(r_version = R.version.string, r_home = R.home(), packages = versions, jags = jags)
if (requireNamespace("jsonlite", quietly = TRUE)) {
  cat(jsonlite::toJSON(out, auto_unbox = TRUE, null = "null"), "\n")
} else {
  cat(sprintf('{"r_version": "%s", "packages": {}, "jags": null, "error": "jsonlite not installed"}\n', R.version.string))
}
