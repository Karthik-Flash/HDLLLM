"""
autochip_adv_runner.py  —  AutoChip Advanced Feedback Edition
Adds Verilator lint + Yosys synthesis as enriched feedback layers on top
of the baseline iverilog+vvp loop.  Runs a controlled comparison:
  baseline  = iverilog/vvp feedback only  (replicates AutoChip paper)
  advanced  = Verilator lint -> iverilog/vvp -> Yosys synthesis check

Usage (from Windows CMD with conda env active):
    python autochip_adv_runner.py --model gemini-2.5-flash --mode both
    python autochip_adv_runner.py --model gemini-2.5-flash --mode baseline
    python autochip_adv_runner.py --model gemini-2.5-flash --mode advanced
    python autochip_adv_runner.py --model gemini-2.5-flash --mode both --module d_latch_gated

All EDA tools (verilator, yosys, iverilog) are called via WSL.
"""

import os, subprocess, re, shutil, sys, json, time, argparse
from openai import OpenAI

# ── CONFIG ────────────────────────────────────────────────────────────────────
MAX_RETRIES     = 6       # enough iterations to show convergence difference
STUCK_THRESHOLD = 2       # rewrite prompt after N consecutive identical errors
TESTBENCH_DIR   = "testbenches"
RESULTS_DIR     = "results"
WSL_PREFIX      = ["wsl"]  # prefix for all EDA tool calls from Windows

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

SYSTEM_PROMPT = """You are a Verilog-2001 Expert.
STRICT RULES:
1. Outputs driven by 'assign' MUST be declared as 'wire'.
2. ONLY use 'reg' for signals assigned inside an 'always' block.
3. Use non-blocking assignments (<=) in clocked always blocks.
4. Use blocking assignments (=) in combinational always blocks.
5. Every combinational always block MUST have a 'default' case or cover all branches.
   Missing branches infer latches — a common synthesis error.
6. Level-sensitive latches use: always @(en or d) — NOT always @(posedge clk).
7. Return ONLY Verilog inside ```verilog ... ``` fences. No prose, no explanations."""


# ── PATH HELPERS ──────────────────────────────────────────────────────────────
def win_to_wsl(win_path):
    """Convert a Windows absolute path to its WSL /mnt/x/... equivalent."""
    p = os.path.abspath(win_path).replace("\\", "/")
    if len(p) > 1 and p[1] == ":":
        drive = p[0].lower()
        p = f"/mnt/{drive}" + p[2:]
    return p


def sanitize_ascii(text):
    return text.encode("ascii", errors="ignore").decode("ascii")


_PATH_RE = re.compile(
    r"(?:[A-Za-z]:[\\/]|[\\/])(?:[^\s:'\"/\\<>|*?\n]+[\\/])*([^\s:'\"/\\<>|*?\n]+\.v)",
    re.VERBOSE,
)

def strip_paths(text):
    return _PATH_RE.sub(r"\1", text)


# ── LLM CALL ──────────────────────────────────────────────────────────────────
def call_llm(model, messages):
    if model.startswith("gemini"):
        if not GEMINI_AVAILABLE:
            print("ERROR: Set GEMINI_API_KEY and install google-genai")
            sys.exit(1)
        api_model = GEMINI_MODEL_MAP.get(model, f"models/{model}")
        history = "\n".join(
            f"[{'USER' if m['role']=='user' else 'ASSISTANT'}]\n{m['content']}"
            for m in messages if m["role"] != "system"
        )
        resp = GEMINI_CLIENT.models.generate_content(
            model=api_model,
            config=genai_types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT, temperature=0.1
            ),
            contents=history,
        )
        return resp.text
    elif model.startswith("gpt-") or model.startswith("o1") or model.startswith("o3"):
        if not OPENAI_CLIENT:
            print("ERROR: Set OPENAI_API_KEY for OpenAI models")
            sys.exit(1)
        resp = OPENAI_CLIENT.chat.completions.create(
            model=model, messages=messages, temperature=0.1
        )
        return resp.choices[0].message.content
    else:
        resp = OLLAMA_CLIENT.chat.completions.create(
            model=model, messages=messages, temperature=0.1
        )
        return resp.choices[0].message.content


# ── LAYER 1: VERILATOR LINT ───────────────────────────────────────────────────
def run_verilator_lint(v_file):
    """
    Run Verilator lint-only pass via WSL.
    Returns (warnings_str, had_errors: bool).
    Key flags:
      -Wno-DECLFILENAME  suppress filename!=module noise
      -Wno-TIMESCALEMOD  suppress timescale warnings from testbench files
    """
    wsl_path = win_to_wsl(v_file)
    cmd = WSL_PREFIX + [
        "verilator", "--lint-only", "-Wall",
        "-Wno-DECLFILENAME",
        "-Wno-TIMESCALEMOD",
        "--bbox-unsup",   # allow unsupported constructs without crashing
        wsl_path,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=20
        )
    except subprocess.TimeoutExpired:
        return "[VERILATOR TIMEOUT]", True
    except FileNotFoundError:
        return "[VERILATOR NOT FOUND — is WSL installed?]", True

    output = result.stdout + result.stderr
    # Filter to meaningful lines only
    kept = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        # Keep warnings and errors; skip pure path/location noise lines
        if line.startswith("%Warning") or line.startswith("%Error"):
            kept.append(line)
        elif "... Use" in line or "... For warning" in line:
            continue  # skip "how to suppress" hints — saves tokens
        elif line.startswith("..."):
            kept.append(line)  # keep source-location context

    had_errors = result.returncode != 0
    return "\n".join(kept) if kept else "(no warnings)", had_errors


# ── LAYER 2: YOSYS SYNTHESIS CHECK ───────────────────────────────────────────
_YOSYS_KEEP = re.compile(
    r"(Warning|Error|error|Latch|inferred|latches|continuous assignment|"
    r"Number of cells|Number of wires|FAIL|$dff|$dlatch)",
    re.IGNORECASE,
)

def run_yosys_check(v_file, module_name):
    """
    Run Yosys generic synthesis via WSL to catch latches and structural issues.
    Returns (report_str, has_latches: bool).
    """
    wsl_path = win_to_wsl(v_file)
    # synth without a target library — just checks structure
    script = (
        f"read_verilog {wsl_path}; "
        f"synth -top {module_name} -flatten; "
        f"stat"
    )
    cmd = WSL_PREFIX + ["yosys", "-p", script]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )
    except subprocess.TimeoutExpired:
        return "[YOSYS TIMEOUT]", False
    except FileNotFoundError:
        return "[YOSYS NOT FOUND — is WSL installed?]", False

    output = result.stdout + result.stderr
    kept = [
        line.strip() for line in output.splitlines()
        if line.strip() and _YOSYS_KEEP.search(line)
    ]
    has_latches = any(
        kw in output.lower()
        for kw in ["latch inferred", "inferred latch", "$dlatch", "latches"]
    )
    # Always include Number of cells line for context
    cells_line = next(
        (l.strip() for l in output.splitlines() if "Number of cells" in l), ""
    )
    if cells_line and cells_line not in kept:
        kept.append(cells_line)

    report = "\n".join(kept) if kept else "(no synthesis warnings)"
    return report, has_latches


# ── LAYER 3: IVERILOG + VVP ───────────────────────────────────────────────────
def run_iverilog_sim(iter_dir, module_name):
    """
    Compile all .v files in iter_dir with iverilog (via WSL), simulate with vvp.
    Returns (success: bool, feedback: str).
    """
    log_file = os.path.join(iter_dir, "sim_log.txt")
    vvp_out  = os.path.join(iter_dir, "sim.vvp")

    # Build WSL paths for all .v files
    v_files_win = sorted(
        os.path.join(iter_dir, f)
        for f in os.listdir(iter_dir) if f.endswith(".v")
    )
    v_files_wsl = [win_to_wsl(f) for f in v_files_win]
    vvp_wsl     = win_to_wsl(vvp_out)

    comp_cmd = WSL_PREFIX + ["iverilog", "-o", vvp_wsl] + v_files_wsl
    comp_res = subprocess.run(comp_cmd, capture_output=True, text=True, encoding="utf-8")

    with open(log_file, "w", encoding="utf-8") as f:
        f.write(f"--- COMPILATION ---\n{comp_res.stderr}\n")

    if comp_res.returncode != 0:
        err_clean   = strip_paths(comp_res.stderr)
        err_preview = "\n".join(err_clean.strip().splitlines()[:10])
        print("  iverilog:\n    " + err_preview.replace("\n", "\n    "))
        return False, f"COMPILATION ERROR:\n{err_clean}"

    sim_res = subprocess.run(
        WSL_PREFIX + ["vvp", vvp_wsl],
        capture_output=True, text=True, encoding="utf-8"
    )
    output = sim_res.stdout + sim_res.stderr

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n--- SIMULATION ---\n{output}\n")

    if "FAIL" in output or (
        "ALL TESTS PASSED" not in output and "PASS" not in output
    ):
        sim_preview = "\n".join(output.strip().splitlines()[:8])
        print("  sim:\n    " + sim_preview.replace("\n", "\n    "))
        return False, f"SIMULATION FAILED:\n{output}"

    return True, output


# ── ERROR CLASSIFIER ──────────────────────────────────────────────────────────
def classify_error(feedback):
    fb = feedback.lower()
    if "compilation error" in fb:
        if "not a valid l-value" in fb or "continuous" in fb:
            return "reg_wire_mismatch"
        if "already declared" in fb:
            return "duplicate_module"
        if "unknown module" in fb:
            return "missing_module"
        if "syntax error" in fb or "malformed" in fb:
            return "syntax_error"
        if "is not a port" in fb or "unable to bind" in fb:
            return "port_mismatch"
        if "sorry:" in fb or "not currently supported" in fb:
            return "unsupported_construct"
        return "compile_other"
    if "simulation failed" in fb:
        return "logic_error" if "fail" in fb else "sim_other"
    return "sim_other"


# ── FEEDBACK BUILDERS ─────────────────────────────────────────────────────────
_BASE_HINTS = {
    "reg_wire_mismatch": (
        "\nHINT: A signal declared as 'wire' is driven inside an 'always' block "
        "(or a 'reg' is used with 'assign'). "
        "Rule: use 'wire' for assign/submodule outputs; 'reg' for always-block signals."
    ),
    "duplicate_module": (
        "\nHINT: You redefined a module that is already provided as a dependency. "
        "Delete that definition — only write the top-level module requested."
    ),
    "missing_module": (
        "\nHINT: An instantiated module cannot be found. "
        "Use the EXACT module name from the spec — check case and spelling."
    ),
    "syntax_error": (
        "\nHINT: Verilog-2001 syntax error. Common causes: missing semicolons, "
        "mismatched begin/end, using SystemVerilog keywords (logic, always_comb)."
    ),
    "logic_error": (
        "\nHINT: Module compiles but output is wrong. "
        "Read each FAIL line — it shows exact inputs, expected vs actual outputs. "
        "Trace your logic against those values."
    ),
    "sim_other": (
        "\nHINT: Simulation produced no PASS/FAIL output. "
        "Ensure your module drives all outputs."
    ),
}

def build_baseline_feedback(feedback, err_type):
    """AutoChip-style: single error block + type hint."""
    hint = _BASE_HINTS.get(err_type, "")
    return (
        "The Verilog code failed. Fix ALL errors and return the COMPLETE "
        "corrected module inside a single ```verilog ... ``` block. "
        "ASCII only, no prose outside the fence.\n\n"
        f"Error output:\n{feedback}"
        f"{hint}"
    )

def build_advanced_feedback(verilator_out, yosys_report, iverilog_feedback,
                             err_type, has_latches):
    """
    Three-layer structured feedback:
      [LAYER 1] Verilator — pre-compile structural lint
      [LAYER 2] iverilog/vvp — compile + simulation
      [LAYER 3] Yosys — post-compile synthesis analysis
    """
    hint = _BASE_HINTS.get(err_type, "")

    latch_warning = ""
    if has_latches:
        latch_warning = (
            "\n⚠  SYNTHESIS WARNING: Yosys detected INFERRED LATCHES. "
            "This means your combinational always block has an incomplete case "
            "or missing else — add a 'default' case or ensure all branches "
            "assign every signal. Latches cause unpredictable hardware behaviour."
        )

    return (
        "The Verilog code failed. Analyze ALL three feedback layers below, "
        "then return the COMPLETE corrected module inside ```verilog ... ```.\n\n"

        "━━ [LAYER 1 — VERILATOR LINT] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Verilator performs pre-compile structural analysis. "
        "These warnings indicate signal declaration or sensitivity list issues "
        "that will cause incorrect synthesis even if iverilog compiles:\n"
        f"{verilator_out}\n\n"

        "━━ [LAYER 2 — IVERILOG / SIMULATION] ━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{iverilog_feedback}"
        f"{hint}\n\n"

        "━━ [LAYER 3 — YOSYS SYNTHESIS ANALYSIS] ━━━━━━━━━━━━━━━━━━━━━\n"
        "Yosys synthesizes your design to gate level. "
        "This reveals latches, incorrect inferences, and structural problems "
        "not visible at the simulation level:\n"
        f"{yosys_report}"
        f"{latch_warning}"
    )


_REWRITE_PROMPT = (
    "Your previous {n} attempts all failed with error type '{err_type}'. "
    "DISCARD your previous implementation entirely.\n\n"
    "Write a BRAND-NEW Verilog-2001 module from scratch using only the "
    "original specification. Do not reuse any prior code.\n\n"
    "ORIGINAL SPECIFICATION:\n{spec}\n\n"
    "Return ONLY the complete module inside ```verilog ... ```. ASCII only."
)


# ── MAIN LOOP ──────────────────────────────────────────────────────────────────
def autochip_loop(spec, module_name, model, use_adv_fb,
                  condition_tag, dependencies=None):
    """
    Run one condition (baseline or advanced) for one module.
    Returns metrics dict.

    condition_tag: 'baseline' or 'advanced' — used for result folder naming.
    """
    if dependencies is None:
        dependencies = []

    tb_path = os.path.join(TESTBENCH_DIR, f"{module_name}_tb.v")
    if not os.path.exists(tb_path):
        print(f"  ERROR: Missing testbench: {tb_path}")
        return None

    safe_model   = model.replace(":", "_").replace(".", "")
    project_dir  = os.path.join(RESULTS_DIR, safe_model,
                                 condition_tag, module_name)
    os.makedirs(project_dir, exist_ok=True)

    fb_label = "ADVANCED (Verilator+Yosys+iverilog)" if use_adv_fb else "BASELINE (iverilog only)"
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
        "verilator_catches":  0,   # iterations where Verilator found something
        "error_types":        [],
        "per_iter_detail":    [],  # for paper: error source per iteration
    }

    t_start          = time.time()
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

        # Save raw response
        with open(os.path.join(iter_dir, "llm_response.txt"),
                  "w", encoding="utf-8") as f:
            f.write(llm_out)

        # Extract Verilog
        match = re.search(r"```(?:verilog)?(.*?)```", llm_out, re.DOTALL)
        code  = match.group(1).strip() if match else llm_out.strip()
        code  = sanitize_ascii(code)

        v_path = os.path.join(iter_dir, f"{module_name}.v")
        with open(v_path, "w", encoding="utf-8") as f:
            f.write(code)

        # Copy deps + testbench
        for dep in dependencies:
            if os.path.exists(dep):
                shutil.copy(dep, iter_dir)
        shutil.copy(tb_path, iter_dir)

        # ── Layer 1: Verilator lint (advanced mode only) ───────────────────
        verilator_out  = "(verilator not run in baseline mode)"
        verilator_flag = False
        if use_adv_fb:
            verilator_out, verilator_flag = run_verilator_lint(v_path)
            if verilator_out != "(no warnings)":
                print(f"  Verilator: {verilator_out.splitlines()[0][:80]}")
                metrics["verilator_catches"] += 1

        # ── Layer 2: iverilog + vvp ────────────────────────────────────────
        success, iverilog_fb = run_iverilog_sim(iter_dir, module_name)
        elapsed = time.time() - t_start

        # ── Layer 3: Yosys synthesis (advanced, on compile success) ───────
        yosys_report = "(yosys not run in baseline mode)"
        has_latches  = False
        if use_adv_fb and "COMPILATION ERROR" not in iverilog_fb:
            yosys_report, has_latches = run_yosys_check(v_path, module_name)
            if has_latches:
                print("  Yosys: ⚠ LATCH INFERRED")
                metrics["latch_warnings"] += 1

        # ── Record per-iteration detail ────────────────────────────────────
        iter_detail = {
            "iter":            i + 1,
            "verilator_clean": not verilator_flag,
            "iverilog_result": "PASS" if success else "FAIL",
            "yosys_latch":     has_latches,
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

        # Stuck-loop detection
        if err_type == last_err_type:
            consecutive_same += 1
        else:
            consecutive_same = 1
            last_err_type    = err_type

        messages.append({"role": "assistant", "content": llm_out})

        if consecutive_same >= STUCK_THRESHOLD:
            print(f"  STUCK on '{err_type}' x{consecutive_same} — injecting rewrite")
            messages.append({
                "role": "user",
                "content": _REWRITE_PROMPT.format(
                    n=consecutive_same, err_type=err_type, spec=spec
                ),
            })
            consecutive_same = 0
        else:
            # Build feedback based on mode
            if use_adv_fb:
                fb_msg = build_advanced_feedback(
                    verilator_out, yosys_report, iverilog_fb,
                    err_type, has_latches
                )
            else:
                fb_msg = build_baseline_feedback(iverilog_fb, err_type)

            messages.append({"role": "user", "content": fb_msg})

    # Guarantee total_time_sec is always set
    if metrics["total_time_sec"] is None:
        metrics["total_time_sec"] = round(time.time() - t_start, 2)

    metrics_path = os.path.join(project_dir, "metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    if not metrics["pass_at_1"]:
        print(f"  FAILED after {MAX_RETRIES} iterations"
              f"  ({metrics['total_time_sec']:.1f}s)")

    return metrics


# ── BENCHMARK DEFINITIONS ─────────────────────────────────────────────────────
# Each spec is written to be realistic but subtly incomplete,
# matching how conference specs are typically given.
# Intentional LLM failure vectors are noted in comments.
BENCHMARK = {

    "seq_detector_101": {
        "spec": (
            "Create a Verilog-2001 module named 'seq_detector_101'.\n"
            "Ports: input clk, rst, in; output reg detected\n"
            "Implement a synchronous Moore FSM that detects the overlapping\n"
            "sequence '101' in a serial bitstream on input 'in'.\n"
            "- Synchronous active-high reset (rst) returns to the initial state.\n"
            "- 'detected' is 1 only during the clock cycle AFTER the final '1'\n"
            "  of a valid '101' sequence is received.\n"
            "- Overlapping sequences must be supported: after detecting '101',\n"
            "  the FSM should correctly handle the case where the last '1'\n"
            "  can be the start of the next '10...' pattern.\n"
            "- Use a 2-bit state register with synchronous next-state logic.\n"
            "- IMPORTANT: All branches of every case statement must be covered.\n"
            "  A missing 'default' in a combinational always block will cause\n"
            "  latch inference in synthesis.\n"
        ),
        # LLM failure vectors:
        #  1. Incomplete case -> Yosys: latch inferred on next_state
        #  2. Wrong overlap transitions (S3->S0 instead of S3->S1/S2)
        #  3. Mixing up Moore (output = f(state)) with Mealy (output = f(state,in))
    },

    "up_down_counter_4bit": {
        "spec": (
            "Create a Verilog-2001 module named 'up_down_counter_4bit'.\n"
            "Ports: input clk, rst, load, up, down; input [3:0] d; output reg [3:0] q\n"
            "Synchronous 4-bit counter with these behaviors (priority order):\n"
            "  1. rst=1  -> q <= 0  (highest priority)\n"
            "  2. load=1 -> q <= d  (load overrides up/down)\n"
            "  3. up=1 and down=0 -> q <= q + 1  (wraps 15->0)\n"
            "  4. down=1 and up=0 -> q <= q - 1  (wraps 0->15)\n"
            "  5. up=1 and down=1 -> hold (no change)\n"
            "  6. otherwise -> hold\n"
            "All operations occur on posedge clk. Use a single always block.\n"
        ),
        # LLM failure vectors:
        #  1. Wrong priority (often puts up before load)
        #  2. Forgetting wrap-around (uses if q<15 instead of just +1)
        #  3. up+down simultaneously — LLMs often increment or decrement anyway
    },

    "carry_lookahead_4bit": {
        "spec": (
            "Create a Verilog-2001 module named 'carry_lookahead_4bit'.\n"
            "Ports: input [3:0] a, b; input cin; output [3:0] sum; output cout\n"
            "Implement a 4-bit carry-lookahead adder using the standard CLA equations.\n"
            "Do NOT use a ripple-carry structure (no chained carry signals).\n"
            "Compute generate and propagate for each bit:\n"
            "  g[i] = a[i] & b[i]\n"
            "  p[i] = a[i] ^ b[i]\n"
            "Then compute carries in parallel:\n"
            "  c[0] = cin\n"
            "  c[1] = g[0] | (p[0] & c[0])\n"
            "  c[2] = g[1] | (p[1] & c[1])\n"
            "  c[3] = g[2] | (p[2] & c[2])\n"
            "  cout = g[3] | (p[3] & c[3])\n"
            "  sum[i] = p[i] ^ c[i]\n"
            "Declare all intermediate signals (g, p, c) as wire [3:0] or wire [4:0].\n"
            "All outputs are combinational — use assign statements only.\n"
            "Declare sum and cout as wire (not reg).\n"
        ),
        # LLM failure vectors:
        #  1. Using a & b for propagate instead of a ^ b (or vice versa)
        #  2. Bit-width mismatch on c[4:0] vs c[3:0] -> Verilator width warning
        #  3. Accidentally using blocking assignments in always block -> latch risk
        #  4. Forgetting to declare intermediates -> implicit nets
    },

    "d_latch_gated": {
        "spec": (
            "Create a Verilog-2001 module named 'd_latch_gated'.\n"
            "Ports: input en, d; output reg q\n"
            "Implement a transparent D latch (NOT a D flip-flop):\n"
            "  - When en=1 (gate open): q follows d continuously.\n"
            "  - When en=0 (gate closed): q holds its last value.\n"
            "This is a LEVEL-SENSITIVE device. Do NOT use posedge or negedge.\n"
            "Use:  always @(en or d)\n"
            "      if (en) q = d;\n"
            "There is NO clock port. There is NO reset.\n"
            "A D latch is fundamentally different from a D flip-flop.\n"
            "Synthesis of this module should produce a $dlatch cell, not a $dff.\n"
        ),
        # LLM failure vectors:
        #  1. Almost always adds 'posedge clk' -> Yosys shows $dff not $dlatch
        #  2. Adds a clock port that doesn't exist in the testbench -> port mismatch
        #  3. Verilator warns about sensitivity list if @(*) used without en
    },

    "parity_checker_8bit": {
        "spec": (
            "Create a Verilog-2001 module named 'parity_checker_8bit'.\n"
            "Ports: input [7:0] data; input mode; output wire parity_ok\n"
            "Compute parity of 'data' and check against 'mode':\n"
            "  raw_parity = XOR of all 8 bits of data  (^data)\n"
            "  mode=0: EVEN parity check -> parity_ok=1 when raw_parity==0 "
            "(even number of 1s in data)\n"
            "  mode=1: ODD  parity check -> parity_ok=1 when raw_parity==1 "
            "(odd number of 1s in data)\n"
            "In other words: parity_ok = (raw_parity == mode) ? ... think carefully.\n"
            "  When mode=0: ok if XOR==0  => parity_ok = ~raw_parity\n"
            "  When mode=1: ok if XOR==1  => parity_ok = raw_parity\n"
            "  Combined:    parity_ok = (mode == 0) ? ~raw_parity : raw_parity\n"
            "               OR equivalently: parity_ok = ~(raw_parity ^ mode)\n"
            "               OR:              parity_ok = !(^data ^ mode)\n"
            "Declare parity_ok as 'wire' and use a single assign statement.\n"
            "Do NOT use 'output reg' — this is purely combinational.\n"
        ),
        # LLM failure vectors:
        #  1. Inverted polarity: parity_ok = raw_parity ^ mode (wrong)
        #     correct is ~(raw_parity ^ mode) or XNOR
        #  2. output reg + assign -> Verilator: CONTASSIGN warning immediately
        #  3. Forgetting the mode inversion for even vs odd
    },
}


# ── COMPARISON SUMMARY ────────────────────────────────────────────────────────
def print_comparison(baseline_metrics, advanced_metrics, model):
    W = 75
    print(f"\n{'='*W}")
    print(f"  COMPARISON RESULTS  |  Model: {model}")
    print(f"{'='*W}")
    print(f"  {'Module':<26} {'Baseline':^20} {'Advanced':^20} {'Δ iters':>7}")
    print(f"  {'':26} {'Pass? | Iters':^20} {'Pass? | Iters':^20}")
    print(f"  {'-'*73}")

    base_map = {m["module"]: m for m in baseline_metrics}
    adv_map  = {m["module"]: m for m in advanced_metrics}

    total_base_iters = 0
    total_adv_iters  = 0
    base_passed = 0
    adv_passed  = 0

    for mod in BENCHMARK:
        bm = base_map.get(mod)
        am = adv_map.get(mod)
        if not bm or not am:
            continue

        bp    = "PASS" if bm["pass_at_1"] else "FAIL"
        ap    = "PASS" if am["pass_at_1"] else "FAIL"
        biters = bm["iterations_to_pass"] or MAX_RETRIES
        aiters = am["iterations_to_pass"] or MAX_RETRIES
        delta  = biters - aiters  # positive = advanced needed fewer iters

        total_base_iters += biters
        total_adv_iters  += aiters
        if bm["pass_at_1"]: base_passed += 1
        if am["pass_at_1"]: adv_passed  += 1

        delta_str = f"+{delta}" if delta > 0 else str(delta)
        print(f"  {mod:<26} {bp+' | '+str(biters):^20} {ap+' | '+str(aiters):^20} {delta_str:>7}")

    n = len(BENCHMARK)
    print(f"\n  {'Pass rate':<26} {base_passed}/{n:^18} {adv_passed}/{n:^18}")
    print(f"  {'Total iterations':<26} {total_base_iters:^20} {total_adv_iters:^20}"
          f" {total_base_iters-total_adv_iters:>7}")

    # Verilator-specific stats
    total_vl = sum(m.get("verilator_catches", 0) for m in advanced_metrics)
    total_lt  = sum(m.get("latch_warnings", 0) for m in advanced_metrics)
    print(f"\n  Advanced-only diagnostics:")
    print(f"    Verilator early catches : {total_vl} iterations")
    print(f"    Yosys latch warnings    : {total_lt} iterations")
    print(f"{'='*W}\n")


# ── CLI ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AutoChip Advanced Feedback Benchmark",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--model", default="gemini-2.5-flash",
                        help="LLM to use (gemini-2.5-flash, gpt-4o, gemma3:12b, ...)")
    parser.add_argument("--mode", default="both",
                        choices=["baseline", "advanced", "both"],
                        help="baseline=iverilog only | advanced=+Verilator+Yosys | both=compare")
    parser.add_argument("--module", default=None,
                        help="Run a single module by name (default: all 5)")
    args = parser.parse_args()

    # Filter benchmark
    items = list(BENCHMARK.items())
    if args.module:
        items = [(k, v) for k, v in items if k == args.module]
        if not items:
            print(f"ERROR: module '{args.module}' not found in benchmark")
            sys.exit(1)

    safe_model = args.model.replace(":", "_").replace(".", "")
    baseline_results = []
    advanced_results = []

    run_baseline = args.mode in ("baseline", "both")
    run_advanced = args.mode in ("advanced", "both")

    if run_baseline:
        print(f"\n{'#'*65}")
        print(f"  CONDITION A: BASELINE (iverilog+vvp feedback only)")
        print(f"{'#'*65}")
        for mod_name, cfg in items:
            m = autochip_loop(
                spec         = cfg["spec"],
                module_name  = mod_name,
                model        = args.model,
                use_adv_fb   = False,
                condition_tag= "baseline",
            )
            if m:
                baseline_results.append(m)

    if run_advanced:
        print(f"\n{'#'*65}")
        print(f"  CONDITION B: ADVANCED (Verilator + iverilog + Yosys feedback)")
        print(f"{'#'*65}")
        for mod_name, cfg in items:
            m = autochip_loop(
                spec         = cfg["spec"],
                module_name  = mod_name,
                model        = args.model,
                use_adv_fb   = True,
                condition_tag= "advanced",
            )
            if m:
                advanced_results.append(m)

    # Save combined results
    summary_dir = os.path.join(RESULTS_DIR, safe_model)
    os.makedirs(summary_dir, exist_ok=True)
    summary = {
        "model":    args.model,
        "mode":     args.mode,
        "baseline": baseline_results,
        "advanced": advanced_results,
    }
    summary_path = os.path.join(summary_dir, "adv_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Print comparison if both conditions were run
    if run_baseline and run_advanced:
        print_comparison(baseline_results, advanced_results, args.model)

    print(f"  Full results saved -> {summary_path}\n")
