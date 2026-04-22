"""
autochip_runner.py  —  AutoChipFinalTEST Edition  (FINAL v3)
Benchmarks LLM Verilog generation across 20 modules (4 difficulty tiers).
Supports: Ollama (local), Gemini (google-genai SDK), OpenAI (gpt-*)

Usage (run from AutoChipFinalTEST/ folder):
    python autochip_runner.py --model gemma3:4b
    python autochip_runner.py --model gemma3:12b
    python autochip_runner.py --model qwen2.5-coder:14b
    python autochip_runner.py --model gemini-2.5-flash
    python autochip_runner.py --model gemini-2.5-pro
    python autochip_runner.py --model gpt-4o-mini
    python autochip_runner.py --model deepseek-coder:6.7b
    python autochip_runner.py --model llama3.1:8b
    python autochip_runner.py --model gemma3:4b --level easy
    python autochip_runner.py --model gemma3:4b --module half_adder

ALL FIXES (v3 — cumulative from v2):
  FIX-1  classify_error: "not a valid l-value" -> reg_wire_mismatch
  FIX-2  strip_paths: remove absolute Windows/Unix paths from iverilog errors
  FIX-3  build_feedback_message: type-specific repair hints
  FIX-4  ripple_carry_adder spec: "do NOT redefine full_adder"
  FIX-5  uart_tx spec: baud_cnt as reg [7:0]; no $clog2()
  FIX-6  pwm_generator spec: strict < boundary with example
  FIX-7  lfsr_8bit spec: full Galois concat written out explicitly
  FIX-8  pipeline_mult_4x4 spec: N+2 latency stated explicitly
  FIX-A  call_llm: Gemini model name dynamic (GEMINI_MODEL_MAP), not hardcoded
  FIX-B  metrics: sim_other counted; total_time_sec tracked for ALL modules
  FIX-C  stuck-loop detection: same error type >= STUCK_THRESHOLD -> rewrite prompt
  FIX-D  summary table: TotalTime + DominantError columns for every module
"""

import os, subprocess, re, shutil, sys, json, time, argparse
from openai import OpenAI

# ── CONFIG ─────────────────────────────────────────────────────────────────────
MAX_RETRIES     = 5
STUCK_THRESHOLD = 3   # FIX-C: inject rewrite after this many consecutive same errors
TESTBENCH_DIR   = "testbenches"
RESULTS_DIR     = "results"

# FIX-A: maps --model arg to actual Gemini API model string
GEMINI_MODEL_MAP = {
    "gemini-2.5-flash": "models/gemini-2.5-flash",
    "gemini-2.5-pro":   "models/gemini-2.5-pro",
    "gemini-2.0-flash": "models/gemini-2.0-flash-exp",
    "gemini-1.5-flash": "models/gemini-1.5-flash",
    "gemini-1.5-pro":   "models/gemini-1.5-pro",
}

OLLAMA_CLIENT  = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_CLIENT  = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

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

SYSTEM_PROMPT = """You are a Verilog-2001 Expert.
STRICT RULES:
1. Outputs driven by 'assign' statements MUST be declared as 'wire'.
2. Outputs driven by sub-module output ports MUST be declared as 'wire'.
3. ONLY use 'reg' for signals assigned inside an 'always' block.
4. Use non-blocking assignments (<=) inside clocked always blocks.
5. Use blocking assignments (=) inside combinational always blocks.
6. Return ONLY Verilog code inside ```verilog ... ``` fences.
   No prose, no explanations, no non-ASCII characters anywhere in your response.
7. When instantiating an external module provided as a dependency,
   do NOT redefine or redeclare that module inside your file."""


# ── LLM CALL ──────────────────────────────────────────────────────────────────
def call_llm(model, messages):
    """
    Unified LLM caller: Ollama (local), Gemini (google-genai), or OpenAI.
    FIX-A: Gemini model resolved via GEMINI_MODEL_MAP instead of hardcoded string.
    """
    if model.startswith("gemini"):
        if not GEMINI_AVAILABLE:
            print("ERROR: Set GEMINI_API_KEY env var and run: pip install google-genai")
            sys.exit(1)
        api_model = GEMINI_MODEL_MAP.get(model, f"models/{model}")  # FIX-A
        history = "\n".join(
            f"[{'USER' if m['role'] == 'user' else 'ASSISTANT'}]\n{m['content']}"
            for m in messages if m["role"] != "system"
        )
        response = GEMINI_CLIENT.models.generate_content(
            model=api_model,
            config=genai_types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.1,
            ),
            contents=history,
        )
        return response.text

    elif model.startswith("gpt-") or model.startswith("o1") or model.startswith("o3"):
        if not OPENAI_CLIENT:
            print("ERROR: Set OPENAI_API_KEY env var for OpenAI models")
            sys.exit(1)
        response = OPENAI_CLIENT.chat.completions.create(
            model=model, messages=messages, temperature=0.1
        )
        return response.choices[0].message.content

    else:
        # Ollama: gemma3:4b, gemma3:12b, qwen2.5-coder:14b, deepseek-coder:6.7b, etc.
        response = OLLAMA_CLIENT.chat.completions.create(
            model=model, messages=messages, temperature=0.1
        )
        return response.choices[0].message.content


def sanitize_for_ascii(text):
    """
    Strip non-ASCII characters before writing .v file.
    Prevents Windows cp1252 crash when gemma3:4b emits Hindi/Unicode
    and stops iverilog rejecting the file outright.
    """
    return text.encode("ascii", errors="ignore").decode("ascii")


# ── FIX-2: path stripper ──────────────────────────────────────────────────────
_PATH_RE = re.compile(
    r"""(?:[A-Za-z]:[\\/]|[\\/])       # absolute root: Windows C:\ or Unix /
        (?:[^\s:'"\\/<>|*?\n]+[\\/])*  # zero or more directory segments
        ([^\s:'"\\/<>|*?\n]+\.v)       # capture: filename.v
    """,
    re.VERBOSE,
)

def strip_paths(text):
    """
    Replace absolute iverilog paths with just the filename.
      Before: results\\gemma3_4b\\alu_8bit\\iter_3\\alu_8bit.v:11: error ...
      After : alu_8bit.v:11: error ...
    """
    return _PATH_RE.sub(r"\1", text)


# ── VERIFICATION ───────────────────────────────────────────────────────────────
def run_verification(iter_dir, module_name):
    """
    Compile all .v files in iter_dir with iverilog, simulate with vvp.
    Returns (success: bool, feedback: str).
    """
    log_file = os.path.join(iter_dir, "sim_log.txt")
    vvp_out  = os.path.join(iter_dir, "sim.vvp")
    v_files  = sorted(
        os.path.join(iter_dir, f)
        for f in os.listdir(iter_dir) if f.endswith(".v")
    )

    comp_cmd    = ["iverilog", "-o", vvp_out] + v_files
    comp_result = subprocess.run(
        comp_cmd, capture_output=True, text=True, encoding="utf-8"
    )

    with open(log_file, "w", encoding="utf-8") as f:
        f.write(f"--- COMPILATION ---\n{comp_result.stderr}\n")

    if comp_result.returncode != 0:
        err_clean   = strip_paths(comp_result.stderr)   # FIX-2
        err_preview = "\n".join(err_clean.strip().splitlines()[:8])
        print("  iverilog:\n    " + err_preview.replace("\n", "\n    "))
        return False, f"COMPILATION ERROR:\n{err_clean}"

    sim_result = subprocess.run(
        ["vvp", vvp_out], capture_output=True, text=True, encoding="utf-8"
    )
    output = sim_result.stdout + sim_result.stderr

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n--- SIMULATION ---\n{output}\n")

    if "FAIL" in output or (
        "ALL TESTS PASSED" not in output and "PASS" not in output
    ):
        sim_preview = "\n".join(output.strip().splitlines()[:6])
        print("  sim:\n    " + sim_preview.replace("\n", "\n    "))
        return False, f"SIMULATION FAILED:\n{output}"

    return True, output


# ── FIX-1 + FIX-B: improved error classifier ─────────────────────────────────
def classify_error(feedback):
    """
    FIX-1: 'not a valid l-value' -> reg_wire_mismatch (iverilog never says 'driven by').
    FIX-B: sim_other returned for SIMULATION FAILED without FAIL keyword
           (previously fell to 'unknown' which was never counted in any metric).
    """
    if "COMPILATION ERROR" in feedback:
        fb = feedback.lower()
        if "not a valid l-value" in fb:
            return "reg_wire_mismatch"
        if "reg" in fb and ("driven by" in fb or "continuous" in fb):
            return "reg_wire_mismatch"
        if "already declared" in fb or "already been declared" in fb:
            return "duplicate_module"
        if "unknown module" in fb or "these modules were missing" in fb:
            return "missing_module"
        if "syntax error" in fb or "malformed statement" in fb:
            return "syntax_error"
        if "incomprehensible case" in fb:
            return "syntax_error"
        if "is not a port" in fb or "unable to bind" in fb:
            return "port_mismatch"
        if "sorry:" in fb or "not currently supported" in fb:
            return "unsupported_construct"
        return "compile_other"

    if "SIMULATION FAILED" in feedback:
        return "logic_error" if "FAIL" in feedback else "sim_other"  # FIX-B

    return "sim_other"  # FIX-B: never leave a failure uncounted


# ── FIX-3: type-specific repair hints ────────────────────────────────────────
_HINTS = {
    "reg_wire_mismatch": (
        "\nHINT: 'not a valid l-value' means a signal declared as 'wire' is "
        "being driven inside an 'always' block. Change its declaration from "
        "'wire' to 'reg'. Rule: 'wire' is for signals driven by 'assign' or "
        "sub-module ports; 'reg' is for signals assigned inside 'always' blocks."
    ),
    "duplicate_module": (
        "\nHINT: 'Module X was already declared' means you wrote a module "
        "definition that already exists in a separately provided dependency file. "
        "DELETE that module definition from your code. Only write the single "
        "top-level module that was requested."
    ),
    "missing_module": (
        "\nHINT: A module you are instantiating cannot be found. Use the EXACT "
        "module name from the specification — check spelling and case. Do not "
        "write your own copy of it; it is already provided externally."
    ),
    "port_mismatch": (
        "\nHINT: A port name does not match what the testbench expects. Use "
        "EXACTLY the port names from the specification — same case, same spelling, "
        "no abbreviations, no renames."
    ),
    "syntax_error": (
        "\nHINT: Verilog-2001 syntax error. Common causes: (1) missing semicolons, "
        "(2) mismatched begin/end or case/endcase, (3) using SystemVerilog keywords "
        "(logic, always_comb, always_ff) — use only Verilog-2001 syntax, "
        "(4) a net declared twice."
    ),
    "unsupported_construct": (
        "\nHINT: You used a construct this version of iverilog does not support. "
        "Do NOT use $clog2() in port-width or parameter expressions. "
        "Replace it with a fixed integer literal (e.g. reg [7:0] instead of "
        "reg [$clog2(N)-1:0])."
    ),
    "logic_error": (
        "\nHINT: The module compiles but produces wrong output. Read each FAIL "
        "line — it shows exact inputs, expected output, and actual output. "
        "Trace your logic step by step against those values and correct the mismatch."
    ),
    "sim_other": (
        "\nHINT: Simulation ran but produced no recognisable PASS/FAIL output. "
        "Ensure your module drives all output signals and that the testbench can "
        "detect at least one PASS before it finishes."
    ),
}

# FIX-C: rewrite prompt template injected after STUCK_THRESHOLD identical errors
_REWRITE_PROMPT = (
    "Your previous {n} attempts all failed with the same error: '{err_type}'. "
    "The targeted fixes are not converging.\n\n"
    "DISCARD your previous implementation completely. "
    "Write a BRAND-NEW Verilog-2001 module from scratch using only the "
    "original specification below. Do not reuse any code from prior attempts.\n\n"
    "ORIGINAL SPECIFICATION:\n{spec}\n\n"
    "Return ONLY the complete module inside a single ```verilog ... ``` block. "
    "No prose, no comments outside the fence, ASCII characters only."
)

def build_feedback_message(feedback, err_type):
    """Build repair prompt with type-specific hint (FIX-3)."""
    hint = _HINTS.get(err_type, "")
    return (
        "The Verilog code failed. Fix ALL errors and return the COMPLETE "
        "corrected module inside a single ```verilog ... ``` block. "
        "ASCII only, no prose outside the fence.\n\n"
        f"Error output:\n{feedback}"
        f"{hint}"
    )


# ── MAIN LOOP ──────────────────────────────────────────────────────────────────
def autochip_loop(spec, module_name, model, dependencies=None):
    """
    AutoChip iterative repair loop for one module.
    Returns metrics dict, or None if testbench is missing.

    FIX-B: total_time_sec populated for every module (pass or fail).
    FIX-C: stuck-loop detection -> rewrite prompt after STUCK_THRESHOLD
           consecutive identical error types.
    """
    if dependencies is None:
        dependencies = []

    tb_path = os.path.join(TESTBENCH_DIR, f"{module_name}_tb.v")
    if not os.path.exists(tb_path):
        print(f"  ERROR: Missing testbench: {tb_path}")
        return None

    safe_model  = model.replace(":", "_").replace(".", "")
    project_dir = os.path.join(RESULTS_DIR, safe_model, module_name)
    os.makedirs(project_dir, exist_ok=True)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": spec},
    ]

    # FIX-B: total_time_sec always populated
    metrics = {
        "module":             module_name,
        "model":              model,
        "pass_at_1":          False,
        "iterations_to_pass": None,
        "time_to_pass_sec":   None,
        "total_time_sec":     None,    # FIX-B
        "total_iterations":   MAX_RETRIES,
        "compile_errors":     0,
        "sim_errors":         0,
        "error_types":        [],
        "max_retries":        MAX_RETRIES,
    }

    print(f"\n{'='*60}")
    print(f"  AutoChip: {module_name}  |  Model: {model}")
    print(f"{'='*60}")
    t_start = time.time()

    consecutive_same = 0
    last_err_type    = None

    for i in range(MAX_RETRIES):
        iter_dir = os.path.join(project_dir, f"iter_{i+1}")
        os.makedirs(iter_dir, exist_ok=True)
        print(f"\n  Iteration {i+1}/{MAX_RETRIES}")

        # ── Call LLM ──────────────────────────────────────────────────────
        t_llm = time.time()
        try:
            llm_output = call_llm(model, messages)
        except Exception as e:
            print(f"  LLM Error: {e}")
            break
        print(f"  LLM responded in {time.time()-t_llm:.1f}s")

        # ── Save raw response ──────────────────────────────────────────────
        with open(os.path.join(iter_dir, "raw_ai_response.txt"),
                  "w", encoding="utf-8") as f:
            f.write(llm_output)

        # ── Extract Verilog block ──────────────────────────────────────────
        match = re.search(r"```(?:verilog)?(.*?)```", llm_output, re.DOTALL)
        code  = match.group(1).strip() if match else llm_output.strip()
        code  = sanitize_for_ascii(code)

        # ── Write .v file ──────────────────────────────────────────────────
        with open(os.path.join(iter_dir, f"{module_name}.v"),
                  "w", encoding="utf-8") as f:
            f.write(code)

        # ── Copy dependencies and testbench into iter_dir ──────────────────
        for dep in dependencies:
            if os.path.exists(dep):
                shutil.copy(dep, iter_dir)
            else:
                print(f"  WARNING: Dependency not found: {dep}")
        shutil.copy(tb_path, iter_dir)

        # ── Compile + simulate ─────────────────────────────────────────────
        success, feedback = run_verification(iter_dir, module_name)
        elapsed = time.time() - t_start

        if success:
            print(f"  PASSED on iteration {i+1}  ({elapsed:.1f}s total)")
            metrics.update({
                "pass_at_1":          True,
                "iterations_to_pass": i + 1,
                "time_to_pass_sec":   round(elapsed, 2),
                "total_time_sec":     round(elapsed, 2),  # FIX-B
                "total_iterations":   i + 1,
            })
            break

        # ── Error handling ─────────────────────────────────────────────────
        err_type = classify_error(feedback)

        # FIX-B: sim_other is now a real category, so always increment one counter
        if "COMPILATION" in feedback:
            metrics["compile_errors"] += 1
        else:
            metrics["sim_errors"] += 1

        metrics["error_types"].append(err_type)
        print(f"  FAIL: {err_type}  -- sending feedback to LLM")

        # FIX-C: stuck-loop detection
        if err_type == last_err_type:
            consecutive_same += 1
        else:
            consecutive_same = 1
            last_err_type    = err_type

        messages.append({"role": "assistant", "content": llm_output})

        if consecutive_same >= STUCK_THRESHOLD:
            print(f"  STUCK on '{err_type}' for {consecutive_same} iterations"
                  " -- injecting full rewrite prompt")
            messages.append({
                "role": "user",
                "content": _REWRITE_PROMPT.format(
                    n        = consecutive_same,
                    err_type = err_type,
                    spec     = spec,
                ),
            })
            consecutive_same = 0   # reset after rewrite injection
        else:
            messages.append({
                "role":    "user",
                "content": build_feedback_message(feedback, err_type),
            })

    # FIX-B: guarantee total_time_sec is always set
    if metrics["total_time_sec"] is None:
        metrics["total_time_sec"] = round(time.time() - t_start, 2)

    with open(os.path.join(project_dir, "metrics.json"),
              "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    if not metrics["pass_at_1"]:
        print(f"  FAILED after {MAX_RETRIES} iterations "
              f"({metrics['total_time_sec']:.1f}s total)")

    return metrics


# ── BENCHMARK DEFINITION ───────────────────────────────────────────────────────
BENCHMARK = {

    # ======== L1 EASY ========
    "half_adder": {
        "level": "easy", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'half_adder'.\n"
            "Ports: input a, b; output sum, cout\n"
            "Logic: assign sum = a ^ b; assign cout = a & b;\n"
            "Declare sum and cout as wire."
        ),
    },
    "full_adder": {
        "level": "easy", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'full_adder'.\n"
            "Ports: input a, b, cin; output sum, cout\n"
            "Use only continuous assign statements:\n"
            "  assign sum  = a ^ b ^ cin;\n"
            "  assign cout = (a & b) | (b & cin) | (a & cin);\n"
            "Declare sum and cout as wire. Do NOT use always blocks."
        ),
    },
    "ripple_carry_adder": {   # FIX-4
        "level": "easy", "deps": ["full_adder.v"],
        "spec": (
            "Create a Verilog-2001 module named 'ripple_carry_adder'.\n"
            "Ports: input [3:0] A, B; input cin; output [3:0] Sum; output cout\n"
            "CRITICAL: Do NOT define or redeclare the 'full_adder' module anywhere "
            "in this file. It is provided as a separately compiled dependency. "
            "Only write the 'ripple_carry_adder' module -- nothing else.\n"
            "Rules:\n"
            "1. Declare Sum [3:0] and cout as wire.\n"
            "2. Instantiate 'full_adder' four times: fa0, fa1, fa2, fa3.\n"
            "3. full_adder port names exactly: .a  .b  .cin  .sum  .cout\n"
            "4. Chain carries: fa0.cout->fa1.cin, fa1.cout->fa2.cin, fa2.cout->fa3.cin\n"
            "5. fa0.cin = cin (module input); fa3.cout = cout (module output)\n"
            "6. Sum[0]=fa0.sum, Sum[1]=fa1.sum, Sum[2]=fa2.sum, Sum[3]=fa3.sum"
        ),
    },
    "comparator_8bit": {
        "level": "easy", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'comparator_8bit'.\n"
            "Ports: input [7:0] A, B; output gt, eq, lt\n"
            "Logic (assign only):\n"
            "  assign gt = (A > B);\n"
            "  assign eq = (A == B);\n"
            "  assign lt = (A < B);\n"
            "Declare gt, eq, lt as wire."
        ),
    },
    "bcd_to_7seg": {
        "level": "easy", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'bcd_to_7seg'.\n"
            "Ports: input [3:0] bcd; output reg [6:0] seg\n"
            "Use a combinational always @(*) block with a case statement.\n"
            "seg[6:0] = {a,b,c,d,e,f,g} active-HIGH:\n"
            "  0->7'b1111110  1->7'b0110000  2->7'b1101101  3->7'b1111001\n"
            "  4->7'b0110011  5->7'b1011011  6->7'b1011111  7->7'b1110000\n"
            "  8->7'b1111111  9->7'b1111011  default->7'b0000000\n"
            "Declare seg as reg."
        ),
    },
    "priority_enc_8": {
        "level": "easy", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'priority_enc_8'.\n"
            "Ports: input [7:0] in; output reg [2:0] out; output valid\n"
            "Logic:\n"
            "  assign valid = (|in);   // continuous assign, valid is wire\n"
            "  Use a combinational always @(*) if-else chain for out:\n"
            "    if      (in[7]) out = 3'd7;\n"
            "    else if (in[6]) out = 3'd6;\n"
            "    else if (in[5]) out = 3'd5;\n"
            "    else if (in[4]) out = 3'd4;\n"
            "    else if (in[3]) out = 3'd3;\n"
            "    else if (in[2]) out = 3'd2;\n"
            "    else if (in[1]) out = 3'd1;\n"
            "    else if (in[0]) out = 3'd0;\n"
            "    else            out = 3'd0;\n"
            "Declare out as reg, valid as wire. Do NOT use casez."
        ),
    },

    # ======== L2 MEDIUM ========
    "alu_8bit": {
        "level": "medium", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'alu_8bit'.\n"
            "Ports: input [7:0] A, B; input [2:0] op;\n"
            "       output reg [7:0] result; output wire zero\n"
            "Combinational always @(*) with case on op:\n"
            "  3'b000 ADD:   result = A + B;\n"
            "  3'b001 SUB:   result = A - B;\n"
            "  3'b010 AND:   result = A & B;\n"
            "  3'b011 OR:    result = A | B;\n"
            "  3'b100 XOR:   result = A ^ B;\n"
            "  3'b101 NOT_A: result = ~A;\n"
            "  3'b110 SHL:   result = A << 1;\n"
            "  3'b111 SHR:   result = A >> 1;\n"
            "  default:      result = 8'h00;\n"
            "assign zero = (result == 8'h00);\n"
            "Declare result as reg, zero as wire."
        ),
    },
    "dff_sync_reset": {
        "level": "medium", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'dff_sync_reset'.\n"
            "Ports: input clk, rst, d; output reg q\n"
            "D flip-flop with synchronous active-high reset:\n"
            "  always @(posedge clk) begin\n"
            "    if (rst) q <= 1'b0;\n"
            "    else     q <= d;\n"
            "  end\n"
            "Declare q as reg."
        ),
    },
    "counter_4bit": {
        "level": "medium", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'counter_4bit'.\n"
            "Ports: input clk, rst; output reg [3:0] count\n"
            "4-bit unsigned up-counter, synchronous active-high reset:\n"
            "  always @(posedge clk) begin\n"
            "    if (rst) count <= 4'b0;\n"
            "    else     count <= count + 1'b1;\n"
            "  end\n"
            "Declare count as reg. Wraps naturally 15->0."
        ),
    },
    "lfsr_8bit": {   # FIX-7
        "level": "medium", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'lfsr_8bit'.\n"
            "Ports: input clk, rst, load, enable; input [7:0] seed;\n"
            "       output reg [7:0] lfsr_out\n"
            "8-bit Galois LFSR, polynomial x^8 + x^6 + x^5 + x^4 + 1.\n"
            "Feedback bit = lfsr_out[0] (LSB, read BEFORE the shift).\n"
            "Synchronous always @(posedge clk), priority order:\n"
            "  1. if (rst)          lfsr_out <= 8'hFF;\n"
            "  2. else if (load)    lfsr_out <= seed;\n"
            "  3. else if (enable)  // Galois right-shift with XOR feedback:\n"
            "       lfsr_out <= {\n"
            "           lfsr_out[0],              // new bit[7] = feedback\n"
            "           lfsr_out[7:6],            // bit[6:5]  plain shift\n"
            "           lfsr_out[5]^lfsr_out[0],  // bit[4]    tap x^6\n"
            "           lfsr_out[4]^lfsr_out[0],  // bit[3]    tap x^5\n"
            "           lfsr_out[3]^lfsr_out[0],  // bit[2]    tap x^4\n"
            "           lfsr_out[2:1]             // bit[1:0]  plain shift\n"
            "       };\n"
            "  4. else              hold (no change).\n"
            "Declare lfsr_out as reg."
        ),
    },
    "pwm_generator": {   # FIX-6
        "level": "medium", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'pwm_generator'.\n"
            "Ports: input clk, rst; input [7:0] duty_cycle;\n"
            "       output wire pwm_out\n"
            "Internal 8-bit free-running counter (0..255 wraps), sync reset:\n"
            "  always @(posedge clk) begin\n"
            "    if (rst) counter <= 8'd0;\n"
            "    else     counter <= counter + 1'b1;\n"
            "  end\n"
            "Output (STRICTLY less-than -- NOT less-than-or-equal):\n"
            "  assign pwm_out = (counter < duty_cycle);\n"
            "  pwm_out=1 when counter is 0,1,...,duty_cycle-1\n"
            "  pwm_out=0 when counter is duty_cycle,...,255\n"
            "  Example: duty_cycle=4 => HIGH for counter=0,1,2,3 only.\n"
            "Declare counter as reg [7:0]. Declare pwm_out as wire."
        ),
    },
    "gray_counter_4bit": {
        "level": "medium", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'gray_counter_4bit'.\n"
            "Ports: input clk, rst; output wire [3:0] gray_out\n"
            "Internal 4-bit binary up-counter, synchronous active-high reset:\n"
            "  always @(posedge clk) begin\n"
            "    if (rst) bin <= 4'b0;\n"
            "    else     bin <= bin + 1'b1;\n"
            "  end\n"
            "Gray encode: assign gray_out = bin ^ (bin >> 1);\n"
            "Declare bin as reg [3:0]. Declare gray_out as wire."
        ),
    },

    # ======== L3 HARD ========
    "simple_cpu_alu": {
        "level": "hard", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'simple_cpu_alu'.\n"
            "Ports: input [3:0] A, B; input [1:0] op;\n"
            "       output reg [3:0] result; output wire zero\n"
            "Combinational always @(*) with case on op:\n"
            "  2'b00 ADD: result = A + B;\n"
            "  2'b01 SUB: result = A - B;\n"
            "  2'b10 AND: result = A & B;\n"
            "  2'b11 OR:  result = A | B;\n"
            "  default:   result = 4'b0;\n"
            "assign zero = (result == 4'b0000);\n"
            "Declare result as reg, zero as wire."
        ),
    },
    "fsm_seq_detector": {
        "level": "hard", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'fsm_seq_detector'.\n"
            "Ports: input clk, rst, in; output wire detected\n"
            "Mealy FSM detecting sequence 1011 on serial input 'in'.\n"
            "States (reg [1:0] state): S0=2'd0, S1=2'd1, S2=2'd2, S3=2'd3\n"
            "Synchronous state register (posedge clk), sync reset to S0:\n"
            "  S0: in=1->S1,  in=0->S0\n"
            "  S1: in=0->S2,  in=1->S1\n"
            "  S2: in=1->S3,  in=0->S0\n"
            "  S3: in=1->S1,  in=0->S2  (output fires here; 1 is reused)\n"
            "Combinational output:\n"
            "  assign detected = (state == 2'd3) & in;\n"
            "Declare state as reg [1:0], detected as wire."
        ),
    },
    "uart_tx": {   # FIX-5
        "level": "hard", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'uart_tx'.\n"
            "Parameter: BAUD_DIV = 104\n"
            "Ports: input clk, rst, start; input [7:0] data_in;\n"
            "       output reg tx_out, busy, done\n"
            "UART 8N1 transmitter.\n"
            "Frame: start-bit(0) + 8 data bits LSB-first + stop-bit(1).\n"
            "Each bit lasts exactly BAUD_DIV clock cycles.\n"
            "FSM states (reg [2:0]): IDLE=3'd0 START=3'd1 DATA=3'd2 "
            "STOP=3'd3 DONE=3'd4\n"
            "Internal registers:\n"
            "  reg [7:0] shift_reg  -- data shift register\n"
            "  reg [7:0] baud_cnt   -- baud counter, declare as reg [7:0],"
            " do NOT use $clog2()\n"
            "  reg [3:0] bit_cnt    -- bit index 0..7\n"
            "All assignments non-blocking (<=):\n"
            "  IDLE:  tx_out<=1; busy<=0; done<=0.\n"
            "         On start=1: shift_reg<=data_in; baud_cnt<=0; bit_cnt<=0;"
            " goto START.\n"
            "  START: tx_out<=0; busy<=1.\n"
            "         Increment baud_cnt each cycle.\n"
            "         When baud_cnt==BAUD_DIV-1: baud_cnt<=0; goto DATA.\n"
            "  DATA:  busy<=1; tx_out<=shift_reg[0].\n"
            "         Increment baud_cnt each cycle.\n"
            "         When baud_cnt==BAUD_DIV-1: baud_cnt<=0;\n"
            "           shift_reg<={1'b0,shift_reg[7:1]}; bit_cnt<=bit_cnt+1;\n"
            "           if bit_cnt==7: goto STOP; else stay in DATA.\n"
            "  STOP:  tx_out<=1; busy<=1.\n"
            "         Increment baud_cnt each cycle.\n"
            "         When baud_cnt==BAUD_DIV-1: baud_cnt<=0; goto DONE.\n"
            "  DONE:  done<=1; busy<=0; tx_out<=1; goto IDLE."
        ),
    },
    "sync_fifo_8": {
        "level": "hard", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'sync_fifo_8'.\n"
            "Ports: input clk, rst, wr_en, rd_en; input [7:0] din;\n"
            "       output reg [7:0] dout; output wire full, empty\n"
            "Synchronous FIFO: 8 entries x 8-bit wide.\n"
            "Internal: reg [7:0] mem [0:7]; reg [3:0] wr_ptr, rd_ptr;\n"
            "  assign empty = (wr_ptr == rd_ptr);\n"
            "  assign full  = (wr_ptr[2:0] == rd_ptr[2:0]) && "
            "(wr_ptr[3] != rd_ptr[3]);\n"
            "Synchronous (posedge clk):\n"
            "  if rst: wr_ptr<=0; rd_ptr<=0; dout<=0;\n"
            "  else:\n"
            "    if (wr_en && !full):  mem[wr_ptr[2:0]]<=din; wr_ptr<=wr_ptr+1;\n"
            "    if (rd_en && !empty): dout<=mem[rd_ptr[2:0]]; rd_ptr<=rd_ptr+1;\n"
            "Declare dout as reg; full and empty as wire."
        ),
    },
    "alu_accumulator_top": {
        "level": "hard", "deps": ["alu_8bit.v"],
        "spec": (
            "Create a Verilog-2001 module named 'alu_accumulator_top'.\n"
            "Ports: input clk, rst; input [7:0] data_in; input [2:0] op;\n"
            "       input load_acc; output wire [7:0] acc_out; output wire zero\n"
            "CRITICAL: Do NOT redefine 'alu_8bit' -- it is a provided dependency.\n"
            "Internal: wire [7:0] alu_result; reg [7:0] acc;\n"
            "Instantiate 'alu_8bit' as u_alu with named port connections:\n"
            "  .A(acc_out), .B(data_in), .op(op), .result(alu_result), .zero(zero)\n"
            "Accumulator register:\n"
            "  always @(posedge clk) begin\n"
            "    if (rst)           acc <= 8'h00;\n"
            "    else if (load_acc) acc <= data_in;\n"
            "    else               acc <= alu_result;\n"
            "  end\n"
            "assign acc_out = acc;\n"
            "Declare acc as reg [7:0]; alu_result, acc_out, zero as wire."
        ),
    },

    # ======== L4 CRITICAL ========
    "param_register_file": {
        "level": "critical", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'param_register_file'.\n"
            "Parameters: N = 4, W = 8\n"
            "Ports: input clk, wr_en;\n"
            "       input  [1:0]   wr_addr, rd_addr;\n"
            "       input  [W-1:0] wr_data;\n"
            "       output wire [W-1:0] rd_data\n"
            "Use parameters N and W -- NOT literal numbers -- in all declarations:\n"
            "  reg [W-1:0] mem [0:N-1];\n"
            "Write (synchronous):\n"
            "  always @(posedge clk) if (wr_en) mem[wr_addr] <= wr_data;\n"
            "Read (combinational):\n"
            "  assign rd_data = mem[rd_addr];\n"
            "Declare rd_data as wire."
        ),
    },
    "pipeline_mult_4x4": {   # FIX-8
        "level": "critical", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'pipeline_mult_4x4'.\n"
            "Ports: input clk; input [3:0] a, b; output reg [7:0] product\n"
            "2-stage pipelined 4x4 unsigned multiplier.\n"
            "Internal registers: reg [3:0] a_r, b_r;\n"
            "Both stages update in ONE always block on the SAME posedge clk:\n"
            "  always @(posedge clk) begin\n"
            "    a_r     <= a;           // Stage 1: latch inputs\n"
            "    b_r     <= b;\n"
            "    product <= a_r * b_r;   // Stage 2: multiply the latched values\n"
            "  end\n"
            "TIMING: inputs at cycle N appear at product at cycle N+2 (not N+1).\n"
            "The testbench checks product exactly 2 cycles after inputs are applied.\n"
            "Do NOT compute the product combinationally.\n"
            "Do NOT use separate always blocks for the two stages."
        ),
    },
    "spi_master_8bit": {
        "level": "critical", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'spi_master_8bit'.\n"
            "Parameter: CLK_DIV = 4\n"
            "Ports: input clk, rst, start; input [7:0] mosi_data; input miso;\n"
            "       output reg sclk, cs_n, mosi, done;\n"
            "       output reg [7:0] miso_capture\n"
            "SPI master mode 0 (CPOL=0, CPHA=0), 8-bit MSB-first.\n"
            "FSM states (reg [1:0]): IDLE=2'd0, ACTIVE=2'd1, DONE_ST=2'd2\n"
            "Internal: reg [7:0] shift_out, shift_in; reg [3:0] clk_cnt, bit_cnt;\n"
            "IDLE:  cs_n=1, sclk=0, done=0.\n"
            "  On start: cs_n<=0; shift_out<=mosi_data; bit_cnt<=0; "
            "clk_cnt<=0; goto ACTIVE.\n"
            "ACTIVE: each bit takes 2*CLK_DIV clocks.\n"
            "  clk_cnt increments each cycle.\n"
            "  First half  (clk_cnt < CLK_DIV):    sclk<=0; mosi<=shift_out[7].\n"
            "  At clk_cnt==CLK_DIV-1:               sclk<=1.\n"
            "  Second half (clk_cnt >= CLK_DIV):    sclk<=1.\n"
            "  At clk_cnt==2*CLK_DIV-2:             "
            "shift_in<={shift_in[6:0],miso}.\n"
            "  At clk_cnt==2*CLK_DIV-1: sclk<=0; "
            "shift_out<={shift_out[6:0],1'b0};\n"
            "    clk_cnt<=0; bit_cnt<=bit_cnt+1.\n"
            "  When bit_cnt==8: cs_n<=1; miso_capture<=shift_in; goto DONE_ST.\n"
            "DONE_ST: done<=1 for 1 cycle; goto IDLE."
        ),
    },
}


# ── CLI ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AutoChip HDL Benchmark -- Final v3",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--model", default="gemma3:4b",
        help=(
            "Model to benchmark.\n"
            "  Ollama : gemma3:4b  gemma3:12b  qwen2.5-coder:14b\n"
            "           deepseek-coder:6.7b  llama3.1:8b\n"
            "  Gemini : gemini-2.5-flash  gemini-2.5-pro\n"
            "  OpenAI : gpt-4o-mini  gpt-4o"
        ),
    )
    parser.add_argument("--module", default=None,
                        help="Run a single module by name (omit for all 20)")
    parser.add_argument("--level", default=None,
                        choices=["easy", "medium", "hard", "critical"],
                        help="Run only modules of this difficulty tier")
    parser.add_argument("--deps", nargs="*", default=None,
                        help="Override dependency .v paths (single-module run only)")
    args = parser.parse_args()

    # ── Filter benchmark ────────────────────────────────────────────────────
    items = list(BENCHMARK.items())
    if args.level:
        items = [(k, v) for k, v in items if v.get("level") == args.level]
    if args.module and args.module != "all":
        items = [(k, v) for k, v in items if k == args.module]

    if not items:
        print(f"ERROR: No modules matched (module={args.module}, "
              f"level={args.level})")
        sys.exit(1)

    # ── Single module shortcut ──────────────────────────────────────────────
    if len(items) == 1 and args.module and args.module != "all":
        mod_name, config = items[0]
        deps = args.deps if args.deps is not None else config["deps"]
        autochip_loop(config["spec"], mod_name, args.model, deps)
        sys.exit(0)

    # ── Batch run ───────────────────────────────────────────────────────────
    print(f"\nRunning benchmark | Model: {args.model}"
          + (f" | Level: {args.level}" if args.level else ""))

    all_metrics = []
    safe_model  = args.model.replace(":", "_").replace(".", "")

    for mod_name, config in items:
        # Resolve each dependency from the PASSING iteration's output .v file
        dep_files = []
        for dep in config["deps"]:
            dep_module  = dep.replace(".v", "")
            dep_results = os.path.join(RESULTS_DIR, safe_model, dep_module)
            found       = False
            metrics_f   = os.path.join(dep_results, "metrics.json")
            if os.path.exists(metrics_f):
                try:
                    with open(metrics_f, encoding="utf-8") as mf:
                        dep_m = json.load(mf)
                    itp = dep_m.get("iterations_to_pass")
                    if itp:
                        candidate = os.path.join(
                            dep_results, f"iter_{itp}", dep
                        )
                        if os.path.exists(candidate):
                            dep_files.append(candidate)
                            found = True
                except Exception:
                    pass
            if not found:
                print(f"  WARNING: Dependency {dep} not found for {mod_name} "
                      "(did the dependency module pass?)")

        m = autochip_loop(config["spec"], mod_name, args.model, dep_files)
        if m:
            all_metrics.append(m)

    # ── Summary table (FIX-B + FIX-D) ─────────────────────────────────────
    # Shows TotalTime for every module and DominantError for failed ones
    W = 72
    print(f"\n{'='*W}")
    print(f"  SUMMARY  --  Model: {args.model}")
    print(f"{'='*W}")
    print(f"  {'Module':<26} {'Lvl':<6} {'P':>2} "
          f"{'It':>3} {'PassT':>7} {'TotT':>7} "
          f"{'CE':>3} {'SE':>3}  DominantError")
    print(f"  {'-'*70}")

    passed = 0
    for m in all_metrics:
        lvl  = BENCHMARK[m["module"]].get("level", "?")[:5]
        p    = "Y" if m["pass_at_1"] else "N"
        it   = str(m["iterations_to_pass"]) if m["iterations_to_pass"] else "-"
        pt   = f"{m['time_to_pass_sec']:.1f}" if m["time_to_pass_sec"] else "-"
        tt   = f"{m['total_time_sec']:.1f}"   if m["total_time_sec"]   else "-"
        etypes = m.get("error_types", [])
        dom    = max(set(etypes), key=etypes.count) if etypes else "-"
        print(f"  {m['module']:<26} {lvl:<6} {p:>2} "
              f"{it:>3} {pt:>7} {tt:>7} "
              f"{m['compile_errors']:>3} {m['sim_errors']:>3}  {dom}")
        if m["pass_at_1"]:
            passed += 1

    total   = len(all_metrics)
    pct     = 100 * passed // max(total, 1)
    total_t = sum(m.get("total_time_sec") or 0 for m in all_metrics)
    print(f"\n  Pass@1 : {passed}/{total} = {pct}%")
    print(f"  Failed : {total - passed}/{total}")
    print(f"  Total wall-clock time: {total_t:.0f}s ({total_t/60:.1f} min)")

    # Save combined summary JSON
    summary_path = os.path.join(RESULTS_DIR, safe_model, "summary.json")
    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(
            {"model": args.model, "pass_rate": f"{passed}/{total}",
             "results": all_metrics},
            f, indent=2,
        )
    print(f"  Summary saved -> {summary_path}\n")
