#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import requests

# --- SYSTEM CONFIGURATION ---
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5-coder:14b"
BASE_ROLES_PATH = "./roles/generated_compliance/hosts"
MAX_LINT_RETRIES = 3

def check_dependencies():
    """Verify system binaries exist in the path execution."""
    for tool in ["ansible", "ansible-lint", "ollama"]:
        if not shutil.which(tool) and tool != "ollama":
            print(f"[-] Error: '{tool}' tool missing. Aborting environment generation.")
            sys.exit(1)

def run_command(cmd):
    """Executes a system shell process securely."""
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout.strip(), res.stderr.strip()

def get_dynamic_inventory():
    """Simulates CMDB mapping for production cluster nodes."""
    return {
        "rhel9-db-prod.local": {
            "ansible_host": "192.168.10.45",
            "compliance_profile": "stig_cat1_strict",
            "fips_required": True
        },
        "rhel10-app-dev.local": {
            "ansible_host": "192.168.20.12",
            "compliance_profile": "stig_cat2_relaxed",
            "fips_required": False
        }
    }

def gather_filtered_facts(hostname):
    """Collects system facts and filters down tokens to preserve context limit."""
    print(f"[+] Gathering hardware, network, and storage details from {hostname}...")
    stdout, _ = run_command(["ansible", hostname, "-m", "setup"])
    
    try:
        clean_json = stdout.split("=>")[-1].strip()
        full_facts = json.loads(clean_json).get("ansible_facts", {})
    except Exception:
        print(f"[-] Unreachable or unparsable payload from host: {hostname}")
        return None

    return {
        "os_distribution": full_facts.get("ansible_distribution"),
        "os_version": full_facts.get("ansible_distribution_version"),
        "os_major_version": full_facts.get("ansible_distribution_major_version"),
        "architecture": full_facts.get("ansible_architecture"),
        "virtualization_type": full_facts.get("ansible_virtualization_type"),
        "mounts": [{"mount": m.get("mount"), "fstype": m.get("fstype")} for m in full_facts.get("ansible_mounts", [])],
        "services": list(full_facts.get("ansible_services", {}).keys())
    }

def call_local_llm(prompt):
    """Queries the offline LLM endpoint with highly-deterministic generation params."""
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,  # Low temperature eliminates syntax hallucinations
            "num_ctx": 16384     # Extended context window allocation
        }
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
        raw_output = response.json().get("response", "")
        return raw_output.replace("```yaml", "").replace("```", "").strip()
    except Exception as e:
        print(f"[-] Local LLM engine unavailable: {e}")
        sys.exit(1)

def run_self_correcting_loop(hostname, metadata, facts):
    """Executes the loop testing output against the compiler engine."""
    host_dir = f"{BASE_ROLES_PATH}/{hostname}/tasks"
    os.makedirs(host_dir, exist_ok=True)
    target_file = f"{host_dir}/main.yml"

    # Generation Draft Prompt Instruction
    prompt = f"""
You are an offline secure systems engineer. Generate a compliant Ansible 'tasks/main.yml' file.
TARGET FACTS: {json.dumps(facts, indent=2)}
POLICY DIRECTIVES: Profile: {metadata['compliance_profile']}, FIPS Required: {metadata['fips_required']}

REQUIREMENTS:
1. Support specific constraints for RHEL {facts['os_version']}. 
2. If FIPS execution is true, check crypt policy state via 'fips-mode-setup --check'.
3. Omit hardware security structures (e.g. USBGuard) if virtualization state equals virtual machine.
4. Enforce FQCN format strings (e.g., 'ansible.builtin.template').
5. Output ONLY functional, raw Ansible YAML inside a single markdown block. No text wrappers.
"""
    yaml_payload = call_local_llm(prompt)

    for attempt in range(1, MAX_LINT_RETRIES + 1):
        with open(target_file, "w") as f:
            f.write(yaml_payload)

        # Linting evaluation path
        lint_out, _ = run_command(["ansible-lint", "--parseable", target_file])
        if not lint_out:
            print(f"[+] Clean compile verified for {hostname} on attempt {attempt}.")
            return True

        print(f"[-] Compiling violations found on iteration {attempt}:\n{lint_out}")
        
        correction_prompt = f"""
The Ansible YAML below failed 'ansible-lint' rules. Correct the file to fix all bugs.
CURRENT CODE:\n{yaml_payload}\n\nERRORS DETECTED:\n{lint_out}
Output ONLY modified, executable code wrapped inside a markdown block. No commentary.
"""
        yaml_payload = call_local_llm(correction_prompt)

    print(f"[!] Target {hostname} saved with warning notifications. Manual parsing required.")
    return False

def main():
    check_dependencies()
    hosts_matrix = get_dynamic_inventory()
    for target_host, metadata in hosts_matrix.items():
        print(f"\n[🚀] Beginning validation workflow for node: {target_host}")
        facts_payload = gather_filtered_facts(target_host)
        if facts_payload:
            run_self_correcting_loop(target_host, metadata, facts_payload)

if __name__ == "__main__":
    main()
