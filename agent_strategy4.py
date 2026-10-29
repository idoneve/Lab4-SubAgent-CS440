"""Strategy 4: a vacuum agent coordinated through isolated sub-agents."""

from collections import deque


INITIAL_GRID = [
    ["start", 0, 0, 0],
    [0, "X", 0, 0],
    [0, 0, 0, 0],
    [0, -1, 0, 10],
]

DIRECTIONS = ("UP", "DOWN", "LEFT", "RIGHT")
ACTION_DELTAS = {
    "UP": (-1, 0),
    "DOWN": (1, 0),
    "LEFT": (0, -1),
    "RIGHT": (0, 1),
}


class VacuumEnvironment:
    """Provide the grid and percept contract needed for a standalone run."""

    def __init__(self, grid=INITIAL_GRID):
        """Create an independent environment from a grid."""
        self.grid = []
        for row in grid:
            self.grid.append(list(row))
        self.pos = (0, 0)
        self.dirty_cells = set()

    def percept(self):
        """Return the agent's position, cell, dirt status, and neighbor cells."""
        row, col = self.pos
        neighbors = {}
        for direction in DIRECTIONS:
            delta_row, delta_col = ACTION_DELTAS[direction]
            neighbor_row = row + delta_row
            neighbor_col = col + delta_col
            if (
                0 <= neighbor_row < len(self.grid)
                and 0 <= neighbor_col < len(self.grid[neighbor_row])
            ):
                neighbors[direction] = self.grid[neighbor_row][neighbor_col]
            else:
                neighbors[direction] = None

        return {
            "pos": self.pos,
            "cell": self.grid[row][col],
            "dirty": self.pos in self.dirty_cells,
            "neighbors": neighbors,
        }

    def step(self, action):
        """Apply one valid action, keeping movement inside open grid cells."""
        if action == "SUCK":
            self.dirty_cells.discard(self.pos)
            return self.percept()

        if action not in ACTION_DELTAS:
            return self.percept()

        delta_row, delta_col = ACTION_DELTAS[action]
        row, col = self.pos
        next_row = row + delta_row
        next_col = col + delta_col
        if (
            0 <= next_row < len(self.grid)
            and 0 <= next_col < len(self.grid[next_row])
            and self.grid[next_row][next_col] != "X"
        ):
            self.pos = (next_row, next_col)
        return self.percept()

    def render(self):
        """Return a printable view of the grid and the agent's position."""
        lines = []
        for row_index, row in enumerate(self.grid):
            cells = []
            for col_index, cell in enumerate(row):
                if self.pos == (row_index, col_index):
                    cells.append("A")
                else:
                    cells.append(str(cell))
            lines.append(" ".join(f"{cell:>5}" for cell in cells))
        return "\n".join(lines)


class SubAgentLocateDirt:
    """Find a dirty cell using only the supplied percept."""

    def run(self, percept):
        """Return the current position or first dirty neighboring position."""
        if percept["dirty"]:
            return percept["pos"]

        row, col = percept["pos"]
        neighbors = percept["neighbors"]
        dirty_neighbors = percept.get("dirty_neighbors", {})
        for direction in DIRECTIONS:
            neighbor = neighbors.get(direction)
            is_dirty = dirty_neighbors.get(direction, False)
            if isinstance(neighbor, str) and neighbor.lower() in ("dirt", "dirty"):
                is_dirty = True
            if isinstance(neighbor, dict) and neighbor.get("dirty", False):
                is_dirty = True
            if not is_dirty:
                continue

            delta_row, delta_col = ACTION_DELTAS[direction]
            return row + delta_row, col + delta_col
        return None


class SubAgentPlanPath:
    """Find a shortest route using only the supplied coordinates and blocks."""

    def run(self, start, goal, blocked):
        """Return the first BFS action from start to goal, or None."""
        self.last_path_length = None
        if start == goal or goal in blocked:
            return None

        queue = deque([start])
        visited = {start}
        first_actions = {}
        distances = {start: 0}

        while queue:
            current = queue.popleft()
            current_row, current_col = current
            for direction in DIRECTIONS:
                delta_row, delta_col = ACTION_DELTAS[direction]
                neighbor = (current_row + delta_row, current_col + delta_col)
                if neighbor in blocked or neighbor in visited:
                    continue
                visited.add(neighbor)
                distances[neighbor] = distances[current] + 1
                if current == start:
                    first_actions[neighbor] = direction
                else:
                    first_actions[neighbor] = first_actions[current]
                if neighbor == goal:
                    self.last_path_length = distances[neighbor]
                    return first_actions[neighbor]
                queue.append(neighbor)
        return None


class SubAgentExecuteStep:
    """Validate a single proposed action against the supplied percept."""

    def run(self, percept, action):
        """Return the action when safe, otherwise choose an open movement."""
        if action == "SUCK":
            if percept["dirty"]:
                return "SUCK"
        elif action in ACTION_DELTAS:
            neighbor = percept["neighbors"].get(action)
            if neighbor is not None and neighbor != "X":
                return action

        for direction in ("RIGHT", "DOWN", "LEFT", "UP"):
            neighbor = percept["neighbors"].get(direction)
            if (
                direction != action
                and neighbor is not None
                and neighbor != "X"
            ):
                return direction
        return "RIGHT"


class SubAgentOrchestrator:
    """Delegate vacuum decisions to isolated sub-agents."""

    def __init__(self, env=None):
        """Initialize the environment, sub-agents, and persistent memory."""
        self.env = VacuumEnvironment(INITIAL_GRID) if env is None else env
        self.locate = SubAgentLocateDirt()
        print("[init] SubAgentLocateDirt ready (rules: current-cell, neighbor-scan)")
        self.planner = SubAgentPlanPath()
        print("[init] SubAgentPlanPath ready (algorithm: BFS)")
        self.executor = SubAgentExecuteStep()
        print("[init] SubAgentExecuteStep ready (validation: SUCK-guard)")
        self.memory = {
            "visited": set(),
            "obstacles": set(),
            "rewards": {},
            "last_action": None,
            "step_count": 0,
            "subagent_log": [],
        }
        environment_name = "INITIAL_GRID" if env is None else "provided environment"
        print(
            "[init] SubAgentOrchestrator ready on "
            f"{environment_name} (instantiated SubAgentLocateDirt, "
            "SubAgentPlanPath, SubAgentExecuteStep)"
        )

    def update_memory(self, percept, action, note):
        """Record observed position, obstacles, rewards, and the previous action."""
        self.memory["step_count"] += 1
        pos = percept["pos"]

        self.memory["visited"].add(pos)
        self._log("orchestrator", f"memory.visited: recorded {pos} ({note})")

        row, col = pos
        for direction in DIRECTIONS:
            neighbor_cell = percept["neighbors"].get(direction)
            if neighbor_cell == "X" or neighbor_cell is None:
                delta_row, delta_col = ACTION_DELTAS[direction]
                self.memory["obstacles"].add((row + delta_row, col + delta_col))
        self._log(
            "orchestrator",
            f"memory.obstacles: {self.memory['obstacles']}",
        )

        cell = percept["cell"]
        if isinstance(cell, (int, float)) and not isinstance(cell, bool) and cell != 0:
            self.memory["rewards"][pos] = cell
        self._log(
            "orchestrator",
            f"memory.rewards: {self.memory['rewards']}",
        )

        self.memory["last_action"] = action
        self._log("orchestrator", f"memory.last_action: {action!r}")
        self._log(
            "orchestrator",
            f"memory.step_count: {self.memory['step_count']}",
        )

    def program(self, percept):
        """Choose an action by delegating dirty search, planning, and validation."""
        pos = percept["pos"]

        # --- Rule 1: dirty current cell → SUCK (validated) ---
        if percept["dirty"]:
            self._log(
                "orchestrator",
                "→ SubAgentExecuteStep(percept=current, action='SUCK')",
            )
            action = self.executor.run(percept, "SUCK")
            self._log("SubAgentExecuteStep", f"→ {action!r} (SUCK safety check)")
            self._log("orchestrator", f"chose {action!r} (delegated, validated)")
            return action

        # --- Rule 2: ask locator for nearest dirty ---
        self._log("orchestrator", f"→ SubAgentLocateDirt(percept={percept!r})")
        goal = self.locate.run(percept)
        self._log("SubAgentLocateDirt", f"→ goal={goal}")
        if goal is not None:
            # --- Rule 3: ask planner for next step ---
            blocked = self.memory["obstacles"]
            self._log(
                "orchestrator",
                f"→ SubAgentPlanPath(start={pos}, goal={goal}, blocked={blocked})",
            )
            action = self.planner.run(pos, goal, blocked)
            path_length = self.planner.last_path_length
            if action is None:
                plan_result = "None (no path)"
            else:
                plan_result = f"{action!r} (BFS path length {path_length})"
            self._log("SubAgentPlanPath", f"→ {plan_result}")
            if action is not None:
                self._log(
                    "orchestrator",
                    f"→ SubAgentExecuteStep(percept=current, action={action!r})",
                )
                safe = self.executor.run(percept, action)
                self._log(
                    "SubAgentExecuteStep",
                    f"→ {safe!r} (validated {action!r})",
                )
                self._log(
                    "orchestrator",
                    f"chose {safe!r} (delegated, validated by SubAgentExecuteStep)",
                )
                return safe

        # --- Rule 4: explore unvisited neighbor ---
        for direction in DIRECTIONS:
            neighbor = self._neighbor_coord(pos, direction)
            cell = percept["neighbors"].get(direction)
            if (
                neighbor is not None
                and neighbor not in self.memory["visited"]
                and neighbor not in self.memory["obstacles"]
                and cell is not None
                and cell != "X"
            ):
                self._log("orchestrator", f"explore fallback → {direction}")
                return direction
        self._log("orchestrator", "explore fallback exhausted → RIGHT")
        return "RIGHT"

    def _neighbor_coord(self, pos, direction):
        """Return an adjacent coordinate, or None when it is out of bounds."""
        delta_row, delta_col = ACTION_DELTAS[direction]
        neighbor = (pos[0] + delta_row, pos[1] + delta_col)
        if (
            0 <= neighbor[0] < len(INITIAL_GRID)
            and 0 <= neighbor[1] < len(INITIAL_GRID[neighbor[0]])
        ):
            return neighbor
        return None

    def _log(self, source, note):
        """Store and print one trace entry for an update or delegation."""
        entry = {
            "step": self.memory["step_count"],
            "source": source,
            "note": note,
        }
        self.memory["subagent_log"].append(entry)
        if source == "orchestrator":
            print(f"[step {entry['step']}] ORCH {note}")
        else:
            print(f"[step {entry['step']}] {source} {note}")

    def run(self, steps=20):
        """Run the agent for the requested number of steps and print a summary."""
        for _ in range(steps):
            percept = self.env.percept()
            self.update_memory(
                percept,
                self.memory["last_action"],
                "observed percept",
            )
            action = self.program(percept)
            self.memory["last_action"] = action
            self._log("orchestrator", f"memory.last_action: selected {action!r}")
            self.env.step(action)

        print("\nFinal grid:")
        print(self.env.render())
        print(f"\nsubagent_log summary: {len(self.memory['subagent_log'])} entries")
        for entry in self.memory["subagent_log"]:
            print(
                f"  step {entry['step']}: {entry['source']} — {entry['note']}"
            )


if __name__ == "__main__":
    orchestrator = SubAgentOrchestrator()
    orchestrator.run(steps=20)
