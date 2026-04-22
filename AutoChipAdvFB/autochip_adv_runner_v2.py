"""
autochip_adv_runner_v2.py  —  AutoChip Advanced Feedback v2
Redesigned benchmark targeting LATCH INFERENCE as the primary failure mode.

5 Modules (3+1+1 design):
  LATCH TARGETS (Yosys feedback should break the loop):
    seg7_decoder        — case without default, inputs 10-15 expose latch
    alu_ops             — 3-bit opcode, 5/8 ops described, undefined hold stale result
    decoder_3to8        — if(enable) without else -> latch when enable=0

  VERILATOR TARGET (Verilator sensitivity warning should help):
    comb_sensitivity    — explicit sensitivity list, b/c likely missing

  CONTROL (pure FSM logic, neither tool helps):
    uart_rx             — timing-critical FSM, both conditions expected to fail

Usage:
    python autochip_adv_runner_v2.py --model gemma3:12b --mode both
    python autochip_adv_runner_v2.py --model gemma3:4b  --mode both
    python autochip_adv_runner_v2.py --model gemma3:12b --mode advanced --module seg7_decoder
"""

import os, subprocess, re, shutil, sys, json, time, argparse
from openai import OpenAI

# ── CONFIG ────────────────────────────────────────────────────────────────────
MAX_RETRIES     = 6
STUCK_THRESHOLD = 2
TESTBENCH_DIR   = "testbenches_v2"
RESULTS_DIR     = "results_v2"
WSL_PREFIX      = ["wsl"]

# ── API CLIENTS ───────────────────────────────────────────────────────────────
GEMINI_AVAILABLE = False
GEMINI_CLIENT    = None
try:
    from google import genai as google_genai
    from google.genai import types as genai_types
    GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
    if GEMINI_KEY:
        GEMINI_CLIENT    = google_genai.Client(api_key=GEMINI_KEY)
        GEMINI_AVAILABLE = True
except ImportError:
    pass

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_CLIENT  = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
OLLAMA_CLIENT  = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

GEMINI_MODEL_MAP = {
    "gemini-2.5-flash": "models/gemini-2.5-flash",
    "gemini-2.5-pro":   "models/gemini-2.5-pro",
    "gemini-2.0-flash": "models/gemini-2.0-flash-exp",
    "gemini-1.5-flash": "models/gemini-1.5-flash",
    "gemini-1.5-pro":   "models/gemini-1.5-pro",
}

# ── SYSTEM PROMPT ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a Verilog-2001 expert.

MANDATORY RULES — violating any of these causes synthesis or simulation failure:
1. 'wire' for signals driven by 'assign' or sub-module output ports.
   'reg' ONLY for signals assigned inside 'always' blocks.
2. Non-blocking (<=) in clocked always blocks. Blocking (=) in combinational.
3. EVERY combinational always block MUST have a 'default' branch in case statements
   AND an 'else' branch in if-else chains. Omitting these infers LATCHES which
   cause wrong simulation output and are a synthesis error.
4. Sensitivity list: use @(*) or list ALL signals read inside the block.
   A partial sensitivity list causes the block to silently not re-evaluate.
5. Use ONLY Verilog-2001 syntax. No SystemVerilog: no 'logic', no 'always_comb',
   no 'always_ff', no bit-width-free literals like '1 or '0.
   Write all literals with explicit width: 1'b0, 8'hFF, 2'b01.
6. Return ONLY Verilog code inside ```verilog ... ``` fences. No prose."""


# ── UTILITIES ─────────────────────────────────────────────────────────────────
def win_to_wsl(win_path):
    p = os.path.abspath(win_path).replace("\\", "/")
    if len(p) > 1 and p[1] == ":":
        p = f"/mnt/{p[0].lower()}" + p[2:]
    return p

def sanitize_ascii(text):
    return text.encode("ascii", errors="ignore").decode("ascii")

_PATH_RE = re.compile(
    r"(?:[A-Za-z]:[\\/]|[\\/])(?:[^\s:'\"/\\<>|*?\n]+[\\/])*([^\s:'\"/\\<>|*?\n]+\.v)"
)
def strip_paths(text):
    return _PATH_RE.sub(r"\1", text)


# ── LLM CALL ──────────────────────────────────────────────────────────────────
def call_llm(model, messages):
    if model.startswith("gemini"):
        if not GEMINI_AVAILABLE:
            print("ERROR: Set GEMINI_API_KEY and install google-genai"); sys.exit(1)
        api_model = GEMINI_MODEL_MAP.get(model, f"models/{model}")
        history = "\n".join(
            f"[{'USER' if m['role']=='user' else 'ASSISTANT'}]\n{m['content']}"
            for m in messages if m["role"] != "system"
        )
        resp = GEMINI_CLIENT.models.generate_content(
            model=api_model,
            config=genai_types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT, temperature=0.1),
            contents=history,
        )
        return resp.text
    elif model.startswith("gpt-") or model.startswith("o1") or model.startswith("o3"):
        if not OPENAI_CLIENT:
            print("ERROR: Set OPENAI_API_KEY"); sys.exit(1)
        resp = OPENAI_CLIENT.chat.completions.create(
            model=model, messages=messages, temperature=0.1)
        return resp.choices[0].message.content
    else:
        resp = OLLAMA_CLIENT.chat.completions.create(
            model=model, messages=messages, temperature=0.1)
        return resp.choices[0].message.content


# ── LAYER 1: VERILATOR LINT ───────────────────────────────────────────────────
# Suppressed noise flags:
#   DECLFILENAME  — filename doesn't match module name (harmless)
#   TIMESCALEMOD  — timescale defined in testbench only (harmless)
#   EOFNEWLINE    — "no newline at end of file" (LLM output artifact, irrelevant)
VERILATOR_SUPPRESS = [
    "-Wno-DECLFILENAME", "-Wno-TIMESCALEMOD", "-Wno-EOFNEWLINE",
]

def run_verilator_lint(v_file):
    """
    Returns (warnings_str, had_meaningful_warnings: bool).
    Filters out suppressed noise, keeps actionable structural warnings.
    """
    wsl_path = win_to_wsl(v_file)
    cmd = WSL_PREFIX + [
        "verilator", "--lint-only", "-Wall",
        "--bbox-unsup",
    ] + VERILATOR_SUPPRESS + [wsl_path]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    except subprocess.TimeoutExpired:
        return "[VERILATOR TIMEOUT]", True
    except FileNotFoundError:
        return "[WSL/VERILATOR NOT FOUND]", True

    output = result.stdout + result.stderr
    kept = []
    for line in output.splitlines():
        s = line.strip()
        if not s:
            continue
        if "... Use" in s or "... For warning" in s:
            continue  # suppress "how to suppress" boilerplate
        if s.startswith("%Warning") or s.startswith("%Error") or s.startswith("..."):
            kept.append(s)

    had_warnings = result.returncode != 0 and bool(kept)
    return ("\n".join(kept) if kept else "(no warnings)"), had_warnings


# ── LAYER 2: YOSYS SYNTHESIS CHECK ───────────────────────────────────────────
# These are the exact strings Yosys 0.33 emits when a latch is inferred
# from an incomplete case or missing else branch.
_LATCH_KEYWORDS = [
    "latch inferred", "inferred latch", "$dlatch",
    "generating latch", "latch for signal",
    "found latch", "warning: latch",
    "latch(es)",           # "Found 1 latch(es) in module"
    "has latches",
]

_YOSYS_KEEP = re.compile(
    r"(Warning|warning|Error|error|Latch|latch|inferred|"
    r"continuous assignment|Number of cells|Number of wires|"
    r"\$dlatch|\$dff|FAIL|stat)",
    re.IGNORECASE,
)

def run_yosys_check(v_file, module_name):
    """
    Returns (report_str, has_latches: bool).
    Uses generic 'synth' (no target library) to get latch vs FF inference info.
    """
    wsl_path = win_to_wsl(v_file)
    script = (
        f"read_verilog {wsl_path}; "
        f"synth -top {module_name}; "
        f"stat"
    )
    cmd = WSL_PREFIX + ["yosys", "-p", script]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
    except subprocess.TimeoutExpired:
        return "[YOSYS TIMEOUT]", False
    except FileNotFoundError:
        return "[WSL/YOSYS NOT FOUND]", False

    output = result.stdout + result.stderr
    has_latches = any(kw in output.lower() for kw in _LATCH_KEYWORDS)

    kept = [
        line.strip() for line in output.splitlines()
        if line.strip() and _YOSYS_KEEP.search(line)
    ]

    # Always include the cell count line for context
    for line in output.splitlines():
        if "Number of cells" in line and line.strip() not in kept:
            kept.append(line.strip())
            break

    # If latches detected, extract the specific signal names
    latch_lines = [l for l in kept if "latch" in l.lower() or "dlatch" in l.lower()]

    report = "\n".join(kept) if kept else "(no synthesis warnings)"
    return report, has_latches, latch_lines


# ── LAYER 3: IVERILOG + VVP ───────────────────────────────────────────────────
def run_iverilog_sim(iter_dir, module_name):
    """Compile + simulate all .v files in iter_dir via WSL."""
    log_file = os.path.join(iter_dir, "sim_log.txt")
    vvp_out  = os.path.join(iter_dir, "sim.vvp")

    v_files_wsl = [
        win_to_wsl(os.path.join(iter_dir, f))
        for f in sorted(os.listdir(iter_dir)) if f.endswith(".v")
    ]
    vvp_wsl = win_to_wsl(vvp_out)

    comp = subprocess.run(
        WSL_PREFIX + ["iverilog", "-o", vvp_wsl] + v_files_wsl,
        capture_output=True, text=True, encoding="utf-8"
    )

    with open(log_file, "w", encoding="utf-8") as f:
        f.write(f"--- COMPILATION ---\n{comp.stderr}\n")

    if comp.returncode != 0:
        err = strip_paths(comp.stderr)
        preview = "\n".join(err.strip().splitlines()[:10])
        print("  iverilog:\n    " + preview.replace("\n", "\n    "))
        return False, f"COMPILATION ERROR:\n{err}"

    sim = subprocess.run(
        WSL_PREFIX + ["vvp", vvp_wsl],
        capture_output=True, text=True, encoding="utf-8"
    )
    output = sim.stdout + sim.stderr

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n--- SIMULATION ---\n{output}\n")

    if "FAIL" in output or (
        "ALL TESTS PASSED" not in output and "PASS" not in output
    ):
        preview = "\n".join(output.strip().splitlines()[:8])
        print("  sim:\n    " + preview.replace("\n", "\n    "))
        return False, f"SIMULATION FAILED:\n{output}"

    return True, output


# ── ERROR CLASSIFIER ──────────────────────────────────────────────────────────
def classify_error(feedback):
    fb = feedback.lower()
    if "compilation error" in fb:
        if "not a valid l-value" in fb or "continuous" in fb:
            return "reg_wire_mismatch"
        if "already declared" in fb:    return "duplicate_module"
        if "unknown module" in fb:      return "missing_module"
        if "syntax error" in fb or "malformed" in fb: return "syntax_error"
        if "systemverilog" in fb:       return "systemverilog_syntax"
        if "is not a port" in fb:       return "port_mismatch"
        if "sorry:" in fb:              return "unsupported_construct"
        return "compile_other"
    if "simulation failed" in fb:
        return "logic_error" if "fail" in fb else "sim_other"
    return "sim_other"


# ── FEEDBACK BUILDERS ─────────────────────────────────────────────────────────
_BASE_HINTS = {
    "reg_wire_mismatch": (
        "\nHINT: A 'wire' is being driven inside an 'always' block (or a 'reg' used with assign). "
        "Use 'wire' for assign/submodule outputs; 'reg' for always-block signals only."
    ),
    "syntax_error": (
        "\nHINT: Verilog-2001 syntax error. Check: missing semicolons, mismatched begin/end, "
        "wrong case/endcase pairing. Do NOT use SystemVerilog syntax."
    ),
    "systemverilog_syntax": (
        "\nHINT: You used SystemVerilog syntax that iverilog rejects in Verilog-2001 mode. "
        "Common causes: using 'logic' instead of 'wire'/'reg', using '1 or '0 literals "
        "(write 1'b1 and 1'b0 instead), using 'always_comb' instead of 'always @(*)'."
    ),
    "logic_error": (
        "\nHINT: The module compiles but produces wrong output. "
        "Read each FAIL line — it shows exact inputs, expected output, and actual output. "
        "Trace your logic against those values step by step."
    ),
    "duplicate_module": (
        "\nHINT: You redefined a module already provided. "
        "Delete that definition and write only the requested top-level module."
    ),
    "port_mismatch": (
        "\nHINT: A port name doesn't match the testbench. "
        "Use the EXACT port names from the specification."
    ),
    "sim_other": (
        "\nHINT: Simulation produced no PASS/FAIL output. "
        "Ensure your module drives all output ports."
    ),
}

def build_baseline_feedback(iverilog_fb, err_type):
    """AutoChip baseline: single error block + type hint."""
    hint = _BASE_HINTS.get(err_type, "")
    return (
        "The Verilog code failed. Fix ALL errors and return the COMPLETE "
        "corrected module inside ```verilog ... ```. ASCII only.\n\n"
        f"Error output:\n{iverilog_fb}"
        f"{hint}"
    )

def build_advanced_feedback(verilator_out, yosys_report, latch_lines,
                             iverilog_fb, err_type, has_latches):
    """
    Three-layer structured feedback for LLM.
    Layer 1: Verilator pre-compile lint
    Layer 2: iverilog/vvp compile + simulation
    Layer 3: Yosys post-compile synthesis analysis
    """
    hint = _BASE_HINTS.get(err_type, "")

    # Build a targeted latch explanation if Yosys found one
    latch_warning = ""
    if has_latches:
        signal_list = ""
        if latch_lines:
            signal_list = "\n  Affected signals:\n" + "\n".join(
                f"    {l}" for l in latch_lines[:5]
            )
        latch_warning = (
            f"\n\n⚠  CRITICAL — YOSYS DETECTED INFERRED LATCHES:{signal_list}\n"
            "  Root cause: your combinational always block has a CASE or IF-ELSE\n"
            "  where at least one branch does NOT assign the output signal.\n"
            "  Fix: add 'default: <signal> = 0;' to every case statement,\n"
            "       AND add an 'else <signal> = 0;' to every if without an else.\n"
            "  A latch is NOT a register — it holds the last value when not enabled,\n"
            "  which is why the simulation shows wrong outputs for undefined inputs."
        )

    return (
        "The Verilog code failed. Analyze ALL three feedback layers carefully, "
        "then return the COMPLETE corrected module inside ```verilog ... ```.\n\n"

        "━━ [LAYER 1 — VERILATOR LINT] pre-compile structural analysis ━━━━━━━\n"
        "Verilator checks signal types, sensitivity lists, and wire/reg mismatches\n"
        "BEFORE compilation. Issues here will cause wrong simulation even if it compiles:\n"
        f"{verilator_out}\n\n"

        "━━ [LAYER 2 — IVERILOG / SIMULATION] compile + testbench result ━━━━━\n"
        f"{iverilog_fb}"
        f"{hint}\n\n"

        "━━ [LAYER 3 — YOSYS SYNTHESIS ANALYSIS] gate-level structure ━━━━━━━━\n"
        "Yosys maps your design to logic gates. This reveals whether registers,\n"
        "latches, or combinational logic was inferred — often exposing the ROOT CAUSE\n"
        "of simulation failures that iverilog cannot explain:\n"
        f"{yosys_report}"
        f"{latch_warning}"
    )

_REWRITE_PROMPT = (
    "Your previous {n} attempts all failed with '{err_type}'. "
    "DISCARD all prior code entirely.\n\n"
    "Write a brand-new Verilog-2001 module from scratch using only the original spec.\n"
    "Critical reminders:\n"
    "- Every case statement MUST have a 'default' branch\n"
    "- Every if without an else MUST have an else (assign 0 or a safe value)\n"
    "- Use @(*) for sensitivity lists in combinational always blocks\n"
    "- No SystemVerilog syntax (no 'logic', no '1 or '0 literals)\n\n"
    "ORIGINAL SPECIFICATION:\n{spec}\n\n"
    "Return ONLY the complete module inside ```verilog ... ```. ASCII only."
)


# ── MAIN LOOP ──────────────────────────────────────────────────────────────────
def autochip_loop(spec, module_name, model, use_adv_fb,
                  condition_tag, dependencies=None):
    if dependencies is None:
        dependencies = []

    tb_path = os.path.join(TESTBENCH_DIR, f"{module_name}_tb.v")
    if not os.path.exists(tb_path):
        print(f"  ERROR: Missing testbench: {tb_path}")
        return None

    safe_model  = model.replace(":", "_").replace(".", "")
    project_dir = os.path.join(RESULTS_DIR, safe_model, condition_tag, module_name)
    os.makedirs(project_dir, exist_ok=True)

    fb_label = ("ADVANCED (Verilator+Yosys+iverilog)"
                 if use_adv_fb else "BASELINE (iverilog only)")
    print(f"\n{'='*65}")
    print(f"  {module_name}  |  {model}  |  {fb_label}")
    print(f"{'='*65}")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": spec},
    ]

    metrics = {
        "module":             module_name,
        "model":              model,
        "condition":          condition_tag,
        "pass_at_1":          False,
        "iterations_to_pass": None,
        "time_to_pass_sec":   None,
        "total_time_sec":     None,
        "total_iterations":   MAX_RETRIES,
        "compile_errors":     0,
        "sim_errors":         0,
        "latch_warnings":     0,
        "verilator_catches":  0,
        "error_types":        [],
        "per_iter_detail":    [],
    }

    t_start = time.time()
    consecutive_same = 0
    last_err_type    = None

    for i in range(MAX_RETRIES):
        iter_dir = os.path.join(project_dir, f"iter_{i+1}")
        os.makedirs(iter_dir, exist_ok=True)
        print(f"\n  Iteration {i+1}/{MAX_RETRIES}")

        # ── LLM call ──────────────────────────────────────────────────────
        t_llm = time.time()
        try:
            llm_out = call_llm(model, messages)
        except Exception as e:
            print(f"  LLM Error: {e}")
            break
        print(f"  LLM responded in {time.time()-t_llm:.1f}s")

        with open(os.path.join(iter_dir, "llm_response.txt"), "w", encoding="utf-8") as f:
            f.write(llm_out)

        match = re.search(r"```(?:verilog)?(.*?)```", llm_out, re.DOTALL)
        code  = match.group(1).strip() if match else llm_out.strip()
        code  = sanitize_ascii(code)

        v_path = os.path.join(iter_dir, f"{module_name}.v")
        with open(v_path, "w", encoding="utf-8") as f:
            f.write(code)

        for dep in dependencies:
            if os.path.exists(dep):
                shutil.copy(dep, iter_dir)
        shutil.copy(tb_path, iter_dir)

        # ── Layer 1: Verilator ─────────────────────────────────────────────
        verilator_out  = "(verilator skipped in baseline)"
        verilator_flag = False
        if use_adv_fb:
            verilator_out, verilator_flag = run_verilator_lint(v_path)
            if verilator_flag:
                print(f"  Verilator ⚠: {verilator_out.splitlines()[0][:80]}")
                metrics["verilator_catches"] += 1
            else:
                print(f"  Verilator: clean")

        # ── Layer 2: iverilog + vvp ────────────────────────────────────────
        success, iverilog_fb = run_iverilog_sim(iter_dir, module_name)
        elapsed = time.time() - t_start

        # ── Layer 3: Yosys (advanced, when compile succeeds) ───────────────
        yosys_report = "(yosys skipped in baseline)"
        has_latches  = False
        latch_lines  = []
        if use_adv_fb and "COMPILATION ERROR" not in iverilog_fb:
            yosys_report, has_latches, latch_lines = run_yosys_check(
                v_path, module_name)
            if has_latches:
                print(f"  Yosys ⚠ LATCH INFERRED: {latch_lines[0][:60] if latch_lines else ''}")
                metrics["latch_warnings"] += 1
            else:
                print(f"  Yosys: no latches")

        # ── Record per-iteration detail ────────────────────────────────────
        iter_detail = {
            "iter":              i + 1,
            "verilator_warning": verilator_flag,
            "yosys_latch":       has_latches,
            "iverilog_result":   "PASS" if success else "FAIL",
            "err_type":          "PASS" if success else None,
        }

        if success:
            print(f"  PASSED on iteration {i+1}  ({elapsed:.1f}s)")
            iter_detail["err_type"] = "PASS"
            metrics["per_iter_detail"].append(iter_detail)
            metrics.update({
                "pass_at_1":          True,
                "iterations_to_pass": i + 1,
                "time_to_pass_sec":   round(elapsed, 2),
                "total_time_sec":     round(elapsed, 2),
                "total_iterations":   i + 1,
            })
            break

        # ── Error handling ─────────────────────────────────────────────────
        err_type = classify_error(iverilog_fb)
        iter_detail["err_type"] = err_type
        metrics["per_iter_detail"].append(iter_detail)

        if "COMPILATION" in iverilog_fb:
            metrics["compile_errors"] += 1
        else:
            metrics["sim_errors"] += 1
        metrics["error_types"].append(err_type)
        print(f"  FAIL: {err_type}")

        if err_type == last_err_type:
            consecutive_same += 1
        else:
            consecutive_same = 1
            last_err_type    = err_type

        messages.append({"role": "assistant", "content": llm_out})

        if consecutive_same >= STUCK_THRESHOLD:
            print(f"  STUCK on '{err_type}' x{consecutive_same} — injecting rewrite")
            messages.append({"role": "user", "content": _REWRITE_PROMPT.format(
                n=consecutive_same, err_type=err_type, spec=spec)})
            consecutive_same = 0
        else:
            if use_adv_fb:
                fb = build_advanced_feedback(
                    verilator_out, yosys_report, latch_lines,
                    iverilog_fb, err_type, has_latches)
            else:
                fb = build_baseline_feedback(iverilog_fb, err_type)
            messages.append({"role": "user", "content": fb})

    if metrics["total_time_sec"] is None:
        metrics["total_time_sec"] = round(time.time() - t_start, 2)

    with open(os.path.join(project_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    if not metrics["pass_at_1"]:
        print(f"  FAILED after {MAX_RETRIES} iterations  ({metrics['total_time_sec']:.1f}s)")

    return metrics


# ── BENCHMARK DEFINITIONS ─────────────────────────────────────────────────────
# Each spec is written to mimic a real benchmark description.
# The latch-target specs deliberately omit 'default' guidance and
# use language that leads LLMs to write incomplete case/if-else.
# This is the controlled variable — the spec IS the failure trigger.
BENCHMARK = {

    # ── LATCH TARGET 1 ────────────────────────────────────────────────────────
    "seg7_decoder": {
        "category": "latch_target",
        "spec": (
            "Create a Verilog-2001 module named 'seg7_decoder'.\n"
            "Ports: input [3:0] bcd; output reg [6:0] seg\n"
            "Implement a combinational 7-segment display decoder.\n"
            "Segment bit ordering: seg[6:0] = {g, f, e, d, c, b, a} (1 = segment ON)\n"
            "Use a case statement in a combinational always block.\n"
            "Encodings for BCD digits 0 through 9:\n"
            "  0: 7'b0111111    1: 7'b0000110    2: 7'b1011011\n"
            "  3: 7'b1001111    4: 7'b1100110    5: 7'b1101101\n"
            "  6: 7'b1111101    7: 7'b0000111    8: 7'b1111111\n"
            "  9: 7'b1101111\n"
            "The valid input range is 0-9. Behavior for inputs 10-15 is not\n"
            "specified by the application — implement only the 10 defined cases.\n"
            # ^ This is the deliberate trap: LLM omits default,
            #   Yosys infers latch, inputs 10-15 hold stale value.
        ),
    },

    # ── LATCH TARGET 2 ────────────────────────────────────────────────────────
    "alu_ops": {
        "category": "latch_target",
        "spec": (
            "Create a Verilog-2001 module named 'alu_ops'.\n"
            "Ports: input [7:0] a, b; input [2:0] opcode;\n"
            "       output reg [7:0] result; output reg carry_out, zero\n"
            "Implement a combinational ALU with these operations:\n"
            "  3'b000 (ADD): result = a + b, carry_out = carry from addition\n"
            "  3'b001 (SUB): result = a - b, carry_out = 1 if borrow (a < b)\n"
            "  3'b010 (AND): result = a & b, carry_out = 0\n"
            "  3'b011 (OR) : result = a | b, carry_out = 0\n"
            "  3'b100 (XOR): result = a ^ b, carry_out = 0\n"
            "zero flag: zero = 1 when result == 0, else 0.\n"
            "Use a case statement on opcode in a combinational always block.\n"
            "Implement only the five operations listed above.\n"
            # ^ Trap: 3-bit opcode has 8 values, only 5 described.
            #   LLM skips default -> latch on result, carry_out, zero.
            #   Opcodes 101,110,111 hold last computed value instead of 0.
        ),
    },

    # ── LATCH TARGET 3 ────────────────────────────────────────────────────────
    "decoder_3to8": {
        "category": "latch_target",
        "spec": (
            "Create a Verilog-2001 module named 'decoder_3to8'.\n"
            "Ports: input enable; input [2:0] in; output reg [7:0] out\n"
            "Implement a 3-to-8 one-hot decoder with an active-high enable.\n"
            "When enable is asserted, use a case statement to drive the\n"
            "corresponding output bit high and all others low:\n"
            "  in=3'd0 -> out=8'b0000_0001\n"
            "  in=3'd1 -> out=8'b0000_0010\n"
            "  in=3'd2 -> out=8'b0000_0100\n"
            "  in=3'd3 -> out=8'b0000_1000\n"
            "  in=3'd4 -> out=8'b0001_0000\n"
            "  in=3'd5 -> out=8'b0010_0000\n"
            "  in=3'd6 -> out=8'b0100_0000\n"
            "  in=3'd7 -> out=8'b1000_0000\n"
            "All logic is combinational — no clock, no reset.\n"
            # ^ Trap: spec says "when enable is asserted", so LLMs write
            #   if (enable) begin case ... end  <- missing else out = 0
            #   Yosys: "Inferred latch for signal \out"
            #   When enable=0, out holds last value instead of 0.
        ),
    },

    # ── VERILATOR TARGET ──────────────────────────────────────────────────────
    "comb_sensitivity": {
        "category": "verilator_target",
        "spec": (
            "Create a Verilog-2001 module named 'comb_sensitivity'.\n"
            "Ports: input a, b, c, sel; output reg out\n"
            "Implement a combinational function:\n"
            "  When sel=0: out = a AND b\n"
            "  When sel=1: out = b OR c\n"
            "Implement using an always block with an explicit sensitivity list.\n"
            "Do NOT use the @(*) wildcard — write the sensitivity list manually.\n"
            "List only the signals that are the primary control inputs.\n"
            # ^ Trap: "primary control inputs" nudges toward @(a, sel) or @(sel)
            #   missing b and c. Verilator: %Warning-UNOPTFLAT or sensitivity warning.
            #   iverilog simulates wrong (b/c changes don't trigger re-evaluation).
        ),
    },

    # ── CONTROL (both conditions expected to fail) ────────────────────────────
    "uart_rx": {
        "category": "control",
        "spec": (
            "Create a Verilog-2001 module named 'uart_rx'.\n"
            "Parameter: CLKS_PER_BIT = 4  (clock cycles per UART bit period)\n"
            "Ports: input clk, rst, rx; output reg [7:0] rx_data; output reg data_valid\n"
            "Implement an 8-N-1 UART receiver (8 data bits, no parity, 1 stop bit).\n"
            "Protocol: idle line is high. A byte begins with a start bit (low),\n"
            "followed by 8 data bits LSB first, followed by a stop bit (high).\n"
            "Sample each bit at the MIDDLE of its bit period (after CLKS_PER_BIT/2 clocks).\n"
            "data_valid must pulse HIGH for exactly 1 clock cycle when a complete\n"
            "byte is received and validated (stop bit confirmed high).\n"
            "Use synchronous active-high reset. FSM states are your design choice.\n"
            "Ignore framing errors — only assert data_valid on valid frames.\n"
        ),
    },
}


# ── COMPARISON TABLE ──────────────────────────────────────────────────────────
def print_comparison(baseline_list, advanced_list, model):
    W = 78
    print(f"\n{'='*W}")
    print(f"  COMPARISON  |  Model: {model}")
    print(f"{'='*W}")
    print(f"  {'Module':<22} {'Cat':<10} {'Baseline':^18} {'Advanced':^18} {'Δ iters':>7}")
    print(f"  {'':22} {'':10} {'Pass | Iters':^18} {'Pass | Iters':^18}")
    print(f"  {'-'*76}")

    base_map = {m["module"]: m for m in baseline_list}
    adv_map  = {m["module"]: m for m in advanced_list}

    total_bi = 0; total_ai = 0
    base_pass = 0; adv_pass = 0

    for mod, cfg in BENCHMARK.items():
        bm = base_map.get(mod)
        am = adv_map.get(mod)
        if not bm or not am:
            continue
        bp    = "PASS" if bm["pass_at_1"] else "FAIL"
        ap    = "PASS" if am["pass_at_1"] else "FAIL"
        bi    = bm["iterations_to_pass"] or MAX_RETRIES
        ai    = am["iterations_to_pass"] or MAX_RETRIES
        delta = bi - ai
        cat   = cfg["category"].replace("_", " ")
        total_bi += bi; total_ai += ai
        if bm["pass_at_1"]: base_pass += 1
        if am["pass_at_1"]: adv_pass  += 1
        ds = f"+{delta}" if delta > 0 else str(delta)
        print(f"  {mod:<22} {cat:<10} {bp+' | '+str(bi):^18} {ap+' | '+str(ai):^18} {ds:>7}")

    n = len(BENCHMARK)
    print(f"\n  {'Pass rate':<32} {base_pass}/{n:^18} {adv_pass}/{n:^18}")
    print(f"  {'Total iterations':<32} {total_bi:^18} {total_ai:^18} {total_bi-total_ai:>7}")

    vl_total = sum(m.get("verilator_catches", 0) for m in advanced_list)
    lt_total = sum(m.get("latch_warnings",    0) for m in advanced_list)
    print(f"\n  Advanced diagnostics across all modules:")
    print(f"    Verilator catches (iter with warnings)  : {vl_total}")
    print(f"    Yosys latch detections (iter with latch): {lt_total}")
    print(f"{'='*W}\n")


# ── CLI ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AutoChip Advanced Feedback v2 — Latch Inference Benchmark",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--model",  default="gemma3:12b")
    parser.add_argument("--mode",   default="both",
                        choices=["baseline", "advanced", "both"])
    parser.add_argument("--module", default=None,
                        help="Single module name (default: all 5)")
    args = parser.parse_args()

    items = list(BENCHMARK.items())
    if args.module:
        items = [(k, v) for k, v in items if k == args.module]
        if not items:
            print(f"ERROR: '{args.module}' not in benchmark. "
                  f"Choices: {list(BENCHMARK.keys())}")
            sys.exit(1)

    baseline_results = []
    advanced_results = []
    run_base = args.mode in ("baseline", "both")
    run_adv  = args.mode in ("advanced", "both")

    if run_base:
        print(f"\n{'#'*65}")
        print(f"  CONDITION A: BASELINE (iverilog+vvp feedback only)")
        print(f"{'#'*65}")
        for mod, cfg in items:
            m = autochip_loop(
                spec=cfg["spec"], module_name=mod, model=args.model,
                use_adv_fb=False, condition_tag="baseline")
            if m: baseline_results.append(m)

    if run_adv:
        print(f"\n{'#'*65}")
        print(f"  CONDITION B: ADVANCED (Verilator + iverilog + Yosys)")
        print(f"{'#'*65}")
        for mod, cfg in items:
            m = autochip_loop(
                spec=cfg["spec"], module_name=mod, model=args.model,
                use_adv_fb=True, condition_tag="advanced")
            if m: advanced_results.append(m)

    # Save summary
    safe_model   = args.model.replace(":", "_").replace(".", "")
    summary_dir  = os.path.join(RESULTS_DIR, safe_model)
    os.makedirs(summary_dir, exist_ok=True)
    summary_path = os.path.join(summary_dir, "adv_summary_v2.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({"model": args.model, "mode": args.mode,
                   "baseline": baseline_results,
                   "advanced": advanced_results}, f, indent=2)

    if run_base and run_adv:
        print_comparison(baseline_results, advanced_results, args.model)

    print(f"  Results saved -> {summary_path}\n")
