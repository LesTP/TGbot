# Governance

Development process for asynchronous, multi-session collaboration with a stateless partner (AI or otherwise). Governing constraint: **minimize wasted work when each session starts cold.**

Documentation is the source of truth — do not rely on prior conversations. If something is ambiguous, **ask** (don't guess). Prioritize clarity over speed.

---

## Process

### Entry to Implementation

Implementation begins when Discovery and Architecture are complete.

**Prerequisites:**
- PROJECT.md exists (scope, audience, constraints, success criteria)
- ARCHITECTURE.md exists (component map, data flow, implementation sequence)
- For multi-module projects: ARCH_[module].md exists for each module
- For single-module projects: Combined spec exists

**First steps:**
1. Load PROJECT.md and ARCHITECTURE.md
2. Pick the first module from the implementation sequence
3. Create its DEVPLAN (see Documentation Structure below)
4. Enter Discuss mode

**Shortcut:** `/cold-start` in Claude Code to re-establish context at the start of any session.

### Documentation Structure

Every module maintains two files:

| File | Purpose | Update Timing |
|------|---------|---------------|
| **DEVPLAN.md** | Cold start context, roadmap, phase breakdown, test specs | Before each iteration |
| **DEVLOG.md** | What actually happened — changes, issues, lessons | After each iteration |

**DEVPLAN opens with:**

*Cold Start Summary* (stable — update on major shifts):
- **What this is** — one-sentence scope
- **Key constraints** — non-obvious technical limits
- **Gotchas** — things that cause silent failures, and operational knowledge learned through trial-and-error (commands, workarounds, patterns that aren't obvious from the code)

*Current Status* (volatile — update after each step):
- **Phase** — e.g., "3b — Hit-test math"
- **Focus** — what's being built right now
- **Blocked/Broken** — anything preventing progress

**DEVPLAN cleanup rule:** When a phase completes, reduce each step to a one-line summary with a DEVLOG reference. Keep the step list scannable but remove detailed work items, test specs, and decision rationale (those live in the DEVLOG). The DEVPLAN should get *shorter* as work progresses.

### Decision Log

```
D-#: [Title]
Date: YYYY-MM-DD | Status: Open | Closed
Priority: Critical | Important | Nice-to-have
Decision:
Rationale:
Revisit if:
```

Once **Closed**, don't reopen unless new evidence appears. For reactive decisions during Refine work, a one-line "changed X because Y" in the DEVLOG is sufficient. Use the full template only for genuine design forks with trade-offs.

### Work Regimes

Work falls along a spectrum based on **evaluability** — who can assess whether the output is correct.

**Build (AI-evaluable):** Correctness verifiable by tests, type checks, or objective criteria.
- Tests and acceptance criteria specified **before** implementation
- Large autonomous work chunks (full phases)
- Human reviews asynchronously after completion
- Decisions are architectural and durable

Examples: data models, algorithms, parsers, API contracts, integration wiring, build config.

**Refine (human-evaluable):** Correctness requires human perception or subjective judgment.
- Goals and constraints specified upfront; steps emerge iteratively
- Small increments shown to human frequently
- Human evaluates each increment synchronously
- Decisions are reactive and may reverse

Feedback loop: Show → React → Triage (fix now / fix later / needs decision) → Adjust → Repeat

Examples: visual design, interaction feel, audio quality, layout, naming, copy.

**Explore (decision-evaluable):** Goal is to make a decision, not produce shipping code.
- Output: a closed decision (using the decision template)
- Method: prototype alternatives, compare, evaluate
- Time-boxed (one session or explicit limit)

Examples: technology selection, A/B comparisons, architecture alternatives.

**Identifying the regime:** Ask "Can the implementer verify this is correct without showing it to someone?"
- Yes → Build. Specify deeply: functions, test cases, step-by-step plan.
- No → Refine. Specify goals and constraints only. Do NOT pre-specify values that depend on perception.
- Need to decide first → Explore. Time-box it, produce a decision, then Build or Refine.

Most features pass through multiple regimes: Explore → Build → Refine. Plan for the transitions.

### Work Modes

Each session operates in one mode at a time:

**1. Discuss (no code changes)**
- Every iteration **starts** here
- Determine scope, identify the work regime, specify accordingly
- Prioritize simplest solutions; check if existing code can be reused/extended
- Preserve existing architecture unless there's a clear reason to change it
- If context is missing, ask before proceeding
- **Ends with** a DEVPLAN update

**2. Code / Debug**
- **Code:** implement the plan from the discuss session
- **Debug:** propose a testable hypothesis first, then make changes
- Switching between code and debug within a session is expected

**3. Review**
- Goal: improve existing code, not write new features
- **Priority #1:** preserve existing functionality
- **Priority #2:** simplify and reduce code
- Confirm architecture alignment (no drift from spec)

### Phase Lifecycle

**Planning (Discuss mode):**
1. Determine scope and specific outcomes
2. Identify work regime (Build / Refine / Explore)
3. **Build:** break into smallest testable steps; create test specs
4. **Refine:** define goals, constraints, and first item to show; skip detailed step plans
5. **Explore:** define the decision to be made and time box
6. Update DEVPLAN

**Shortcut:** `/phase-plan` in Claude Code.

**Refine phase structure:**

| Stage | Focus | Content |
|-------|-------|---------|
| First | Goals & constraints | What "good" looks like, hard limits |
| Middle | Feedback loops | Iterative show→adjust cycles (count unknown upfront) |
| Last | Stabilization | Lock decisions, write tests for final state, document |

For Refine phases, plan a **time budget**, not a step count.

**Step execution:**
1. **Discuss:** specific changes, files affected, decisions needed
2. **Code/Debug**
3. **Verify:** run tests (Build) or show to human (Refine)
4. **Confirm:** human explicitly approves before proceeding
5. **Update DEVLOG** after confirmation
6. **Commit**

**Shortcut:** `/step-done` in Claude Code.

**Phase completion:**
1. Run phase-level tests (Build) or human sign-off (Refine)
2. Review (simplify, remove dead code)
3. Update DEVLOG, documentation pass
4. **DEVLOG learning review** — scan the phase's DEVLOG entries for trial-and-error patterns (anything that took multiple attempts to resolve). Extract prescriptive summaries and promote to the DEVPLAN Cold Start Summary's Gotchas field.
5. Propagate contract changes to upstream documents
6. DEVPLAN cleanup — reduce completed phase to summary + DEVLOG reference
7. Human confirms phase closure
8. Commit

**Shortcut:** `/phase-review` then `/phase-complete` in Claude Code.

### Cross-Module Integration

Before integrating modules A and B:
1. **Type compatibility** — verify A's output types match B's input types
2. **Boundary tests** — feed A's actual outputs into B's actual functions
3. **Bridge logic** — document any adapter/conversion needed

No module imports from the integration/orchestration layer. Subsystems do not import from each other except for shared types from upstream dependencies.

**Shortcut:** `/integration-check` in Claude Code.

### Contract Change Propagation

During module Build, information flows forward: ARCHITECTURE.md → ARCH docs → code. During cross-cutting work, information flows backward. Without explicit propagation, upstream documents silently drift.

**Contract-change markers:** When a DEVLOG entry modifies a shared contract, include a `### Contract Changes` section listing affected documents and specific contracts modified. If no shared contracts were modified, omit the section.

**Propagation rules:**
- **Immediate** (same session): Changes that modify a cross-module API signature or type. Test: "Would a cold-start session on another module produce incorrect code by reading the current ARCH doc?" If yes, propagate now.
- **Phase boundary** (batched): All other contract changes. At phase completion, scan DEVLOG's Contract Changes markers and update listed documents.

**Cross-cutting tracks** should declare their upstream document scope in the DEVPLAN Cold Start Summary.

### Upstream Revision

When implementation reveals that upstream documents need to change:

**Scope changes (PROJECT.md):**
Follow the revision protocol in PROJECT.md. Flexible scope changes can proceed inline. Core scope changes require pausing implementation and assessing impact against ARCHITECTURE.md.

**Architecture changes (ARCHITECTURE.md, ARCH files):**
If a module boundary needs to move or a contract was fundamentally wrong:
1. Pause implementation on affected modules
2. Update ARCHITECTURE.md and affected ARCH files
3. Re-run the stability check
4. Adjust implementation sequence if needed
5. Record the change as a decision (D-#) in the affected DEVLOG
6. Resume implementation

---

## Protocol

Hard-won rules that prevent specific failure modes.

### Confirmation Before Commit

Do not commit until human explicitly confirms. "Tests pass" is necessary but not sufficient — especially for Refine work, documentation, and cross-cutting changes.

Invoking `/step-done` constitutes explicit confirmation for step-level commits. Phase completion, contract propagation, and cross-cutting changes still require separate confirmation.

### Commit Discipline

**Commit vs amend:** "Commit" means create a new commit. "Amend" means modify the previous commit. Default to NEW commit. Only amend when human explicitly says "amend."

**Commit cadence:** One commit per logical unit, not per session. If a session covers visual design + data changes + API cleanup, those are three separate commits.

### Scope Management

**Scope declaration:** At the start of a Refine session, list the discrete work items.

**Scope expansion:** When scope grows mid-session, acknowledge it explicitly. Add to the list (do now) or defer. Log additions in the DEVLOG. Don't silently absorb new work.

### Structured Feedback Logging

When iterating visually (show → react → adjust), log each cycle in the DEVLOG. Failed attempts are especially valuable:

```
1. [Observation] Transport row sticks out past other elements
   Hypothesis: flex-wrap causing wrap when scrollbar appears
   Fix: removed flex-wrap
   Result: ✗ — scrollbar still steals layout width
2. [Same issue]
   Hypothesis: scrollbar-gutter: stable reserves constant space
   Fix: added scrollbar-gutter: stable
   Result: ✗ — scrollbar always visible, user rejected
3. [Root cause found] Native scrollbar steals 15px; rigid min-widths overflow
   Fix: thin 6px custom scrollbar + flex-shrink on tempo group
   Result: ✓ — resolved
```

### Session Protocol

Tactical habits for maintaining coherence within a session.

**Re-read before deciding.** Before any significant decision or direction change, re-read the DEVPLAN. Long sessions cause context drift.

**Error escalation:**
1. Diagnose and apply a targeted fix
2. Same error recurs — try a fundamentally different approach
3. Still failing — question assumptions, search for solutions, reconsider the plan
4. After three failures — stop and ask the human for guidance

**Don't re-read what you just wrote.** If you just created or modified a file, its contents are still in context. Only re-read when starting a new session or when the file may have been modified by another step.

### Sub-Track Pattern

When cross-cutting work grows beyond a few DEVLOG entries, spin it off into its own DEVPLAN/DEVLOG pair within the parent module directory.

**When to create a sub-track:**
- The work has its own cold-start context distinct from the parent
- It spans multiple sessions or design passes
- It touches files across multiple modules
- It has its own decision space

**Naming:** `DEVPLAN_<TOPIC>.md` / `DEVLOG_<TOPIC>.md`. Decision IDs use a topic prefix (e.g., `SB-D1` for sidebar).

**Lifecycle:** When complete, update the parent DEVPLAN's Current Status. Leave sub-track files as historical reference.

### Automation

When using autonomous AI execution, follow the Automation Boundary protocol (AUTOMATION.md) for work unit sizing, checkpoint frequency, and escalation criteria. Governance rules still apply; the automation protocol defines how they are satisfied without a human present at every step.
