"""
autochip_runner.py  --  AutoChipFinalTEST Edition  (FIXED v2)
Benchmarks LLM Verilog generation across 20 modules (4 difficulty tiers).
Supports: Ollama (local), Gemini (google-genai SDK), OpenAI (gpt-*)

Usage (run from AutoChipFinalTEST/ folder):
    python autochip_runner.py --model gemma3:4b
    python autochip_runner.py --model gemma3:12b  --level easy
    python autochip_runner.py --model qwen2.5-coder:14b
    python autochip_runner.py --model gemini-2.5-flash
    python autochip_runner.py --model gpt-4o-mini

FIXES APPLIED (v2):
  FIX-1  classify_error: detects "not a valid l-value" → reg_wire_mismatch
  FIX-2  run_verification: strips absolute Windows/Unix file paths from
         compiler errors before returning to LLM (path noise confuses models)
  FIX-3  autochip_loop: type-specific feedback hints appended to error msgs
  FIX-4  ripple_carry_adder spec: explicit "do NOT redefine full_adder"
  FIX-5  uart_tx spec: replaced $clog2() with fixed [7:0] width for baud_cnt
         ($clog2 in port-width context unsupported by older iverilog builds)
  FIX-6  pwm_generator spec: explicit "<" boundary (counter < duty_cycle)
  FIX-7  lfsr_8bit spec: explicit Galois tap positions (0-indexed bits 5,4,3)
  FIX-8  pipeline_mult_4x4 spec: explicit 2-stage latency (output valid N+2)
  FIX-9  Dependency resolver: already uses metrics.json → confirmed correct
"""

import os, subprocess, re, shutil, sys, json, time, argparse
from openai import OpenAI

# ── CONFIG ─────────────────────────────────────────────────────────────────────
MAX_RETRIES   = 5
TESTBENCH_DIR = "testbenches"
RESULTS_DIR   = "results"

OLLAMA_CLIENT = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

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
2. Outputs driven by sub-module instantiations MUST be declared as 'wire'.
3. ONLY use 'reg' if the signal is assigned inside an 'always' block.
4. Use only non-blocking assignments (<=) inside clocked always blocks.
5. Use blocking assignments (=) inside combinational always blocks.
6. Return ONLY Verilog code inside ```verilog ... ``` fences. No prose, no comments outside the fence, no non-ASCII characters anywhere.
7. When instantiating an external module (provided as a dependency), do NOT redefine it inside your file."""


# ── LLM CALL ──────────────────────────────────────────────────────────────────
def call_llm(model, messages):
    """Unified LLM caller: Ollama, Gemini, or OpenAI."""
    if model.startswith("gemini"):
        if not GEMINI_AVAILABLE:
            print("❌  Set GEMINI_API_KEY env var and pip install google-genai")
            sys.exit(1)
        history = "\n".join(
            f"[{'USER' if m['role']=='user' else 'ASSISTANT'}]\n{m['content']}"
            for m in messages if m["role"] != "system"
        )
        response = GEMINI_CLIENT.models.generate_content(
            model="models/gemini-2.5-flash",
            config=genai_types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.1
            ),
            contents=history
        )
        return response.text

    elif model.startswith("gpt-"):
        if not OPENAI_CLIENT:
            print("❌  Set OPENAI_API_KEY env var for OpenAI models")
            sys.exit(1)
        response = OPENAI_CLIENT.chat.completions.create(
            model=model, messages=messages, temperature=0.1
        )
        return response.choices[0].message.content

    else:
        # Ollama — gemma3:4b, gemma3:12b, qwen2.5-coder:7b/14b, deepseek-coder, etc.
        response = OLLAMA_CLIENT.chat.completions.create(
            model=model, messages=messages, temperature=0.1
        )
        return response.choices[0].message.content


def sanitize_for_ascii(text):
    """
    Remove non-ASCII characters from LLM output before writing to .v file.
    Small models (gemma3:4b) occasionally mix in Unicode/Hindi script
    which crashes Windows cp1252 writes and causes iverilog to reject the file.
    """
    return text.encode("ascii", errors="ignore").decode("ascii")


# ── FIX-2: path stripper ──────────────────────────────────────────────────────
_PATH_RE = re.compile(
    r"""(?:[A-Za-z]:[\\/]|[\\/])          # absolute root (Windows C:\ or Unix /)
        (?:[^\s:'"\\/<>|*?]+[\\/])*        # intermediate directories
        ([^\s:'"\\/<>|*?]+\.v)             # capture just the filename.v
    """,
    re.VERBOSE,
)

def strip_paths(text):
    """
    Replace absolute file paths in iverilog output with just the filename.
    Before: results\\gemma3_4b\\alu_8bit\\iter_3\\alu_8bit.v:11: error ...
    After : alu_8bit.v:11: error ...
    This prevents the LLM from getting confused by Windows/Unix paths it
    cannot act on, and keeps the feedback focused on the actual error.
    """
    return _PATH_RE.sub(r"\1", text)


# ── VERIFICATION ───────────────────────────────────────────────────────────────
def run_verification(iter_dir, module_name):
    """Compile all .v files in iter_dir together and simulate with iverilog/vvp."""
    log_file = os.path.join(iter_dir, "sim_log.txt")
    vvp_out  = os.path.join(iter_dir, "sim.vvp")
    v_files  = sorted(
        os.path.join(iter_dir, f)
        for f in os.listdir(iter_dir) if f.endswith(".v")
    )

    comp_cmd    = ["iverilog", "-o", vvp_out] + v_files
    comp_result = subprocess.run(comp_cmd, capture_output=True, text=True, encoding="utf-8")

    with open(log_file, "w", encoding="utf-8") as f:
        f.write(f"--- COMPILATION ---\n{comp_result.stderr}\n")
        if comp_result.returncode != 0:
            # FIX-2: strip paths BEFORE showing to user AND before sending to LLM
            err_clean = strip_paths(comp_result.stderr)
            err_preview = "\n".join(err_clean.strip().splitlines()[:8])
            print(f"  ⚙️  iverilog:\n    " + err_preview.replace("\n", "\n    "))
            return False, f"COMPILATION ERROR:\n{err_clean}"

        sim_result = subprocess.run(
            ["vvp", vvp_out], capture_output=True, text=True, encoding="utf-8"
        )
        output = sim_result.stdout + sim_result.stderr
        f.write(f"\n--- SIMULATION ---\n{output}\n")

    if "FAIL" in output or ("ALL TESTS PASSED" not in output and "PASS" not in output):
        sim_preview = "\n".join(output.strip().splitlines()[:6])
        print(f"  ⚙️  sim:\n    " + sim_preview.replace("\n", "\n    "))
        return False, f"SIMULATION FAILED:\n{output}"

    return True, output


# ── FIX-1: improved error classifier ─────────────────────────────────────────
def classify_error(feedback):
    """
    Classify the error type from iverilog/simulation feedback.
    FIX-1: Added 'not a valid l-value' and 'reg'+'wire' co-occurrence
           to catch reg/wire mismatch errors that iverilog reports differently
           from what was originally expected.
    """
    if "COMPILATION ERROR" in feedback:
        fb = feedback.lower()
        # FIX-1: iverilog says "X is not a valid l-value" for wire-driven-in-always errors
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
        if "is not a port" in fb or "unable to bind" in fb:
            return "port_mismatch"
        return "compile_other"
    if "SIMULATION FAILED" in feedback:
        return "logic_error" if "FAIL" in feedback else "sim_other"
    return "unknown"


# ── FIX-3: type-specific feedback hints ───────────────────────────────────────
_HINTS = {
    "reg_wire_mismatch": (
        "\nHINT: The error 'not a valid l-value' means a signal is declared "
        "as 'wire' but is being assigned inside an 'always' block. "
        "Change that signal's declaration from 'wire' to 'reg'. "
        "Remember: use 'wire' only for signals driven by 'assign' or sub-module "
        "output ports; use 'reg' for signals driven inside 'always' blocks."
    ),
    "duplicate_module": (
        "\nHINT: The error 'Module X was already declared' means you have defined "
        "a module that already exists in a separately compiled dependency file. "
        "Do NOT redefine or copy that module into your file. "
        "Only write the top-level module requested — the dependency is already compiled."
    ),
    "missing_module": (
        "\nHINT: A module you are trying to instantiate is not found. "
        "Check that you are using the exact module name and port names as specified. "
        "Do not rename the module. Do not inline a copy of it — it is provided externally."
    ),
    "port_mismatch": (
        "\nHINT: A port name in your module does not match what the testbench expects. "
        "Use EXACTLY the port names given in the specification. "
        "Do not rename, abbreviate, or change the case of any port name."
    ),
    "syntax_error": (
        "\nHINT: There is a Verilog syntax error. Common causes: "
        "(1) missing semicolons, (2) wrong keyword (e.g. 'begin'/'end' mismatch), "
        "(3) net declared twice, (4) using SystemVerilog syntax in Verilog-2001. "
        "Ensure you are writing strict Verilog-2001, not SystemVerilog."
    ),
    "logic_error": (
        "\nHINT: The module compiles but produces wrong simulation output. "
        "Read each FAIL line carefully — it shows the exact inputs and expected vs actual outputs. "
        "Fix the logic to match the expected values exactly."
    ),
}

def build_feedback_message(feedback, err_type):
    """Build the repair prompt with an error-type-specific hint appended."""
    hint = _HINTS.get(err_type, "")
    return (
        "The Verilog code you provided failed. "
        "Fix ALL errors below and return the COMPLETE corrected module "
        "inside a single ```verilog ... ``` block. "
        "Use only ASCII characters — no comments or text in any other language.\n\n"
        f"Error:\n{feedback}"
        f"{hint}"
    )


# ── MAIN LOOP ──────────────────────────────────────────────────────────────────
def autochip_loop(spec, module_name, model, dependencies=None):
    """
    Run AutoChip iterative loop for one module.
    Returns metrics dict. Returns None if testbench is missing.
    """
    if dependencies is None:
        dependencies = []

    tb_path = os.path.join(TESTBENCH_DIR, f"{module_name}_tb.v")
    if not os.path.exists(tb_path):
        print(f"  ❌ Missing testbench: {tb_path}")
        return None

    safe_model  = model.replace(":", "_").replace(".", "")
    project_dir = os.path.join(RESULTS_DIR, safe_model, module_name)
    os.makedirs(project_dir, exist_ok=True)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": spec},
    ]

    metrics = {
        "module":              module_name,
        "model":               model,
        "pass_at_1":           False,
        "iterations_to_pass":  None,
        "time_to_pass_sec":    None,
        "total_iterations":    MAX_RETRIES,
        "compile_errors":      0,
        "sim_errors":          0,
        "error_types":         [],
        "max_retries":         MAX_RETRIES,
    }

    print(f"\n{'='*60}")
    print(f"  AutoChip: {module_name}  |  Model: {model}")
    print(f"{'='*60}")
    t_start = time.time()

    for i in range(MAX_RETRIES):
        iter_dir = os.path.join(project_dir, f"iter_{i+1}")
        os.makedirs(iter_dir, exist_ok=True)
        print(f"\n  🔄 Iteration {i+1}/{MAX_RETRIES}")

        # ── Call LLM ────────────────────────────────────────────────────────
        t_llm = time.time()
        try:
            llm_output = call_llm(model, messages)
        except Exception as e:
            print(f"  ❌ LLM Error: {e}")
            break
        print(f"  🤖 LLM responded in {time.time()-t_llm:.1f}s")

        # ── Save raw response ────────────────────────────────────────────────
        raw_path = os.path.join(iter_dir, "raw_ai_response.txt")
        with open(raw_path, "w", encoding="utf-8") as f:
            f.write(llm_output)

        # ── Extract Verilog block ────────────────────────────────────────────
        match = re.search(r"```(?:verilog)?(.*?)```", llm_output, re.DOTALL)
        if match:
            code = match.group(1).strip()
        else:
            code = llm_output.strip()

        # Strip non-ASCII (fixes Windows cp1252 crash on gemma3 Hindi output)
        code = sanitize_for_ascii(code)

        # ── Write .v file ────────────────────────────────────────────────────
        v_path = os.path.join(iter_dir, f"{module_name}.v")
        with open(v_path, "w", encoding="utf-8") as f:
            f.write(code)

        # ── Copy dependencies and testbench into iter_dir ───────────────────
        for dep in dependencies:
            if os.path.exists(dep):
                shutil.copy(dep, iter_dir)
            else:
                print(f"  ⚠️  Dependency not found: {dep}")
        shutil.copy(tb_path, iter_dir)

        # ── Compile + simulate ───────────────────────────────────────────────
        success, feedback = run_verification(iter_dir, module_name)

        if success:
            elapsed = time.time() - t_start
            print(f"  ✅ PASSED on iteration {i+1}  ({elapsed:.1f}s total)")
            metrics.update({
                "pass_at_1":          True,
                "iterations_to_pass": i + 1,
                "time_to_pass_sec":   round(elapsed, 2),
                "total_iterations":   i + 1,
            })
            break
        else:
            err_type = classify_error(feedback)
            if "COMPILATION" in feedback:
                metrics["compile_errors"] += 1
            else:
                metrics["sim_errors"] += 1
            metrics["error_types"].append(err_type)
            print(f"  ❌ {err_type}  — sending feedback to LLM")

            # FIX-3: use type-specific hint in feedback message
            messages.append({"role": "assistant", "content": llm_output})
            messages.append({
                "role": "user",
                "content": build_feedback_message(feedback, err_type),
            })

    # ── Save per-module metrics ──────────────────────────────────────────────
    with open(os.path.join(project_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    if not metrics["pass_at_1"]:
        print(f"  ❌ FAILED after {MAX_RETRIES} iterations")

    return metrics


# ── BENCHMARK DEFINITION ───────────────────────────────────────────────────────
# 20 modules · 4 tiers.
BENCHMARK = {

    # ══════ L1 EASY ══════
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
    # FIX-4: added explicit "do NOT redefine full_adder" constraint
    "ripple_carry_adder": {
        "level": "easy", "deps": ["full_adder.v"],
        "spec": (
            "Create a Verilog-2001 module named 'ripple_carry_adder'.\n"
            "Ports: input [3:0] A, B; input cin; output [3:0] Sum; output cout\n"
            "CRITICAL: Do NOT define or redeclare the 'full_adder' module in this file. "
            "It is provided as a separately compiled dependency file. "
            "Only write the 'ripple_carry_adder' module — nothing else.\n"
            "Rules:\n"
            "1. Declare Sum [3:0] and cout as wire.\n"
            "2. Instantiate 'full_adder' four times: fa0, fa1, fa2, fa3.\n"
            "3. full_adder port names: .a .b .cin .sum .cout\n"
            "4. Connect carries: fa0.cout -> fa1.cin -> fa2.cin -> fa3.cin\n"
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
            "Use a combinational always block with a case statement.\n"
            "seg[6:0] = {a,b,c,d,e,f,g} active HIGH:\n"
            "  0->7'b1111110  1->7'b0110000  2->7'b1101101  3->7'b1111001\n"
            "  4->7'b0110011  5->7'b1011011  6->7'b1011111  7->7'b1110000\n"
            "  8->7'b1111111  9->7'b1111011  default->7'b0000000\n"
            "Declare seg as reg (driven in always block)."
        ),
    },
    "priority_enc_8": {
        "level": "easy", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'priority_enc_8'.\n"
            "Ports: input [7:0] in; output reg [2:0] out; output valid\n"
            "Logic:\n"
            "  valid = (|in)  -- use a continuous assign for this.\n"
            "  out encodes the index of the HIGHEST-numbered set bit (7 > 6 > ... > 0).\n"
            "  Use a combinational always @(*) block with an if-else chain:\n"
            "    if      (in[7]) out = 3'd7;\n"
            "    else if (in[6]) out = 3'd6;\n"
            "    ...continuing down...\n"
            "    else if (in[0]) out = 3'd0;\n"
            "    else            out = 3'd0;\n"
            "Declare out as reg, valid as wire.\n"
            "Do NOT use casez."
        ),
    },

    # ══════ L2 MEDIUM ══════
    "alu_8bit": {
        "level": "medium", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'alu_8bit'.\n"
            "Ports: input [7:0] A, B; input [2:0] op; output reg [7:0] result; output wire zero\n"
            "Operations (use a combinational always block with case):\n"
            "  3'b000 ADD:   result = A + B;\n"
            "  3'b001 SUB:   result = A - B;\n"
            "  3'b010 AND:   result = A & B;\n"
            "  3'b011 OR:    result = A | B;\n"
            "  3'b100 XOR:   result = A ^ B;\n"
            "  3'b101 NOT_A: result = ~A;\n"
            "  3'b110 SHL:   result = A << 1;\n"
            "  3'b111 SHR:   result = A >> 1;\n"
            "  default:      result = 8'h00;\n"
            "Declare result as reg, zero as wire.\n"
            "assign zero = (result == 8'h00);"
        ),
    },
    "dff_sync_reset": {
        "level": "medium", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'dff_sync_reset'.\n"
            "Ports: input clk, rst, d; output reg q\n"
            "Logic: D flip-flop with synchronous active-high reset.\n"
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
            "Logic: 4-bit unsigned up-counter, synchronous active-high reset.\n"
            "  always @(posedge clk) begin\n"
            "    if (rst) count <= 4'b0;\n"
            "    else     count <= count + 1'b1;\n"
            "  end\n"
            "Declare count as reg. Wraps naturally 15->0."
        ),
    },
    # FIX-7: explicit polynomial tap positions (0-indexed) to eliminate ambiguity
    "lfsr_8bit": {
        "level": "medium", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'lfsr_8bit'.\n"
            "Ports: input clk, rst, load, enable; input [7:0] seed; output reg [7:0] lfsr_out\n"
            "Logic: 8-bit Galois LFSR, polynomial x^8+x^6+x^5+x^4+1.\n"
            "Galois LFSR tap positions (0-indexed): bits 5, 4, 3 receive feedback XOR.\n"
            "The feedback bit is lfsr_out[0] (LSB before shift).\n"
            "Priority (synchronous, in always @(posedge clk)):\n"
            "  1. if (rst)         lfsr_out <= 8'hFF;\n"
            "  2. else if (load)   lfsr_out <= seed;\n"
            "  3. else if (enable) begin\n"
            "       // Right-shift with Galois feedback\n"
            "       lfsr_out <= { lfsr_out[0],         // bit 7 (MSB) gets feedback\n"
            "                     lfsr_out[7:6],        // bits 6:5 shift right\n"
            "                     lfsr_out[5] ^ lfsr_out[0],  // bit 4 XOR feedback (tap x^6)\n"
            "                     lfsr_out[4] ^ lfsr_out[0],  // bit 3 XOR feedback (tap x^5)\n"
            "                     lfsr_out[3] ^ lfsr_out[0],  // bit 2 XOR feedback (tap x^4)\n"
            "                     lfsr_out[2:1] };      // bits 1:0 shift right\n"
            "     end\n"
            "  4. else hold value (no change).\n"
            "Declare lfsr_out as reg."
        ),
    },
    # FIX-6: explicit '<' boundary condition for pwm_out
    "pwm_generator": {
        "level": "medium", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'pwm_generator'.\n"
            "Ports: input clk, rst; input [7:0] duty_cycle; output wire pwm_out\n"
            "Logic:\n"
            "  Internal 8-bit counter counts 0..255 and wraps (free-running).\n"
            "  Synchronous active-high reset: counter <= 0.\n"
            "  always @(posedge clk) begin\n"
            "    if (rst) counter <= 8'd0;\n"
            "    else     counter <= counter + 1'b1;\n"
            "  end\n"
            "  assign pwm_out = (counter < duty_cycle);   // STRICTLY less than\n"
            "  pwm_out is HIGH when counter < duty_cycle, LOW when counter >= duty_cycle.\n"
            "  Example: duty_cycle=4 means pwm_out is HIGH for counter values 0,1,2,3\n"
            "           and LOW for counter values 4,5,...,255.\n"
            "Declare counter as reg [7:0]. Declare pwm_out as wire."
        ),
    },
    "gray_counter_4bit": {
        "level": "medium", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'gray_counter_4bit'.\n"
            "Ports: input clk, rst; output wire [3:0] gray_out\n"
            "Logic:\n"
            "  Internal 4-bit binary up-counter (counts 0..15, wraps).\n"
            "  Synchronous active-high reset sets binary counter to 0.\n"
            "  always @(posedge clk) begin\n"
            "    if (rst) bin <= 4'b0;\n"
            "    else     bin <= bin + 1'b1;\n"
            "  end\n"
            "  Gray encode: assign gray_out = bin ^ (bin >> 1);\n"
            "Declare internal counter as reg [3:0] bin. Declare gray_out as wire."
        ),
    },

    # ══════ L3 HARD ══════
    "simple_cpu_alu": {
        "level": "hard", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'simple_cpu_alu'.\n"
            "Ports: input [3:0] A, B; input [1:0] op; output reg [3:0] result; output wire zero\n"
            "Use a combinational always @(*) block with case:\n"
            "  2'b00 ADD: result = A + B; (4-bit, wraps)\n"
            "  2'b01 SUB: result = A - B; (4-bit, wraps)\n"
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
            "Logic: Mealy FSM detecting bit sequence 1011 on input 'in'.\n"
            "States (reg [1:0] state): S0=0, S1=1, S2=2, S3=3\n"
            "State transitions (synchronous, posedge clk, sync reset to S0):\n"
            "  S0: in=0->S0,  in=1->S1\n"
            "  S1: in=0->S2,  in=1->S1\n"
            "  S2: in=0->S0,  in=1->S3\n"
            "  S3: in=0->S2,  in=1->S1  (detected fires here; trailing 1 reused)\n"
            "Combinational output: assign detected = (state == 2'd3) & in;\n"
            "Declare state as reg [1:0], detected as wire."
        ),
    },
    # FIX-5: replaced $clog2(BAUD_DIV) with fixed [7:0] (iverilog compat)
    "uart_tx": {
        "level": "hard", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'uart_tx'.\n"
            "Parameter: BAUD_DIV = 104\n"
            "Ports: input clk, rst, start; input [7:0] data_in;\n"
            "       output reg tx_out, busy, done\n"
            "Logic: UART 8N1 transmitter.\n"
            "Frame: 1 start bit (0) + 8 data bits LSB-first + 1 stop bit (1).\n"
            "Each bit lasts exactly BAUD_DIV clock cycles.\n"
            "FSM states (reg [2:0]): IDLE=0, START=1, DATA=2, STOP=3, DONE=4\n"
            "Behavior:\n"
            "  IDLE:  tx_out=1, busy=0, done=0. On start=1 -> latch data_in -> goto START.\n"
            "  START: tx_out=0, busy=1. Count BAUD_DIV clocks then goto DATA, bit_cnt=0.\n"
            "  DATA:  busy=1. Shift data LSB-first: tx_out = shift_reg[0].\n"
            "         Count BAUD_DIV clocks per bit. After 8 bits goto STOP.\n"
            "  STOP:  tx_out=1, busy=1. Count BAUD_DIV clocks then goto DONE.\n"
            "  DONE:  done=1 for 1 cycle, busy=0, tx_out=1. goto IDLE.\n"
            "Internal regs: shift_reg [7:0], baud_cnt [7:0], bit_cnt [3:0]\n"
            "IMPORTANT: Declare baud_cnt as 'reg [7:0]' — do NOT use $clog2().\n"
            "Use non-blocking assignments (<=) throughout the clocked always block."
        ),
    },
    "sync_fifo_8": {
        "level": "hard", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'sync_fifo_8'.\n"
            "Ports: input clk, rst, wr_en, rd_en; input [7:0] din;\n"
            "       output reg [7:0] dout; output wire full, empty\n"
            "Spec: Synchronous FIFO, 8 entries x 8-bit wide.\n"
            "Internal: reg [7:0] mem [0:7]; reg [3:0] wr_ptr, rd_ptr; (4-bit each)\n"
            "  empty = (wr_ptr == rd_ptr)\n"
            "  full  = (wr_ptr[2:0] == rd_ptr[2:0]) && (wr_ptr[3] != rd_ptr[3])\n"
            "Synchronous (posedge clk):\n"
            "  if rst: wr_ptr<=0; rd_ptr<=0; dout<=0;\n"
            "  else:\n"
            "    if (wr_en && !full):  mem[wr_ptr[2:0]] <= din; wr_ptr <= wr_ptr+1;\n"
            "    if (rd_en && !empty): dout <= mem[rd_ptr[2:0]]; rd_ptr <= rd_ptr+1;\n"
            "Declare dout as reg. Declare full, empty as wire."
        ),
    },
    "alu_accumulator_top": {
        "level": "hard", "deps": ["alu_8bit.v"],
        "spec": (
            "Create a Verilog-2001 module named 'alu_accumulator_top'.\n"
            "Ports: input clk, rst; input [7:0] data_in; input [2:0] op; input load_acc;\n"
            "       output wire [7:0] acc_out; output wire zero\n"
            "CRITICAL: Do NOT redefine 'alu_8bit' — it is provided as a dependency file.\n"
            "Internal wires: wire [7:0] alu_result;\n"
            "Instantiate 'alu_8bit' as u_alu:\n"
            "  .A(acc_out), .B(data_in), .op(op), .result(alu_result), .zero(zero)\n"
            "Accumulator register (reg [7:0] acc):\n"
            "  always @(posedge clk) begin\n"
            "    if (rst)           acc <= 8'h00;\n"
            "    else if (load_acc) acc <= data_in;\n"
            "    else               acc <= alu_result;\n"
            "  end\n"
            "assign acc_out = acc;\n"
            "Declare acc as reg [7:0], alu_result as wire [7:0], acc_out/zero as wire."
        ),
    },

    # ══════ L4 CRITICAL ══════
    "param_register_file": {
        "level": "critical", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'param_register_file'.\n"
            "Parameters: N = 4, W = 8\n"
            "Ports: input clk, wr_en;\n"
            "       input  [1:0] wr_addr, rd_addr;\n"
            "       input  [W-1:0] wr_data;\n"
            "       output wire [W-1:0] rd_data\n"
            "CRITICAL: Use N and W in the memory declaration, not literal numbers.\n"
            "  reg [W-1:0] mem [0:N-1];\n"
            "Write (synchronous):\n"
            "  always @(posedge clk) if (wr_en) mem[wr_addr] <= wr_data;\n"
            "Read (combinational):\n"
            "  assign rd_data = mem[rd_addr];\n"
            "Declare rd_data as wire."
        ),
    },
    # FIX-8: explicit 2-stage pipeline timing and latency description
    "pipeline_mult_4x4": {
        "level": "critical", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'pipeline_mult_4x4'.\n"
            "Ports: input clk; input [3:0] a, b; output reg [7:0] product\n"
            "Logic: 2-stage pipelined 4x4 unsigned multiplier.\n"
            "PIPELINE TIMING: This is a strictly 2-stage pipeline.\n"
            "  Stage 1 register (reg [3:0] a_r, b_r): captures inputs on posedge clk.\n"
            "  Stage 2 register (output reg [7:0] product): captures (a_r * b_r) on posedge clk.\n"
            "  Inputs presented at cycle N will appear at 'product' at cycle N+2.\n"
            "  The testbench checks product at exactly cycle N+2 — not N+1.\n"
            "Both stages update in ONE always block on the SAME posedge clk:\n"
            "  always @(posedge clk) begin\n"
            "    a_r     <= a;        // Stage 1: latch inputs\n"
            "    b_r     <= b;\n"
            "    product <= a_r * b_r; // Stage 2: multiply latched inputs\n"
            "  end\n"
            "Do NOT compute the product combinationally. Do NOT use separate always blocks."
        ),
    },
    "spi_master_8bit": {
        "level": "critical", "deps": [],
        "spec": (
            "Create a Verilog-2001 module named 'spi_master_8bit'.\n"
            "Parameter: CLK_DIV = 4\n"
            "Ports: input clk, rst, start; input [7:0] mosi_data; input miso;\n"
            "       output reg sclk, cs_n, mosi, done; output reg [7:0] miso_capture\n"
            "Logic: SPI master mode 0 (CPOL=0 CPHA=0), 8-bit MSB-first transfer.\n"
            "FSM states (reg [1:0]): IDLE=0, ACTIVE=1, DONE_ST=2\n"
            "Internal: reg [7:0] shift_out, shift_in; reg [3:0] clk_cnt, bit_cnt;\n"
            "Idle state: cs_n=1, sclk=0, done=0.\n"
            "On start (from IDLE): cs_n<=0; shift_out<=mosi_data; bit_cnt<=0; clk_cnt<=0; goto ACTIVE.\n"
            "ACTIVE state: count CLK_DIV clocks per half-period.\n"
            "  First half (clk_cnt < CLK_DIV): sclk=0, drive mosi=shift_out[7].\n"
            "  At clk_cnt==CLK_DIV-1: sclk<=1 (rising edge).\n"
            "  Second half (CLK_DIV <= clk_cnt < 2*CLK_DIV-1): sclk=1.\n"
            "  At clk_cnt==2*CLK_DIV-2: sample miso into shift_in, shift_in<={shift_in[6:0],miso}.\n"
            "  At clk_cnt==2*CLK_DIV-1: sclk<=0; shift_out<={shift_out[6:0],1'b0};\n"
            "    clk_cnt<=0; bit_cnt<=bit_cnt+1.\n"
            "  When bit_cnt==8: cs_n<=1; miso_capture<=shift_in; goto DONE_ST.\n"
            "DONE_ST: done<=1 for 1 cycle; goto IDLE."
        ),
    },
}


# ── CLI ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AutoChip benchmark — AutoChipFinalTEST v2 (FIXED)")
    parser.add_argument("--model",  default="gemma3:4b",
                        help="Model name. Ollama: gemma3:4b, gemma3:12b, qwen2.5-coder:14b, etc.")
    parser.add_argument("--module", default=None,
                        help="Single module name, or omit for all")
    parser.add_argument("--level",  default=None,
                        choices=["easy", "medium", "hard", "critical"],
                        help="Run only modules of this difficulty tier")
    parser.add_argument("--deps",   nargs="*", default=None,
                        help="Override dependency .v paths for single-module run")
    args = parser.parse_args()

    # ── Filter benchmark ────────────────────────────────────────────────────
    items = list(BENCHMARK.items())
    if args.level:
        items = [(k, v) for k, v in items if v.get("level") == args.level]
    if args.module and args.module != "all":
        items = [(k, v) for k, v in items if k == args.module]

    if not items:
        print(f"❌ No modules matched (module={args.module}, level={args.level})")
        sys.exit(1)

    # ── Single module shortcut ──────────────────────────────────────────────
    if len(items) == 1 and args.module and args.module != "all":
        mod_name, config = items[0]
        deps = args.deps if args.deps else config["deps"]
        autochip_loop(config["spec"], mod_name, args.model, deps)
        sys.exit(0)

    # ── Batch run ───────────────────────────────────────────────────────────
    print(f"\n🚀 Running benchmark | Model: {args.model}"
          + (f" | Level: {args.level}" if args.level else ""))
    all_metrics  = []
    safe_model   = args.model.replace(":", "_").replace(".", "")

    for mod_name, config in items:
        # FIX-9 (confirmed): resolve dependency from the PASSING iteration's file
        dep_files = []
        for dep in config["deps"]:
            dep_module  = dep.replace(".v", "")
            dep_results = os.path.join(RESULTS_DIR, safe_model, dep_module)
            found = False
            metrics_f = os.path.join(dep_results, "metrics.json")
            if os.path.exists(metrics_f):
                try:
                    with open(metrics_f, encoding="utf-8") as mf:
                        dep_metrics = json.load(mf)
                    itp = dep_metrics.get("iterations_to_pass")
                    if itp:
                        candidate = os.path.join(dep_results, f"iter_{itp}", dep)
                        if os.path.exists(candidate):
                            dep_files.append(candidate)
                            found = True
                except Exception:
                    pass
            if not found:
                print(f"  ⚠️  Dependency {dep} not found for {mod_name} "
                      f"(did the dependency module pass?)")

        m = autochip_loop(config["spec"], mod_name, args.model, dep_files)
        if m:
            all_metrics.append(m)

    # ── Summary table ───────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  SUMMARY — Model: {args.model}")
    print(f"{'='*65}")
    print(f"  {'Module':<28} {'Lvl':<8} {'Pass':>5} {'Iters':>6} {'Time(s)':>8} {'CE':>4} {'SE':>4}")
    print(f"  {'-'*28} {'-'*8} {'-'*5} {'-'*6} {'-'*8} {'-'*4} {'-'*4}")

    passed = 0
    for m in all_metrics:
        lvl  = BENCHMARK[m["module"]].get("level", "?")[:6]
        p    = "✓" if m["pass_at_1"] else "✗"
        it   = str(m["iterations_to_pass"]) if m["iterations_to_pass"] else "-"
        t    = str(m["time_to_pass_sec"])   if m["time_to_pass_sec"]   else "-"
        print(f"  {m['module']:<28} {lvl:<8} {p:>5} {it:>6} {t:>8} "
              f"{m['compile_errors']:>4} {m['sim_errors']:>4}")
        if m["pass_at_1"]:
            passed += 1

    pct = 100 * passed // max(len(all_metrics), 1)
    print(f"\n  Pass@1: {passed}/{len(all_metrics)} = {pct}%")

    # Save combined summary
    summary_path = os.path.join(RESULTS_DIR, safe_model, "summary.json")
    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({"model": args.model, "results": all_metrics}, f, indent=2)
    print(f"  Summary → {summary_path}\n")
