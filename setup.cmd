@echo off
setlocal
cd /d "%~dp0"
py -3.12 --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.12 is required. Install it from https://www.python.org/downloads/
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" py -3.12 -m venv .venv
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install -r requirements-lock.txt
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install --no-deps -e ".[test]"
if errorlevel 1 exit /b 1
where Rscript >nul 2>&1
if errorlevel 1 (
  echo [optional] R not found. The *_r meta-analysis methods need R 4.x with meta, metafor, rjags, RTSA and JAGS.
  echo            Install R from https://cloud.r-project.org and JAGS from https://mcmc-jags.sourceforge.io, then run: .venv\Scripts\python.exe -m statstudio install-r-packages
) else (
  Rscript "src\statstudio\r\install_packages.R"
)
echo Setup complete. Run start.cmd to open StatStudio AI.
endlocal
