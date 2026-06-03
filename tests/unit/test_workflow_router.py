from shannon_py.orchestration.router import WorkflowMode, WorkflowRouter


def test_workflow_router_respects_explicit_mode() -> None:
    router = WorkflowRouter()

    route = router.route("simple query", WorkflowMode.REACT, {})

    assert route.selected_mode == WorkflowMode.REACT


def test_workflow_router_auto_selects_simple_for_low_complexity() -> None:
    router = WorkflowRouter()

    route = router.route("hello", WorkflowMode.AUTO, {})

    assert route.selected_mode == WorkflowMode.SIMPLE


def test_workflow_router_auto_selects_research_when_forced() -> None:
    router = WorkflowRouter()

    route = router.route("hello", WorkflowMode.AUTO, {"force_research": True})

    assert route.selected_mode == WorkflowMode.RESEARCH
