# Synthetic 6-study fixture; reference values from R meta/metafor for tests/test_meta.py
suppressPackageStartupMessages({library(meta); library(metafor); library(jsonlite)})
d <- data.frame(study=paste0("S",1:6), e1=c(12,3,0,45,8,10), n1=c(100,40,30,500,60,150), e2=c(18,5,2,40,19,35), n2=c(98,42,31,490,58,148), x=c(60,65,70,55,72,68), g=c("a","a","b","b","a","b"))
m <- metabin(e1,n1,e2,n2,data=d,studlab=study,sm="OR",method="Inverse",method.tau="DL",random=TRUE,common=TRUE,method.random.ci="classic",incr=0.5,method.incr="only0")
hk <- update(m, method.random.ci="HK"); reml <- update(m, method.tau="REML"); pm <- update(m, method.tau="PM")
pe <- metabin(e1,n1,e2,n2,data=d,studlab=study,sm="OR",method="Peto")
mh <- metabin(e1,n1,e2,n2,data=d,studlab=study,sm="OR",method="MH",incr=0,method.incr="only0",MH.exact=TRUE)
sg <- metabin(e1,n1,e2,n2,data=d,studlab=study,sm="OR",method="Inverse",method.tau="DL",subgroup=g,tau.common=FALSE,random=TRUE,common=FALSE,method.random.ci="classic")
eg <- metabias(m, method.bias="Egger", k.min=3)
ci <- confint(rma(yi=m$TE, sei=m$seTE, method="DL"))$random
es <- escalc(measure="OR", ai=e1, n1i=n1, ci=e2, n2i=n2, data=d, add=0.5, to="only0")
mr <- rma(yi, vi, mods=~x, data=es, method="REML", test="knha"); mr0 <- rma(yi, vi, data=es, method="REML")
mrdl <- rma(yi, vi, mods=~x, data=es, method="DL", test="z")
out <- list(TE=m$TE, seTE=m$seTE, common=c(m$TE.common,m$seTE.common,m$lower.common,m$upper.common,m$pval.common), random=c(m$TE.random,m$seTE.random,m$lower.random,m$upper.random,m$pval.random),
  hk=c(hk$TE.random,hk$seTE.random,hk$lower.random,hk$upper.random,hk$pval.random), tau2=m$tau2, I2=m$I2*100, H=m$H, Q=m$Q, pQ=m$pval.Q, predict=c(m$lower.predict,m$upper.predict),
  reml_tau2=reml$tau2, pm_tau2=pm$tau2, peto=c(pe$TE.common,pe$seTE.common), mh=c(mh$TE.common,mh$seTE.common), egger=c(eg$estimate[1],eg$estimate[2],eg$statistic,eg$p.value),
  tau2_ci=c(ci["tau^2","ci.lb"],ci["tau^2","ci.ub"]), sub_TE=sg$TE.random.w, sub_lower=sg$lower.random.w, sub_upper=sg$upper.random.w, sub_tau2=sg$tau2.w, Qb=sg$Q.b.random, pb=sg$pval.Q.b.random,
  mr_beta=as.numeric(mr$beta), mr_se=as.numeric(mr$se), mr_p=as.numeric(mr$pval), mr_tau2=mr$tau2, mr_tau2_0=mr0$tau2, mr_R2=mr$R2, mr_QE=mr$QE, mrdl_beta=as.numeric(mrdl$beta), mrdl_se=as.numeric(mrdl$se), mrdl_tau2=mrdl$tau2)
write_json(out, "validation/meta/synthetic_oracle.json", auto_unbox=TRUE, digits=NA, pretty=TRUE)
cat("ok\n")
