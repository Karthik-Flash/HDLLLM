import os, subprocess, re, shutil, sys, json, time, argparse
from google import genai
from google.genai import types

MAX_RETRIES   = 5
TESTBENCH_DIR = "testbenches"
RESULTS_DIR   = "results"
MODEL_NAME = "models/gemini-2.5-flash"
SAFE_NAME  = "gemini_2_5_flash"

API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not API_KEY:
    print("GEMINI_API_KEY not set. Run: set GEMINI_API_KEY=AIzaSyBFjgr3px0aDDnD101ixYZeKJghiho3VCo")
    sys.exit(1)

SYSTEM_PROMPT = """You are a Verilog-2001 Expert.
STRICT RULES:
1. Outputs driven by assign statements MUST be declared as wire.
2. Outputs driven by sub-module instantiations MUST be declared as wire.
3. ONLY use reg if the signal is assigned inside an always block.
4. Use only non-blocking assignments (<=) inside clocked always blocks.
5. Use blocking assignments (=) inside combinational always blocks.
6. Return ONLY code inside verilog blocks. No explanation outside the block.
7. Do NOT use SystemVerilog syntax (no typedef enum, no logic type).
8. Use localparam for state declarations."""

def call_gemini(messages, max_api_retries=3):
    client = genai.Client(api_key=API_KEY)
    contents = []
    non_system = [m for m in messages if m["role"] != "system"]
    for m in non_system:
        role = "user" if m["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=m["content"])]))
    delay = 5
    for attempt in range(max_api_retries):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, temperature=0.1),
                contents=contents
            )
            return response.text
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower() or "exhausted" in str(e).lower():
                print(f"  Rate limit hit. Waiting {delay}s...")
                time.sleep(delay)
                delay *= 2
            else:
                print(f"  Gemini API error: {e}")
                raise
    raise Exception("Max retries exceeded.")

def run_verification(iter_dir, module_name):
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
    if "COMPILATION ERROR" in feedback:
        if "reg" in feedback and ("driven by" in feedback or "continuous" in feedback):
            return "reg_wire_mismatch"
        if "undefined" in feedback or "Unknown module" in feedback:
            return "missing_module"
        return "compile_other"
    if "SIMULATION FAILED" in feedback:
        return "logic_error"
    return "unknown"

def autochip_loop(spec, module_name, dependencies=None):
    if dependencies is None:
        dependencies = []
    tb_path = os.path.join(TESTBENCH_DIR, f"{module_name}_tb.v")
    if not os.path.exists(tb_path):
        print(f"Missing testbench: {tb_path}")
        return None
    project_dir = os.path.join(RESULTS_DIR, SAFE_NAME, module_name)
    os.makedirs(project_dir, exist_ok=True)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": spec}]
    metrics = {"module": module_name, "model": MODEL_NAME, "pass_at_1": False,
               "iterations_to_pass": None, "time_to_pass_sec": None,
               "total_iterations": MAX_RETRIES, "compile_errors": 0,
               "sim_errors": 0, "error_types": [], "max_retries": MAX_RETRIES}
    print(f"\n{'='*60}")
    print(f"  AutoChip: {module_name}  |  Model: {MODEL_NAME}")
    print(f"{'='*60}")
    t_start = time.time()
    for i in range(MAX_RETRIES):
        iter_dir = os.path.join(project_dir, f"iter_{i+1}")
        os.makedirs(iter_dir, exist_ok=True)
        print(f"\n  Iteration {i+1}/{MAX_RETRIES}")
        t_llm = time.time()
        try:
            llm_output = call_gemini(messages)
        except Exception as e:
            print(f"  Stopping: {e}")
            break
        print(f"  Gemini responded in {time.time()-t_llm:.1f}s")
        match = re.search(r"```(?:verilog)?(.*?)```", llm_output, re.DOTALL)
        code  = match.group(1).strip() if match else llm_output.strip()
        with open(os.path.join(iter_dir, f"{module_name}.v"), "w") as f: f.write(code)
        with open(os.path.join(iter_dir, "raw_ai_response.txt"), "w") as f: f.write(llm_output)
        for dep in dependencies:
            if os.path.exists(dep): shutil.copy(dep, iter_dir)
        shutil.copy(tb_path, iter_dir)
        success, feedback = run_verification(iter_dir, module_name)
        if success:
            elapsed = round(time.time() - t_start, 2)
            print(f"  PASSED on iteration {i+1}  ({elapsed}s total)")
            metrics["pass_at_1"] = True
            metrics["iterations_to_pass"] = i + 1
            metrics["time_to_pass_sec"] = elapsed
            metrics["total_iterations"] = i + 1
            break
        else:
            err = classify_error(feedback)
            if "COMPILATION" in feedback: metrics["compile_errors"] += 1
            else: metrics["sim_errors"] += 1
            metrics["error_types"].append(err)
            print(f"  {err} - sending feedback to Gemini")
            messages.append({"role": "assistant", "content": llm_output})
            messages.append({"role": "user", "content": f"The code failed. Fix ALL errors and return the complete corrected module.\nError:\n{feedback}"})
    with open(os.path.join(project_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    if not metrics["pass_at_1"]:
        print(f"  FAILED after {MAX_RETRIES} iterations")
    return metrics

BENCHMARK = {
    "half_adder": {"deps": [], "spec": "Create a Verilog-2001 module 'half_adder'.\nPorts: input a, b; output sum, cout\nLogic: assign sum = a ^ b; assign cout = a & b;\nDeclare sum and cout as wire."},
    "full_adder": {"deps": [], "spec": "Create a Verilog-2001 module 'full_adder'.\nPorts: input a, b, cin; output sum, cout\nUse continuous assign only. sum = a^b^cin, cout = (a&b)|(b&cin)|(a&cin).\nDeclare sum and cout as wire."},
    "ripple_carry_adder": {"deps": ["full_adder.v"], "spec": "Create a Verilog-2001 module 'ripple_carry_adder'.\nPorts: input [3:0] A, B; input cin; output [3:0] Sum; output cout\n1. Declare Sum and cout as WIRE.\n2. Instantiate full_adder four times: fa0, fa1, fa2, fa3.\n3. Ports: .a .b .cin .sum .cout\n4. Chain carries: fa0.cout->fa1.cin->fa2.cin->fa3.cin"},
    "alu_8bit": {"deps": [], "spec": "Create a Verilog-2001 module 'alu_8bit'.\nPorts: input [7:0] A, B; input [2:0] op; output [7:0] result; output zero\n000=ADD 001=SUB 010=AND 011=OR 100=XOR 101=NOT_A 110=SHL 111=SHR\nzero=(result==0). Combinational always+case. result is reg, zero is wire."},
    "dff_sync_reset": {"deps": [], "spec": "Create a Verilog-2001 module 'dff_sync_reset'.\nPorts: input clk, rst, d; output q\nD flip-flop, synchronous active-high reset. q is reg."},
    "counter_4bit": {"deps": [], "spec": "Create a Verilog-2001 module 'counter_4bit'.\nPorts: input clk, rst; output [3:0] count\n4-bit up counter, synchronous active-high reset. count is reg."},
    "fsm_seq_detector": {"deps": [], "spec": "Create a Verilog-2001 module 'fsm_seq_detector'.\nPorts: input clk, rst, in; output detected\nMealy FSM detecting sequence 1011.\nAssert detected=1 on the clock cycle the LAST bit of 1011 arrives.\nStates S0 S1 S2 S3 using localparam and reg [1:0].\nSynchronous reset to S0. Support overlapping sequences.\nTransitions: S0--(1)-->S1, S1--(0)-->S2, S2--(1)-->S3, S3--(1)-->S1, S3--(0)-->S2\ndetected is reg. NO typedef enum. NO SystemVerilog."},
    "simple_cpu_alu": {"deps": [], "spec": "Create a Verilog-2001 module 'simple_cpu_alu'.\nPorts: input [3:0] A, B; input [1:0] op; output [3:0] result; output zero\n00=ADD 01=SUB 10=AND 11=OR. zero=(result==0). result is reg, zero is wire."},
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AutoChip with Gemini 1.5 Pro")
    parser.add_argument("--module", default="all", help="Module name or 'all'")
    args = parser.parse_args()

    if args.module == "all":
        print(f"\nRunning full benchmark suite on {MODEL_NAME}\n")
        all_metrics = []
        for mod_name, config in BENCHMARK.items():
            dep_files = []
            for dep in config["deps"]:
                dep_module = dep.replace(".v", "")
                dep_result_dir = os.path.join(RESULTS_DIR, SAFE_NAME, dep_module)
                found = False
                if os.path.exists(dep_result_dir):
                    for folder in sorted(os.listdir(dep_result_dir)):
                        candidate = os.path.join(dep_result_dir, folder, dep)
                        if os.path.exists(candidate):
                            dep_files.append(candidate)
                            found = True
                            break
                if not found and os.path.exists(dep):
                    dep_files.append(dep)
            m = autochip_loop(config["spec"], mod_name, dep_files)
            if m: all_metrics.append(m)

        print(f"\n{'='*60}")
        print(f"  SUMMARY - {MODEL_NAME}")
        print(f"{'='*60}")
        print(f"  {'Module':<28} {'Pass':>5} {'Iters':>6} {'Time(s)':>8} {'CE':>4} {'SE':>4}")
        print(f"  {'-'*28} {'-'*5} {'-'*6} {'-'*8} {'-'*4} {'-'*4}")
        passed = 0
        for m in all_metrics:
            p  = "PASS" if m["pass_at_1"] else "FAIL"
            it = str(m["iterations_to_pass"]) if m["iterations_to_pass"] else "-"
            t  = str(m["time_to_pass_sec"])   if m["time_to_pass_sec"]   else "-"
            print(f"  {m['module']:<28} {p:>5} {it:>6} {t:>8} {m['compile_errors']:>4} {m['sim_errors']:>4}")
            if m["pass_at_1"]: passed += 1
        print(f"\n  Pass@1: {passed}/{len(all_metrics)} = {100*passed//max(len(all_metrics),1)}%")
    else:
        config = BENCHMARK.get(args.module)
        if not config:
            print(f"Unknown module '{args.module}'. Available: {list(BENCHMARK.keys())}")
            sys.exit(1)
        autochip_loop(config["spec"], args.module, config["deps"])
