# agentm-main-agent

**Version:** 0.1.0

## Trigger
- **Type:** manual (Python API / CLI)
- **Description:** Build the main agent coordinator layer

## Config
References `config.yaml`:
- `executor_mode`: simple | complex | auto (auto = 渐进式)
- `stream_output`: true | false
- `max_retries`: 3

## Nodes

### 1. Write Coordinator Core
- **Action:** Write `main_agent/coordinator.py`
- **Input:** Requirements from architecture design
- **Output:** `data/01-coordinator-core.json`
- **Output schema:** `{ "file": string, "lines": number, "functions": string[] }`
- **On error:** fail
- **On empty:** N/A

### 2. Write State Manager
- **Action:** Write `main_agent/state_manager.py`
- **Input:** `data/01-coordinator-core.json`
- **Output:** `data/02-state-manager.json`
- **On error:** fail

### 3. Write Intent Parser
- **Action:** Write `main_agent/intent_parser.py`
- **Input:** `data/02-state-manager.json`
- **Output:** `data/03-intent-parser.json`
- **On error:** fail

### 4. Write Result Aggregator
- **Action:** Write `main_agent/result_aggregator.py`
- **Input:** `data/03-intent-parser.json`
- **Output:** `data/04-result-aggregator.json`
- **On error:** fail

### 5. Write FastAPI Interface
- **Action:** Write `interfaces/api/main.py`
- **Input:** All above outputs
- **Output:** `data/05-api-interface.json`
- **On error:** fail

### 6. Integration Test
- **Action:** Run pytest against the new modules
- **Input:** All module files
- **Output:** `data/06-test-results.json`
- **Output schema:** `{ "passed": number, "failed": number, "errors": string[] }`
- **On error:** continue

## Output
Complete main agent coordinator with FastAPI interface, streaming support, and integration tests.

## State
- **Cursor:** `state/cursor.json` — tracks current step
- **Checkpoint:** `state/checkpoint.json` — saved state on each step completion
