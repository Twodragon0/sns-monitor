# OpenCode CCG and Lead Agents Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a reusable CCG workflow and lead-owned subagents so OpenCode can fan out work with Codex/Gemini and structured lead orchestration.

**Architecture:** Keep the existing `lead` primary agent on `openai/gpt-5.4`, add global custom commands for `/ccg` and `/lead-agents`, and define focused lead subagents in `~/.config/opencode/agents/`. Update `lead` so it knows when to delegate and which subagents it is allowed to call.

**Tech Stack:** OpenCode config, global markdown agents, global markdown commands, OMC `omc ask` CLI.

---

### Task 1: Add the implementation plan artifact

**Files:**
- Create: `docs/plans/2026-03-19-opencode-ccg-lead-agents.md`

**Step 1: Write the plan file**

Add this document with exact paths, delegation shape, and verification commands.

**Step 2: Verify the file exists**

Run: `ls docs/plans`
Expected: `2026-03-19-opencode-ccg-lead-agents.md` appears in the directory listing.

### Task 2: Add reusable CCG and lead orchestration commands

**Files:**
- Create: `/Users/twodragon/.config/opencode/commands/ccg.md`
- Create: `/Users/twodragon/.config/opencode/commands/lead-agents.md`

**Step 1: Write the `ccg` command**

Create a markdown command that:
- runs on `lead`
- keeps `openai/gpt-5.4`
- injects `omc ask codex --print ...`
- injects `omc ask gemini --print ...`
- asks Claude/OpenCode to synthesize common ground, disagreements, recommendation, and next actions

**Step 2: Write the `lead-agents` command**

Create a markdown command that:
- runs on `lead`
- tells `lead` to decompose the user request into planning, execution, and review lanes
- explicitly encourages `lead-planner`, `lead-executor`, and `lead-reviewer` when useful

**Step 3: Verify commands load**

Run: `opencode run "/ccg smoke-test for tri-model synthesis"`
Expected: command resolves instead of being treated as plain text and the run references `lead`.

### Task 3: Add focused lead subagents

**Files:**
- Create: `/Users/twodragon/.config/opencode/agents/lead-planner.md`
- Create: `/Users/twodragon/.config/opencode/agents/lead-executor.md`
- Create: `/Users/twodragon/.config/opencode/agents/lead-reviewer.md`
- Modify: `/Users/twodragon/.config/opencode/agents/lead.md`
- Modify: `/Users/twodragon/.config/opencode/opencode.json`

**Step 1: Write the failing behavior check**

Run: `opencode run --agent lead "Use @lead-planner to break this into steps"`
Expected before config: agent mention or subagent use is unavailable or not routed through the custom lead subagent set.

**Step 2: Add the subagent files**

Create focused prompts:
- `lead-planner`: read-heavy decomposition, checklists, sequencing
- `lead-executor`: implementation-focused, can edit and run commands
- `lead-reviewer`: verification/review focused, read-only where practical

**Step 3: Update lead orchestration prompt**

Teach `lead` to:
- use canonical skill naming
- use `/ccg` or equivalent Codex/Gemini fan-out for ambiguous or high-risk requests
- delegate planning/execution/review to the new lead subagents when it improves quality or speed

**Step 4: Restrict task permissions**

Update `opencode.json` so `lead` can call the new lead subagents plus safe built-ins like `explore`/`general`, instead of unconstrained delegation.

**Step 5: Verify subagent availability**

Run: `opencode run --agent lead "Use @lead-planner to outline a 3-step plan for adding a health endpoint"`
Expected: run acknowledges `lead-planner` instead of failing to find the agent.

### Task 4: Verify the final setup

**Files:**
- Verify only: `/Users/twodragon/.config/opencode/opencode.json`
- Verify only: `/Users/twodragon/.config/opencode/agents/*.md`
- Verify only: `/Users/twodragon/.config/opencode/commands/*.md`

**Step 1: Validate config parses**

Run: `opencode mcp list`
Expected: config loads without JSON/schema errors.

**Step 2: Validate CCG command**

Run: `opencode run "/ccg compare two approaches for adding Redis retry logic"`
Expected: command executes, uses `lead`, and includes Codex/Gemini material in the synthesis path.

**Step 3: Validate lead-agent orchestration**

Run: `opencode run --agent lead "Use lead agents to plan, implement, and review how you would add a dummy endpoint without making changes"`
Expected: lead references the new subagents or at minimum shows the orchestration policy in action.

**Step 4: Commit**

Do not commit unless the user explicitly asks.
