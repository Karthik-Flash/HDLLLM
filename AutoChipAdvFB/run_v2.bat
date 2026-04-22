@echo off
REM ================================================================
REM  AutoChip Advanced Feedback v2 — Comparison Runner
REM
REM  Usage examples:
REM    run_v2.bat                          -> all 5 models, both conditions
REM    run_v2.bat gemma3:12b               -> one model, both conditions
REM    run_v2.bat gemma3:12b advanced      -> one model, advanced only
REM    run_v2.bat gemma3:12b both seg7_decoder  -> single module
REM ================================================================

set MODEL=%1
set MODE=%2
set MODULE=%3

if "%MODE%"=="" set MODE=both

REM ── Single model ─────────────────────────────────────────────────
if NOT "%MODEL%"=="" goto run_single

REM ── All 5 Ollama models ──────────────────────────────────────────
echo.
echo ================================================================
echo  AutoChip v2 Latch Inference Benchmark — All Models
echo  Mode: %MODE%
echo ================================================================
echo.

python autochip_adv_runner_v2.py --model gemma3:4b           --mode %MODE%
python autochip_adv_runner_v2.py --model gemma3:12b          --mode %MODE%
python autochip_adv_runner_v2.py --model qwen2.5-coder:14b   --mode %MODE%
python autochip_adv_runner_v2.py --model llama3.1            --mode %MODE%
python autochip_adv_runner_v2.py --model deepseek-coder:6.7b --mode %MODE%

echo.
echo ================================================================
echo  Done. Results in results_v2\
echo ================================================================
goto end

REM ── Single model ─────────────────────────────────────────────────
:run_single
echo.
echo Model: %MODEL%   Mode: %MODE%
echo.

if "%MODULE%"=="" (
    python autochip_adv_runner_v2.py --model %MODEL% --mode %MODE%
) else (
    python autochip_adv_runner_v2.py --model %MODEL% --mode %MODE% --module %MODULE%
)

:end
