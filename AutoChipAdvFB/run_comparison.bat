@echo off
REM ================================================================
REM  AutoChip Advanced Feedback — Full Comparison Runner
REM  Runs baseline vs advanced for all 5 Ollama models
REM
REM  Usage:
REM    run_comparison.bat              -> all models, both conditions
REM    run_comparison.bat gemma3:12b   -> one model, both conditions
REM    run_comparison.bat gemma3:12b advanced d_latch_gated  -> single module
REM ================================================================

set MODEL=%1
set MODE=%2
set MODULE=%3

REM ── Default mode is both (baseline + advanced comparison) ────────
if "%MODE%"=="" set MODE=both

REM ── If a specific model was given, just run that one ─────────────
if NOT "%MODEL%"=="" goto run_single

REM ── No model given: loop through all 5 Ollama models ─────────────
echo.
echo ================================================================
echo  Running AutoChip Advanced Feedback Benchmark
echo  Mode: %MODE%  ^|  All 5 models
echo ================================================================
echo.

python autochip_adv_runner.py --model gemma3:4b          --mode %MODE%
python autochip_adv_runner.py --model gemma3:12b         --mode %MODE%
python autochip_adv_runner.py --model qwen2.5-coder:14b  --mode %MODE%
python autochip_adv_runner.py --model llama3.1           --mode %MODE%
python autochip_adv_runner.py --model deepseek-coder:6.7b --mode %MODE%

echo.
echo ================================================================
echo  All models done. Results in results\
echo ================================================================
goto end

REM ── Single model run ─────────────────────────────────────────────
:run_single
echo.
echo ================================================================
echo  Model: %MODEL%   Mode: %MODE%
echo ================================================================
echo.

if "%MODULE%"=="" (
    python autochip_adv_runner.py --model %MODEL% --mode %MODE%
) else (
    python autochip_adv_runner.py --model %MODEL% --mode %MODE% --module %MODULE%
)

:end
