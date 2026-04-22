"""
autochip_runner_hpc.py  --  AutoChip using HuggingFace Transformers directly
No Ollama needed. Runs on GPU via transformers + accelerate.

Usage:
    python scripts/autochip_runner_hpc.py --model 14b --module half_adder
    python scripts/autochip_runner_hpc.py --model 14b --module all
    python scripts/autochip_runner_hpc.py --model 32b --module all

Models:
    14b  ->  Qwen/Qwen2.5-Coder-14B-Instruct
    32b  ->  Qwen/Qwen2.5-Coder-32B-Instruct  (needs ~30GB VRAM, fits V100-32GB)
    7b   ->  Qwen/Qwen2.5-Coder-7B-Instruct
"""

import os, subprocess, re, shutil, sys, json, time, argparse
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

# ── CONFIG ────────────────────────────────────────────────────────────────────
MAX_RETRIES   = 5
TESTBENCH_DIR = "testbenches"
RESULTS_DIR   = "results"

# Point HuggingFace cache to scratch so it doesn't fill home quota
HF_CACHE = "/scratch/soumyaj/hf_cache"
os.environ["HF_HOME"]             = HF_CACHE
os.environ["TRANSFORMERS_CACHE"]  = HF_CACHE
os.environ["HF_DATASETS_CACHE"]   = HF_CACHE

MODEL_MAP = {
    "14b": "Qwen/Qwen2.5-Coder-14B-Instruct",
    "32b": "Qwen/Qwen2.5-Coder-32B-Instruct",
    "7b":  "Qwen/Qwen2.5-Coder-7B-Instruct",
    "deepseek": "deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct",
}

SYSTEM_PROMPT = """You are a Verilog-2001 Expert.
STRICT RULES:
1. Outputs driven by 'assign' statements MUST be declared as 'wire'.
2. Outputs driven by sub-module instantiations MUST be declared as 'wire'.
3. ONLY use 'reg' if the signal is assigned inside an 'always' block.
4. Use only non-blocking assignments (<=) inside clocked always blocks.
5. Use blocking assignments (=) inside combinational always blocks.
6. Do NOT use SystemVerilog syntax. No typedef enum, no logic type.
7. Use localparam for state declarations.
8. Return ONLY code inside ```verilog blocks. No explanation outside."""

# ── MODEL LOADING ─────────────────────────────────────────────────────────────
_model     = None
_tokenizer = None
_model_name = None

def load_model(model_key):
    global _model, _tokenizer, _model_name
    model_id = MODEL_MAP[model_key]

    if _model_name == model_id:
        return  # already loaded

    print(f"\n📦 Loading {model_id} ...")
    print(f"   VRAM available: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    _tokenizer = AutoTokenizer.from_pretrained(
        model_id,
        cache_dir=HF_CACHE,
        trust_remote_code=True
    )

    _model = AutoModelForCausalLM.from_pretrained(
        model_id,
        cache_dir=HF_CACHE,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True
    )
    _model.eval()
    _model_name = model_id

    used = torch.cuda.memory_allocated() / 1e9
    print(f"   ✅ Model loaded. VRAM used: {used:.1f} GB\n")


def call_model(messages):
    """
    Takes OpenAI-style messages list, returns generated string.
    Uses Qwen chat template.
    """
    # Build chat using tokenizer template
    text = _tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    inputs = _tokenizer([text], return_tensors="pt").to(_model.device)

    with torch.no_grad():
        outputs = _model.generate(
            **inputs,
            max_new_tokens=1024,
            temperature=0.1,
            do_sample=True,
            pad_token_id=_tokenizer.eos_token_id
        )

    # Decode only the new tokens (not the input)
    new_tokens = outputs[0][inputs.input_ids.shape[1]:]
    return _tokenizer.decode(new_tokens, skip_special_tokens=True)


# ── VERIFICATION ──────────────────────────────────────────────────────────────
def run_verification(iter_dir, module_name):
    log_file = os.path.join(iter_dir, "sim_log.txt")
    vvp_out  = os.path.join(iter_dir, "sim.vvp")
    v_files  = [os.path.join(iter_dir, f)
                for f in os.listdir(iter_dir) if f.endswith('.v')]

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


# ── MAIN LOOP ─────────────────────────────────────────────────────────────────
def autochip_loop(spec, module_name, model_key, dependencies=None):
    if dependencies is None:
        dependencies = []

    tb_path = os.path.join(TESTBENCH_DIR, f"{module_name}_tb.v")
    if not os.path.exists(tb_path):
        print(f"❌ Missing testbench: {tb_path}")
        return None

    safe_name   = f"hpc_qwen25coder_{model_key}"
    project_dir = os.path.join(RESULTS_DIR, safe_name, module_name)
    os.makedirs(project_dir, exist_ok=True)

    messages = [
        {"role": "system",  "content": SYSTEM_PROMPT},
        {"role": "user",    "content": spec}
    ]

    metrics = {
        "module":             module_name,
        "model":              MODEL_MAP[model_key],
        "hardware":           "H100-80GB-HPC",
        "pass_at_1":          False,
        "iterations_to_pass": None,
        "time_to_pass_sec":   None,
        "total_iterations":   MAX_RETRIES,
        "compile_errors":     0,
        "sim_errors":         0,
        "error_types":        [],
        "max_retries":        MAX_RETRIES,
    }

    print(f"\n{'='*60}")
    print(f"  AutoChip: {module_name}  |  Model: Qwen2.5-Coder-{model_key.upper()}")
    print(f"  Hardware: Tesla V100-PCIE-32GB")
    print(f"{'='*60}")
    t_start = time.time()

    for i in range(MAX_RETRIES):
        iter_dir = os.path.join(project_dir, f"iter_{i+1}")
        os.makedirs(iter_dir, exist_ok=True)
        print(f"\n  🔄 Iteration {i+1}/{MAX_RETRIES}")

        t_llm = time.time()
        try:
            llm_output = call_model(messages)
        except Exception as e:
            print(f"  ❌ Model error: {e}")
            break
        llm_time = round(time.time() - t_llm, 1)
        print(f"  🤖 Model responded in {llm_time}s")

        # Extract verilog code block
        match = re.search(r"```(?:verilog)?(.*?)```", llm_output, re.DOTALL)
        code  = match.group(1).strip() if match else llm_output.strip()

        # Save
        with open(os.path.join(iter_dir, f"{module_name}.v"), "w") as f:
            f.write(code)
        with open(os.path.join(iter_dir, "raw_ai_response.txt"), "w") as f:
            f.write(llm_output)

        for dep in dependencies:
            if os.path.exists(dep):
                shutil.copy(dep, iter_dir)
        shutil.copy(tb_path, iter_dir)

        success, feedback = run_verification(iter_dir, module_name)

        if success:
            elapsed = round(time.time() - t_start, 2)
            print(f"  ✅ PASSED on iteration {i+1}  ({elapsed}s total)")
            metrics["pass_at_1"]           = True
            metrics["iterations_to_pass"]  = i + 1
            metrics["time_to_pass_sec"]    = elapsed
            metrics["total_iterations"]    = i + 1
            break
        else:
            err = classify_error(feedback)
            if "COMPILATION" in feedback:
                metrics["compile_errors"] += 1
            else:
                metrics["sim_errors"] += 1
            metrics["error_types"].append(err)
            print(f"  ❌ {err}  — sending feedback to model")
            messages.append({"role": "assistant", "content": llm_output})
            messages.append({"role": "user",
                "content": f"The code failed. Fix ALL errors and return the complete corrected module.\nError:\n{feedback}"})

    with open(os.path.join(project_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    if not metrics["pass_at_1"]:
        print(f"  ❌ FAILED after {MAX_RETRIES} iterations")

    return metrics


# ── BENCHMARK ─────────────────────────────────────────────────────────────────
BENCHMARK = {
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
Use continuous assign only. sum = a^b^cin, cout = (a&b)|(b&cin)|(a&cin).
Declare sum and cout as wire."""
    },
    "ripple_carry_adder": {
        "deps": ["full_adder.v"],
        "spec": """Create a Verilog-2001 module 'ripple_carry_adder'.
Ports: input [3:0] A, B; input cin; output [3:0] Sum; output cout
1. Declare Sum and cout as WIRE.
2. Instantiate 'full_adder' four times: fa0, fa1, fa2, fa3.
3. Ports: .a .b .cin .sum .cout
4. Chain carries: fa0.cout->fa1.cin->fa2.cin->fa3.cin"""
    },
    "alu_8bit": {
        "deps": [],
        "spec": """Create a Verilog-2001 module 'alu_8bit'.
Ports: input [7:0] A, B; input [2:0] op; output [7:0] result; output zero
000=ADD 001=SUB 010=AND 011=OR 100=XOR 101=NOT_A 110=SHL 111=SHR
zero=(result==0). Combinational always+case. result is reg, zero is wire."""
    },
    "dff_sync_reset": {
        "deps": [],
        "spec": """Create a Verilog-2001 module 'dff_sync_reset'.
Ports: input clk, rst, d; output q
D flip-flop, synchronous active-high reset. q is reg."""
    },
    "counter_4bit": {
        "deps": [],
        "spec": """Create a Verilog-2001 module 'counter_4bit'.
Ports: input clk, rst; output [3:0] count
4-bit up counter, synchronous active-high reset. count is reg."""
    },
    "fsm_seq_detector": {
        "deps": [],
        "spec": """Create a Verilog-2001 module 'fsm_seq_detector'.
Ports: input clk, rst, in; output detected
Mealy FSM detecting sequence 1011.
Assert detected=1 on the clock cycle the LAST bit of 1011 arrives.
States S0 S1 S2 S3 using localparam and reg [1:0].
Synchronous reset to S0. Support overlapping sequences.
Transitions: S0--(1)-->S1, S1--(0)-->S2, S2--(1)-->S3, S3--(1)-->S1, S3--(0)-->S2
detected is reg. NO typedef enum. NO SystemVerilog."""
    },
    "simple_cpu_alu": {
        "deps": [],
        "spec": """Create a Verilog-2001 module 'simple_cpu_alu'.
Ports: input [3:0] A, B; input [1:0] op; output [3:0] result; output zero
00=ADD 01=SUB 10=AND 11=OR. zero=(result==0). result is reg, zero is wire."""
    },
    # ── L3 harder modules ─────────────────────────────────────────────────────
    "shift_register_8bit": {
        "deps": [],
        "spec": """Create a Verilog-2001 module 'shift_register_8bit'.
Ports: input clk, rst, sin; output sout; output [7:0] data
8-bit serial-in serial-out shift register.
On posedge clk: if rst data<=0; else data<={data[6:0],sin};
sout = data[7]. data and sout are reg."""
    },
    "register_file_4x8": {
        "deps": [],
        "spec": """Create a Verilog-2001 module 'register_file_4x8'.
Ports: input clk; input we; input [1:0] waddr, raddr1, raddr2;
       input [7:0] wdata; output [7:0] rdata1, rdata2
4 registers x 8-bit. Synchronous write on posedge clk when we=1.
Asynchronous read: rdata1=reg[raddr1], rdata2=reg[raddr2].
rdata1 and rdata2 are wire driven by assign."""
    },
    # ── L4 Processor (ROME pipeline) ──────────────────────────────────────────
    "simple_cpu_regfile": {
        "deps": [],
        "spec": """Create a Verilog-2001 module 'simple_cpu_regfile'.
Ports: input clk, rst, we; input [1:0] waddr, raddr1, raddr2;
       input [3:0] wdata; output [3:0] rdata1, rdata2
4 registers x 4-bit. Sync write (posedge clk, we=1). Sync reset clears all.
Async read via assign. rdata1 rdata2 are wire."""
    },
    "simple_cpu_ctrl": {
        "deps": [],
        "spec": """Create a Verilog-2001 module 'simple_cpu_ctrl'.
Ports: input clk, rst; input [7:0] instruction;
       output [1:0] alu_op; output we_reg; output [1:0] rs1, rs2, rd
8-instruction FSM controller. instruction[7:5] = opcode:
  000=NOP 001=ADD 010=SUB 011=AND 100=OR 101=LOAD 110=STORE 111=BRANCH
instruction[4:3]=rs1, instruction[2:1]=rs2, instruction[0] unused for rd (use rs1).
we_reg=1 for ADD/SUB/AND/OR/LOAD only.
alu_op: 00=ADD 01=SUB 10=AND 11=OR
Use localparam. All outputs are reg except combinational assigns."""
    },
    "simple_cpu_top": {
        "deps": ["simple_cpu_alu.v", "simple_cpu_regfile.v", "simple_cpu_ctrl.v"],
        "spec": """Create a Verilog-2001 module 'simple_cpu_top'.
Ports: input clk, rst; input [7:0] instruction; output [3:0] result; output zero
Instantiate:
  simple_cpu_ctrl  ctrl  (.clk .rst .instruction .alu_op .we_reg .rs1 .rs2 .rd)
  simple_cpu_regfile rf  (.clk .rst .we(we_reg) .waddr(ctrl.rd) .raddr1(ctrl.rs1)
                          .raddr2(ctrl.rs2) .wdata(result) .rdata1(A) .rdata2(B))
  simple_cpu_alu   alu   (.A .B .op(alu_op) .result .zero)
All interconnect wires declared as wire. result and zero are wire."""
    },
}


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model",  default="14b",
                        choices=["7b", "14b", "32b", "deepseek"],
                        help="Model size: 7b, 14b, or 32b")
    parser.add_argument("--module", default="all",
                        help="Module name or 'all' or 'l4' for processor only")
    args = parser.parse_args()

    if args.model not in MODEL_MAP:
        print(f"Unknown model. Use: {list(MODEL_MAP.keys())}")
        sys.exit(1)

    # Load model once, reuse for all modules
    load_model(args.model)

    if args.module == "l4":
        # ROME pipeline — run processor submodules in order
        run_modules = ["simple_cpu_alu", "simple_cpu_regfile",
                       "simple_cpu_ctrl", "simple_cpu_top"]
    elif args.module == "all":
        run_modules = list(BENCHMARK.keys())
    else:
        run_modules = [args.module]

    print(f"\n🚀 Running {len(run_modules)} module(s) on Qwen2.5-Coder-{args.model.upper()}")

    all_metrics = []
    safe_name   = f"hpc_qwen25coder_{args.model}"

    for mod_name in run_modules:
        config = BENCHMARK.get(mod_name)
        if not config:
            print(f"⚠️  Unknown module: {mod_name}")
            continue

        # Resolve dependency paths from passing HPC results
        dep_files = []
        for dep in config["deps"]:
            dep_module = dep.replace(".v", "")
            dep_dir = os.path.join(RESULTS_DIR, safe_name, dep_module)
            found = False
            if os.path.exists(dep_dir):
                for folder in sorted(os.listdir(dep_dir)):
                    candidate = os.path.join(dep_dir, folder, dep)
                    if os.path.exists(candidate):
                        dep_files.append(candidate)
                        found = True
                        print(f"  📎 Using passing dep: {candidate}")
                        break
            if not found:
                fallback = os.path.join("/scratch/soumyaj/AutoChipTEST", dep)
                if os.path.exists(fallback):
                    dep_files.append(fallback)
                    print(f"  📎 Using fallback dep: {fallback}")

        m = autochip_loop(config["spec"], mod_name, args.model, dep_files)
        if m:
            all_metrics.append(m)

    # Summary table
    print(f"\n{'='*60}")
    print(f"  SUMMARY — Qwen2.5-Coder-{args.model.upper()} on H100-80GB-HPC")
    print(f"{'='*60}")
    print(f"  {'Module':<28} {'Pass':>5} {'Iters':>6} {'Time(s)':>8} {'CE':>4} {'SE':>4}")
    print(f"  {'-'*28} {'-'*5} {'-'*6} {'-'*8} {'-'*4} {'-'*4}")
    passed = 0
    for m in all_metrics:
        p  = "✓" if m["pass_at_1"] else "✗"
        it = str(m["iterations_to_pass"]) if m["iterations_to_pass"] else "-"
        t  = str(m["time_to_pass_sec"])   if m["time_to_pass_sec"]   else "-"
        print(f"  {m['module']:<28} {p:>5} {it:>6} {t:>8} {m['compile_errors']:>4} {m['sim_errors']:>4}")
        if m["pass_at_1"]: passed += 1
    print(f"\n  Pass@1: {passed}/{len(all_metrics)} = {100*passed//max(len(all_metrics),1)}%")
