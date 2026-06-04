from shannon_py.swarm import SwarmCoordinator, SwarmTaskStatus


def test_swarm_coordinator_creates_and_assigns_tasks() -> None:
    coordinator = SwarmCoordinator()

    tasks = coordinator.create_swarm("first; second")
    assigned = coordinator.assign_tasks("agent_1")

    assert len(tasks) == 2
    assert len(assigned) == 2
    assert all(task.assigned_to == "agent_1" for task in assigned)
    assert all(task.status == SwarmTaskStatus.IN_PROGRESS for task in assigned)


def test_swarm_coordinator_records_messages_and_convergence() -> None:
    coordinator = SwarmCoordinator()

    tasks = coordinator.create_swarm("single task")
    coordinator.complete_task(tasks[0].task_id)
    message = coordinator.publish_findings("agent_1", "lead", "done")

    assert message.content == "done"
    assert coordinator.mailbox.inbox("lead")[0].content == "done"
    assert coordinator.converged() is True


async def test_swarm_coordinator_executes_worker_tasks_with_runtime() -> None:
    coordinator = SwarmCoordinator()

    results = await coordinator.execute_pending_tasks("first; second")

    assert len(results) == 2
    assert coordinator.converged() is True
    assert len(coordinator.mailbox.inbox("lead")) == 2
    assert coordinator.workspace.get("results") == results
