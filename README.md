# Intelligent Revenue Cycle Management (RCM) Agent

**Subtitle:** Multi-agent healthcare billing assistant powered by LangGraph, Gemini, FastAPI, and Gradio.

> ⚠️ This project is a technical prototype for the **Google x Kaggle AI Agents Intensive (Enterprise Agents track)**.  
> It is **not** a medical product and must **not** be used for real clinical or billing decisions.

---

[![Watch the demo on YouTube](https://img.youtube.com/vi/oBHuCjsi6NU/0.jpg)](https://www.youtube.com/watch?v=oBHuCjsi6NU)



## 1. Problem & Motivation

Healthcare providers lose large amounts of revenue every year due to:

- Incorrect or incomplete medical coding  
- Preventable claim denials  
- Manual, error-prone billing workflows  

Traditional revenue cycle management (RCM) involves:

- Human staff verifying insurance eligibility  
- Coders mapping visit notes to ICD-10 codes  
- Staff preparing and submitting claims  
- Teams investigating denials and writing appeal letters  

This is slow, repetitive, and expensive.

---

## 2. Solution Overview

This project is an **Intelligent Revenue Cycle Management Agent** that acts like a digital billing assistant.

It runs a **multi-agent pipeline**:

1. **Intake Agent** – verifies the insurance number and captures the visit context  
2. **Coding Agent** – suggests ICD-10 diagnosis codes (using Gemini or a heuristic fallback)  
3. **Claim Agent** – prepares and “submits” the claim (simulated long-running external API)  
4. **Audit Agent** – evaluates the claim, computes an issue score, and decides whether to loop back  
5. **Appeal Agent** – generates an appeal letter for rejected claims  
6. **Memory Agent** – compacts the context and writes to a long-term memory bank  

The agent is exposed via:

- A **FastAPI A2A-style JSON API**: `POST /a2a/rcm`  
- A **modern Gradio UI** for interactive testing  
- A **minimal MCP-style tool server**: `GET /mcp/tools`, `POST /mcp/call`

This fits the **Enterprise Agents** track by targeting a real B2B workflow: automating hospital and clinic billing processes.

---

## 3. Architecture

### 3.1 High-Level Diagram (Conceptual)

**User / Calling System**  
→ FastAPI A2A endpoint (`/a2a/rcm`)  
→ LangGraph workflow (RCMState)  
→ Agents (nodes)  
→ Tools (MCP-style)  
→ Long-term memory bank

### 3.2 Agents (LangGraph Nodes)

All agents share a single typed state: `RCMState` (patient_id, insurance_number, visit_reason, codes, status, audit_issues, appeal, history, etc.).

- **Intake Agent**
  - Verifies insurance using `InsuranceCheckTool`
  - Sets `insurance_verified` flag
  - Logs step into `history`

- **Coding Agent**
  - Calls `suggest_icd_codes(visit_reason)`
  - Uses:
    - `MockSearchTool` as a built-in-style search tool (MCP-style tool usage)
    - Gemini via LangChain when `GOOGLE_API_KEY` is available
    - Heuristic fallback when Gemini is not available
  - Writes `codes` into the state
  - Logs into `history`

- **Claim Agent**
  - Calls `ClaimSubmitTool` (simulated long-running external API)
  - Adds a 1-second delay to represent a long-running operation
  - Writes `status`, `claim_id`, `denial_reason`
  - Logs into `history`

- **Audit Agent**
  - Checks:
    - `insurance_verified`
    - `codes` present
    - `status` is `"Submitted"`
  - Uses `CodeExecutionTool` to compute a simple `IssueScore` based on the number of issues
  - Writes `audit_issues`
  - Logs into `history`

- **Appeal Agent**
  - If status is `"Rejected"`:
    - Uses Gemini (or template fallback) to generate an appeal letter
  - If status is `"Submitted"`:
    - Writes `"No appeal needed – claim is submitted."`
  - Writes `appeal`
  - Logs into `history`

- **Memory Agent**
  - Compacts `history` into a short summary (context compaction)
  - Stores a record in `long_term_memory` containing:
    - patient_id  
    - claim_id  
    - status  
    - codes  
    - summary  

### 3.3 Workflow (LangGraph)

The LangGraph `StateGraph` is wired as:

```text
intake → coding → claim → audit → (conditional) → appeal → memory → END
                         ↳ if "Missing codes" → coding (loop) ```

This shows:

- **Sequential agents**: `intake → coding → claim → audit → appeal → memory`
- **Looping agent**: `audit` can route back to `coding`
- **Shared state and history** across all nodes

---

## 4. Features & Course Concepts

This project is designed to hit multiple rubric items from the AI Agents Intensive.

### 4.1 Multi-Agent System

- Multiple agents orchestrated via **LangGraph**
- Each agent is a pure function over `RCMState`
- Agents collaborate through a **shared, typed state**

### 4.2 Tools

**Custom tools:**

- `InsuranceCheckTool`
- `ClaimSubmitTool`
- `MockSearchTool`
- `CodeExecutionTool`

**Minimal MCP-style server:**

- `GET /mcp/tools` – list tools (name + description)
- `POST /mcp/call` – call any tool by name with `args` / `kwargs`

### 4.3 Long-Running Operations

- `ClaimSubmitTool` simulates a long-running external service  
  (sleep + random UUID `claim_id`)
- Demonstrates how the graph can model **slow, external calls**

### 4.4 Sessions & Memory

**Session service:**

- `InMemorySessionService` for the A2A endpoint  
- Stores per-session state and allows **resuming runs**

**Long-term memory:**

- `long_term_memory` list holds compact summaries of past claims
- Uses `compact_context(history)` to keep memory size bounded

### 4.5 Context Engineering

- `history` list accumulates agent events and decisions
- `compact_context` merges and truncates history to the last ~500 characters
- Can be extended to feed into **LLM prompts** or **observability dashboards**

### 4.6 Observability & Evaluation

- Each agent node prints log messages (simple tracing)
- **Audit Agent** acts as an evaluation agent:
  - Checks correctness of the pipeline outcome
  - Produces `audit_issues` and an `IssueScore`
  - Drives the loop (retry coding or move to appeal)

### 4.7 A2A Protocol & Deployment

**A2A-style API:**

- `POST /a2a/rcm`  
  - **Input:** `patient_id`, `insurance_number`, `visit_reason`, optional `session_id`  
  - **Output:** `session_id` + full final state  

Another agent or system can treat this RCM agent as a **service**.

**Deployment-ready FastAPI app:**

- Can be run via `uvicorn` locally or containerized for cloud deployment

**Gradio UI:**

- Provides an easy way to demo the agent to non-technical stakeholders

---

## 5. Tech Stack

- **Python 3.10+**
- **LangGraph** – multi-agent stateful workflows
- **LangChain + Gemini (Google Generative AI)** – LLM-powered coding & appeals
- **FastAPI** – A2A-style HTTP API + MCP-style endpoints
- **Gradio** – modern UI for demo
- **python-dotenv** – loading `GOOGLE_API_KEY` from `.env`

---
