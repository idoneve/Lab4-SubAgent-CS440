import copy

from agent_strategy4 import (
    INITIAL_GRID,
    SubAgentExecuteStep,
    SubAgentLocateDirt,
    SubAgentOrchestrator,
    SubAgentPlanPath,
    VacuumEnvironment,
)


def test_initial_grid_is_assignment_grid_and_environment_copies_it():
    expected = [
        ["start", 0, 0, 0],
        [0, "X", 0, 0],
        [0, 0, 0, 0],
        [0, -1, 0, 10],
    ]

    environment = VacuumEnvironment(INITIAL_GRID)
    environment.grid[0][0] = "changed"

    assert INITIAL_GRID == expected


def test_locator_finds_current_and_first_dirty_neighbor():
    locator = SubAgentLocateDirt()

    assert locator.run(
        {"pos": (1, 2), "dirty": True, "neighbors": {}}
    ) == (1, 2)

    percept = {
        "pos": (0, 0),
        "dirty": False,
        "neighbors": {"UP": None, "DOWN": 0, "LEFT": None, "RIGHT": 0},
        "dirty_neighbors": {"UP": False, "DOWN": True, "LEFT": False, "RIGHT": True},
    }
    assert locator.run(percept) == (1, 0)


def test_planner_returns_first_bfs_action_around_blocked_cell():
    planner = SubAgentPlanPath()

    action = planner.run((0, 0), (2, 1), blocked={(1, 1)})

    assert action == "DOWN"
    assert planner.last_path_length == 3


def test_planner_returns_none_for_blocked_goal():
    planner = SubAgentPlanPath()

    assert planner.run((0, 0), (1, 1), blocked={(1, 1)}) is None


def test_executor_rejects_unsafe_actions():
    executor = SubAgentExecuteStep()
    percept = {
        "pos": (0, 0),
        "cell": 0,
        "dirty": False,
        "neighbors": {"UP": None, "DOWN": 0, "LEFT": None, "RIGHT": 0},
    }

    assert executor.run(percept, "SUCK") == "RIGHT"
    assert executor.run(percept, "UP") == "RIGHT"
    assert executor.run(percept, "DOWN") == "DOWN"
    percept["dirty"] = True
    assert executor.run(percept, "SUCK") == "SUCK"


def test_orchestrator_delegates_dirty_neighbor_goal_to_planner(capsys):
    orchestrator = SubAgentOrchestrator()
    percept = {
        "pos": (0, 0),
        "cell": "start",
        "dirty": False,
        "neighbors": {"UP": None, "DOWN": 0, "LEFT": None, "RIGHT": 0},
        "dirty_neighbors": {"UP": False, "DOWN": False, "LEFT": False, "RIGHT": True},
    }

    action = orchestrator.program(percept)

    output = capsys.readouterr().out
    assert action == "RIGHT"
    assert "SubAgentLocateDirt" in output
    assert "SubAgentPlanPath" in output
    assert "BFS path length 1" in output
    assert "SubAgentExecuteStep" in output


def test_orchestrator_runs_and_logs_twenty_steps(capsys):
    environment = VacuumEnvironment(INITIAL_GRID)
    original_grid = copy.deepcopy(environment.grid)
    orchestrator = SubAgentOrchestrator(environment)

    orchestrator.run(steps=20)

    output = capsys.readouterr().out
    assert output.count("[init]") == 4
    assert "[step 1] ORCH" in output
    assert "Final grid:" in output
    assert "subagent_log summary:" in output
    assert orchestrator.memory["step_count"] == 20
    assert orchestrator.memory["visited"]
    assert all(
        0 <= row < len(INITIAL_GRID) and 0 <= col < len(INITIAL_GRID[row])
        for row, col in orchestrator.memory["visited"]
    )
    assert environment.grid == original_grid
