the agentic look
1. Pipeline Architecture Diagram+--------------------------+

|  Ansible Dynamic         | <--- Maps cluster nodes & enforces profile rules
|  Inventory Script        |      (e.g., STIG CAT I Strict vs CAT II Relaxed)
+--------------------------+
             |
             v
+--------------------------+

|  Ansible Setup Module    | <--- Gathers live telemetry from target hosts
|  (Fact Collector)        |      (OS version, virtualization type, mount points)
+--------------------------+
             |
             v
+--------------------------+

|  Python Core Agent       | <--- Filters 20k lines of raw telemetry JSON down
|  (Data Pre-processor)    |      to essential, high-signal security tokens
+--------------------------+
             |
             v
+--------------------------+

|  Local Offline LLM       | <--- Generates initial deterministic YAML payload
|  (Ollama/vLLM Api)       |      (Temperature: 0.1, Model: Qwen2.5-Coder 14B)
+--------------------------+
             |
             +-----------------------+
             v                       |
+--------------------------+         |

|  Local Execution &       |         | [SELF-CORRECTION LOOP]
|  Ansible-Lint Validation |         | Refeed compilation/style errors
+--------------------------+         | back to LLM context up to 3 times

             |                       |
     [Passes Validation]             |
             v                       |
+--------------------------+         |

| Production Task Saved    | --------+
| to Host Directory Path   |
+--------------------------+





