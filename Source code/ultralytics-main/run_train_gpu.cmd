@echo off
setlocal EnableExtensions

set "PROJECT_DIR=%~dp0"
if not defined TRAIN_PYTHON set "TRAIN_PYTHON=python"
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
set "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True"

"%TRAIN_PYTHON%" --version >nul 2>&1
if errorlevel 1 goto missing_python
if not exist "%PROJECT_DIR%train_gpu_10class.py" goto missing_script

pushd "%PROJECT_DIR%"

echo ============================================================
echo Wood Defect 10-Class GPU Training
echo GPU: CUDA device 0 by default
echo Image size: 896
echo Batch size: automatic, about 60 percent of available VRAM
echo Epochs: up to 300, early stop after 30 stale epochs
echo Output: %PROJECT_DIR%runs\detect
echo ============================================================
echo.

"%TRAIN_PYTHON%" train_gpu_10class.py --device 0 --batch -1 --workers 4 %*
set "TRAIN_EXIT_CODE=%ERRORLEVEL%"

popd
echo.
if not "%TRAIN_EXIT_CODE%"=="0" goto training_failed

echo [DONE] Training finished successfully.
echo Find the best model under runs\detect\...\weights\best.pt
pause
exit /b 0

:missing_python
echo [ERROR] Training Python was not found:
echo %TRAIN_PYTHON%
pause
exit /b 1

:missing_script
echo [ERROR] Training script was not found:
echo %PROJECT_DIR%train_gpu_10class.py
pause
exit /b 1

:training_failed
echo [ERROR] Training exited with code %TRAIN_EXIT_CODE%.
echo Keep the error text above. An existing last.pt can be resumed later.
pause
exit /b %TRAIN_EXIT_CODE%
