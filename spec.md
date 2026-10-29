# spec.md — Strategy 4: Sub-Agent Isolation Vacuum Agent

## Goal

Implement a Python agent for the AIMA vacuum world that uses a
sub-agent isolation architecture. The main "orchestrator" agent does
NOT make low-level decisions itself — it delegates each subtask to a
separate, isolated sub-agent, and only aggregates their results.
Today: scaffolding only, NO Q-learning.

## Environment Contract (implemented in vacuum_env.py, do not modify here)

- Grid: 4x4. Coordinates are (row, col), 0-indexed.
- Initial state (MUST be used — see "Initial State" section below).
- Cells: 'start' (robot start, at (0,0)), 'X' (obstacle),
  -1 (penalty), 10 (reward), 0 (plain).
- Actions: 'UP', 'DOWN', 'LEFT', 'RIGHT', 'SUCK'.
- Percepts available to the agent each step:
    {
      "pos": (row, col),
      "cell": <cell value>,
      "dirty": bool,
      "neighbors": {
          "UP": <cell value or None>,
          "DOWN": ..., "LEFT": ..., "RIGHT": ...
      }
    }

## Initial State — REQUIRED

The orchestrator MUST be constructed against the assignment's initial
state, hardcoded in the spec and in the generated file:

    INITIAL_GRID = [
        ["start",  0,  0,  0],
        [ 0,      "X", 0,  0],
        [ 0,       0,  0,  0],
        [ 0,      -1,  0,  10],
    ]

- The orchestrator must instantiate / connect to a `VacuumEnvironment`
  built from this exact grid (do NOT expect the notebook or caller to
  pass it in — construct it here if `env` is not provided).
- The file must contain a `if __name__ == "__main__":` block that runs
  the orchestrator on `INITIAL_GRID` for at least 20 steps and prints
  the trace, so it can be demonstrated standalone.
- Do NOT change grid values, coordinates, or cell symbols.

## Architecture — Sub-Agent Isolation (the core requirement)

Define THREE isolated sub-agents, each as its own class with a single
`run(...)` method and NO reference to the orchestrator's state:

### SubAgentLocateDirt

- Input:  `percept`
- Output: `(r, c) | None` — nearest known-dirty cell, or None
- Rule:  if `percept["dirty"]` → return current pos; else scan
  `neighbors` and return the first dirty neighbor; else None.
- Constraint: knows ONLY the percept it is handed.

### SubAgentPlanPath

- Input:  `start: (r,c)`, `goal: (r,c)`, `blocked: set[(r,c)]`
- Output: `str | None` — first action toward goal (BFS), or None
- Constraint: knows ONLY start, goal, blocked. It must NOT read the
  orchestrator's memory or the environment's full grid.

### SubAgentExecuteStep

- Input:  `percept`, `action: str`
- Output: `action` after a safety check (e.g. refuse 'SUCK' if not
  dirty → return 'RIGHT' or another valid move).
- Constraint: validates a single action only.

## Orchestrator Contract (`agent_strategy4.py`)

Define class `SubAgentOrchestrator` with:

### State

    self.env           = env
    self.locate        = SubAgentLocateDirt()
    self.planner       = SubAgentPlanPath()
    self.executor      = SubAgentExecuteStep()
    self.memory        = {
        "visited": set(),
        "obstacles": set(),
        "rewards": {},
        "last_action": None,
        "step_count": 0,
        "subagent_log": [],   # one entry per sub-agent call
    }

### Methods

- `__init__(self, env=None)` — if `env is None`, build one from
  `INITIAL_GRID`. Then explicitly log each sub-agent instantiation:
      `[init] instantiated SubAgentLocateDirt, SubAgentPlanPath, SubAgentExecuteStep`
- `update_memory(self, percept, action, note)` — same explicit style
  as Strategy 1 (named steps, one update per block, `_log` call each).
- `program(self, percept) -> str` — MUST delegate, in this order:
      1. If `percept["dirty"]` → ask executor to validate 'SUCK'.
      2. Else ask `locate.run(percept)` for a goal.
      3. If goal → ask `planner.run(pos, goal, blocked=obstacles)`
         → hand the planned action to `executor.run(percept, action)`.
      4. If no goal / no path → fall back to an unvisited neighbor.
      5. Log every delegation with sub-agent name, inputs, and output.
- `_log(self, source, note)` — append to `memory["subagent_log"]`
  AND `print()` a trace line. `source` is 'orchestrator' or the
  sub-agent class name.

## Verbose Logging — REQUIRED (construction AND runtime)

Logging is mandatory at three moments, and the format must match:

### 1. Construction-time logs

Print one line per sub-agent as it is instantiated, plus one line for
the orchestrator itself, e.g.:
    [init] SubAgentLocateDirt ready (rules: current-cell, neighbor-scan)
    [init] SubAgentPlanPath ready (algorithm: BFS)
    [init] SubAgentExecuteStep ready (validation: SUCK-guard)
    [init] SubAgentOrchestrator ready on INITIAL_GRID

### 2. Per-step delegation logs (runtime)

Every call from orchestrator → sub-agent must be logged with:
    [step N] ORCH → SubAgentPlanPath(start=(0,0), goal=(0,1), blocked={...})
    [step N] SubAgentPlanPath → 'RIGHT' (BFS path length 1)
    [step N] ORCH chose 'RIGHT' (delegated, validated by SubAgentExecuteStep)

### 3. Memory-update logs

Same as Strategy 1: named blocks, one `_log(...)` per logical update.

### Forbidden patterns

- Orchestrator computing BFS directly (must call `SubAgentPlanPath`).
- Orchestrator inspecting `env.grid` directly.
- Sub-agents referencing `self.orchestrator` or each other.
- Silent sub-agent calls with no `_log(...)` entry.
- Compressing the memory schema into a one-liner.
- Inlining any sub-agent logic with a lambda/comprehension.

## Required reference style (match this in generated code)

    def program(self, percept):
        pos = percept["pos"]

        # --- Rule 1: dirty current cell → SUCK (validated) ---
        if percept["dirty"]:
            action = self.executor.run(percept, "SUCK")
            self._log("orchestrator", f"delegated SUCK validation → {action}")
            return action

        # --- Rule 2: ask locator for nearest dirty ---
        goal = self.locate.run(percept)
        self._log("SubAgentLocateDirt", f"goal={goal}")
        if goal is not None:
            # --- Rule 3: ask planner for next step ---
            action = self.planner.run(pos, goal, self.memory["obstacles"])
            self._log("SubAgentPlanPath", f"plan({pos}→{goal}) → {action}")
            if action is not None:
                safe = self.executor.run(percept, action)
                self._log("SubAgentExecuteStep", f"validated {action} → {safe}")
                return safe

        # --- Rule 4: explore unvisited neighbor ---
        for d in ("UP", "DOWN", "LEFT", "RIGHT"):
            nbr = self._neighbor_coord(pos, d)
            if nbr and nbr not in self.memory["visited"]:
                self._log("orchestrator", f"explore fallback → {d}")
                return d
        return "RIGHT"

## Constraints

- Pure Python 3.10+, standard library only.
- Orchestrator MUST NOT read `env.grid` — only percepts.
- Sub-agents MUST NOT touch orchestrator state or each other.
- The file MUST run standalone via `python agent_strategy4.py`.
- Every public method has a docstring.

## Test Expectations (standalone run)

Running `python agent_strategy4.py` should:

- print the four `[init]` lines,
- run ≥20 steps on `INITIAL_GRID`,
- show at least one `ORCH → SubAgentPlanPath` delegation log per step
  where a dirty goal exists,
- print the final grid and the `subagent_log` summary,
- never crash on out-of-bounds moves or on `None` returns.
