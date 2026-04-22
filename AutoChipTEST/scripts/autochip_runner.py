"""
autochip_runner.py  --  Enhanced AutoChip with metrics logging
Drop this into AutoChipTEST/ and run from there.

Usage:
    python scripts/autochip_runner.py --model qwen2.5-coder:14b --module half_adder
    python scripts/autochip_runner.py --model llama3.1 --module ripple_carry_adder --deps full_adder.v
    python scripts/run_all.py   <- runs full benchmark suite on all configured models
"""

import os, subprocess, re, shutil, sys, json, time, argparse
from openai import OpenAI

# ── CONFIG ──────────────────────────────────────────────────────────────────────
MAX_RETRIES = 5
TESTBENCH_DIR = "testbenches"
RESULTS_DIR   = "results"

OLLAMA_CLIENT = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

# Gemini adapter (if you have a key)
try:
    import google.generativeai as genai
    GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
    if GEMINI_KEY:
        genai.configure(api_key=GEMINI_KEY)
    GEMINI_AVAILABLE = bool(GEMINI_KEY)
except ImportError:
    GEMINI_AVAILABLE = False

SYSTEM_PROMPT = """You are a Verilog-2001 Expert.
STRICT RULES:
1. Outputs driven by 'assign' statements MUST be declared as 'wire'.
2. Outputs driven by sub-module instantiations MUST be declared as 'wire'.
3. ONLY use 'reg' if the signal is assigned inside an 'always' block.
4. Use only non-blocking assignments (<=) inside clocked always blocks.
5. Use blocking assignments (=) inside combinational always blocks.
6. Return ONLY code inside ```verilog blocks. No explanation outside the block."""

# ── LLM CALL ────────────────────────────────────────────────────────────────────
def call_llm(model, messages):
    """Unified LLM caller. Handles Ollama models and gemini-flash."""
    if model.startswith("gemini"):
        if not GEMINI_AVAILABLE:
            print("❌ Gemini not configured. Set GEMINI_API_KEY env var and pip install google-generativeai")
            sys.exit(1)
        # Build flat string from messages for Gemini
        history = ""
        for m in messages:
            role = "USER" if m["role"] == "user" else "ASSISTANT"
            history += f"\n[{role}]\n{m['content']}\n"
        gemini_model = genai.GenerativeModel("gemini-2.0-flash")
        resp = gemini_model.generate_content(history)
        return resp.text
    else:
        # Ollama (OpenAI-compatible)
        response = OLLAMA_CLIENT.chat.completions.create(
            model=model, messages=messages, temperature=0.1
        )
        return response.choices[0].message.content

# ── VERIFICATION ─────────────────────────────────────────────────────────────────
def run_verification(iter_dir, module_name):
    """Compile ALL .v files in iter_dir together and simulate."""
    log_file = os.path.join(iter_dir, "sim_log.txt")
    vvp_out  = os.path.join(iter_dir, "sim.vvp")
    v_files  = [os.path.join(iter_dir, f) for f in os.listdir(iter_dir) if f.endswith('.v')]

    comp_cmd    = ["iverilog", "-o", vvp_out] + v_files
    comp_result = subprocess.run(comp_cmd, capture_output=True, text=True)

    with open(log_file, "w") as f:
        f.write(f"--- COMPILATION ---\n{comp_result.stderr}\n")
        if comp_result.returncode != 0:
            return False, f"COMPILATION ERROR:\n{comp_result.stderr}"

        sim_result = subprocess.run(["vvp", vvp_out], capture_output=True, text=True)
        output = sim_result.stdout
        f.write(f"\n--- SIMULATION ---\n{output}\n")

    if "FAIL" in output or ("ALL TESTS PASSED" not in output and "PASS" not in output):
        return False, f"SIMULATION FAILED:\n{output}"
    return True, output

def classify_error(feedback):
    """Classify the type of error for metrics."""
    if "COMPILATION ERROR" in feedback:
        if "reg" in feedback and ("driven by" in feedback or "continuous" in feedback):
            return "reg_wire_mismatch"
        if "undefined" in feedback or "Unknown module" in feedback:
            return "missing_module"
        return "compile_other"
    if "SIMULATION FAILED" in feedback:
        if "FAIL" in feedback:
            return "logic_error"
        return "sim_other"
    return "unknown"

# ── MAIN LOOP ────────────────────────────────────────────────────────────────────
def autochip_loop(spec, module_name, model, dependencies=None):
    """
    Returns: dict with keys pass_at_1, iterations_to_pass, time_to_pass_sec,
             compile_errors, sim_errors, error_types
    """
    if dependencies is None:
        dependencies = []

    tb_filename = f"{module_name}_tb.v"
    tb_path = os.path.join(TESTBENCH_DIR, tb_filename)

    if not os.path.exists(tb_path):
        print(f"❌ Missing testbench: {tb_path}")
        return None

    # Result folder: results/<model>/<module>/
    safe_model = model.replace(":", "_").replace(".", "")
    project_dir = os.path.join(RESULTS_DIR, safe_model, module_name)
    os.makedirs(project_dir, exist_ok=True)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": spec}
    ]

    metrics = {
        "module":       module_name,
        "model":        model,
        "pass_at_1":    False,
        "iterations_to_pass": None,
        "time_to_pass_sec":   None,
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

    for i in range(MAX_RETRIES):
        iter_dir = os.path.join(project_dir, f"iter_{i+1}")
        os.makedirs(iter_dir, exist_ok=True)
        print(f"\n  🔄 Iteration {i+1}/{MAX_RETRIES}")

        # Call LLM
        t_llm = time.time()
        try:
            llm_output = call_llm(model, messages)
        except Exception as e:
            print(f"  ❌ LLM Error: {e}")
            break
        llm_time = time.time() - t_llm
        print(f"  🤖 LLM responded in {llm_time:.1f}s")

        # Extract code
        match = re.search(r"```(?:verilog)?(.*?)```", llm_output, re.DOTALL)
        code  = match.group(1).strip() if match else llm_output.strip()

        # Save files
        with open(os.path.join(iter_dir, f"{module_name}.v"), "w") as f:
            f.write(code)
        with open(os.path.join(iter_dir, "raw_ai_response.txt"), "w") as f:
            f.write(llm_output)

        # Copy dependencies and testbench
        for dep in dependencies:
            if os.path.exists(dep):
                shutil.copy(dep, iter_dir)
            else:
                print(f"  ⚠️  Dependency not found: {dep}")
        shutil.copy(tb_path, iter_dir)

        # Verify
        success, feedback = run_verification(iter_dir, module_name)

        if success:
            elapsed = time.time() - t_start
            print(f"  ✅ PASSED on iteration {i+1}  ({elapsed:.1f}s total)")
            metrics["pass_at_1"]    = True
            metrics["iterations_to_pass"]  = i + 1
            metrics["time_to_pass_sec"]    = round(elapsed, 2)
            metrics["total_iterations"]    = i + 1
            break
        else:
            err_type = classify_error(feedback)
            if "COMPILATION" in feedback:
                metrics["compile_errors"] += 1
            else:
                metrics["sim_errors"] += 1
            metrics["error_types"].append(err_type)
            print(f"  ❌ {err_type}  — sending feedback to LLM")
            messages.append({"role": "assistant", "content": llm_output})
            messages.append({"role": "user",
                "content": f"The code failed. Fix all errors and return the complete corrected module.\nError:\n{feedback}"})

    # Save metrics
    metrics_path = os.path.join(project_dir, "metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    if not metrics["pass_at_1"]:
        print(f"  ❌ FAILED after {MAX_RETRIES} iterations")

    return metrics


# ── SPECS ────────────────────────────────────────────────────────────────────────
BENCHMARK = {
    # L1 Combinational
    "half_adder": {
        "deps": [],
        "spec": """Create a Verilog-2001 module 'half_adder'.
Ports: input a, b; output sum, cout
Logic: assign sum = a ^ b; assign cout = a & b;
Declare sum and cout as wire."""
    },
    "full_adder": {
        "deps": [],
        "spec": """Create a Verilog-2001 module 'full_adder'.
Ports: input a, b, cin; output sum, cout
Logic: Use continuous assign statements only.
  sum = a ^ b ^ cin
  cout = (a & b) | (b & cin) | (a & cin)
Declare sum and cout as wire."""
    },
    "ripple_carry_adder": {
        "deps": ["full_adder.v"],
        "spec": """Create a Verilog-2001 module 'ripple_carry_adder'.
Ports: input [3:0] A, B; input cin; output [3:0] Sum; output cout
HARDWARE CONSTRAINTS:
1. Declare Sum and cout as WIRE (not reg).
2. Instantiate 'full_adder' four times: fa0, fa1, fa2, fa3.
3. full_adder ports: .a, .b, .cin, .sum, .cout
4. Chain: fa0.cout -> fa1.cin -> fa2.cin -> fa3.cin
5. fa0.cin = cin (module input)"""
    },
    "alu_8bit": {
        "deps": [],
        "spec": """Create a Verilog-2001 module 'alu_8bit'.
Ports: input [7:0] A, B; input [2:0] op; output [7:0] result; output zero
Operations (op):
  3'b000 = ADD:   result = A + B
  3'b001 = SUB:   result = A - B
  3'b010 = AND:   result = A & B
  3'b011 = OR:    result = A | B
  3'b100 = XOR:   result = A ^ B
  3'b101 = NOT_A: result = ~A
  3'b110 = SHL:   result = A << 1
  3'b111 = SHR:   result = A >> 1
zero flag: zero = (result == 0)
Use a combinational always block with case statement. Declare result as reg, zero as wire."""
    },
    # L2 Sequential
    "dff_sync_reset": {
        "deps": [],
        "spec": """Create a Verilog-2001 module 'dff_sync_reset'.
Ports: input clk, rst, d; output q
Logic: D flip-flop with synchronous active-high reset.
  On posedge clk: if rst then q <= 0; else q <= d;
Declare q as reg."""
    },
    "counter_4bit": {
        "deps": [],
        "spec": """Create a Verilog-2001 module 'counter_4bit'.
Ports: input clk, rst; output [3:0] count
Logic: 4-bit up counter, synchronous active-high reset.
  On posedge clk: if rst then count <= 0; else count <= count + 1;
Declare count as reg."""
    },
    # L3 FSM
    "fsm_seq_detector": {
        "deps": [],
        "spec": """Create a Verilog-2001 module 'fsm_seq_detector'.
Ports: input clk, rst, in; output detected
Logic: Mealy FSM that detects the sequence 1011 on the 'in' input.
  Set detected=1 in the clock cycle when the last bit of the sequence is received.
  Use 4 states: S0 (idle), S1 (got 1), S2 (got 10), S3 (got 101).
  Synchronous active-high reset returns to S0.
  Overlapping sequences should be detected.
Declare detected as reg."""
    },
    # L4 Processor components
    "simple_cpu_alu": {
        "deps": [],
        "spec": """Create a Verilog-2001 module 'simple_cpu_alu'.
Ports: input [3:0] A, B; input [1:0] op; output [3:0] result; output zero
Operations:
  2'b00 = ADD: result = A + B (4-bit, wraps on overflow)
  2'b01 = SUB: result = A - B (4-bit, wraps)
  2'b10 = AND: result = A & B
  2'b11 = OR:  result = A | B
zero = (result == 4'b0000)
Use combinational always block. Declare result as reg, zero as wire."""
    },
}


# ── CLI ──────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AutoChip runner with metrics")
    parser.add_argument("--model",  default="qwen2.5-coder:14b", help="Ollama model name or 'gemini-flash'")
    parser.add_argument("--module", default=None, help="Module name from BENCHMARK dict (or 'all')")
    parser.add_argument("--deps",   nargs="*", default=None, help="Dependency .v file paths")
    args = parser.parse_args()

    if args.module == "all" or args.module is None:
        print(f"\n🚀 Running full benchmark suite on model: {args.model}")
        all_metrics = []
        for mod_name, config in BENCHMARK.items():
            # Find passing dependency files from results
            dep_files = []
            safe_model = args.model.replace(":", "_").replace(".", "")
            for dep in config["deps"]:
                # Try to find the passing iteration file
                dep_module = dep.replace(".v", "")
                dep_results = os.path.join(RESULTS_DIR, safe_model, dep_module)
                found = False
                if os.path.exists(dep_results):
                    for iter_folder in sorted(os.listdir(dep_results)):
                        candidate = os.path.join(dep_results, iter_folder, dep)
                        metrics_f = os.path.join(dep_results, iter_folder, "..", "metrics.json")
                        if os.path.exists(candidate):
                            # Use the file from the passing iteration
                            dep_files.append(candidate)
                            found = True
                            break
                if not found and os.path.exists(dep):
                    dep_files.append(dep)  # fallback to root
            
            m = autochip_loop(config["spec"], mod_name, args.model, dep_files)
            if m:
                all_metrics.append(m)

        # Print summary table
        print(f"\n{'='*60}")
        print(f"  SUMMARY — Model: {args.model}")
        print(f"{'='*60}")
        print(f"  {'Module':<28} {'Pass':>5} {'Iters':>6} {'Time(s)':>8} {'CE':>4} {'SE':>4}")
        print(f"  {'-'*28} {'-'*5} {'-'*6} {'-'*8} {'-'*4} {'-'*4}")
        passed = 0
        for m in all_metrics:
            p = "✓" if m["pass_at_1"] else "✗"
            it = str(m["iterations_to_pass"]) if m["iterations_to_pass"] else "-"
            t  = str(m["time_to_pass_sec"])   if m["time_to_pass_sec"]   else "-"
            print(f"  {m['module']:<28} {p:>5} {it:>6} {t:>8} {m['compile_errors']:>4} {m['sim_errors']:>4}")
            if m["pass_at_1"]:
                passed += 1
        print(f"\n  Pass@1: {passed}/{len(all_metrics)} = {100*passed//max(len(all_metrics),1)}%")

    else:
        config = BENCHMARK.get(args.module)
        if not config:
            print(f"Unknown module '{args.module}'. Available: {list(BENCHMARK.keys())}")
            sys.exit(1)
        deps = args.deps if args.deps else config["deps"]
        autochip_loop(config["spec"], args.module, args.model, deps)
