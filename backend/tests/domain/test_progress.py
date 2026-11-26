import pytest

from kairos.domain.model import Criterion, Evidence, EvidenceKind, Task
from kairos.domain.progress import ChildProgress, container_progress, epic_status, task_progress
from kairos.domain.status import EpicStatus, Status

PROOF = Evidence(EvidenceKind.TEXT, "ran it", "a1")


def _task(status: Status = Status.IN_PROGRESS, criteria: tuple[Criterion, ...] = ()) -> Task:
    return Task(
        id="t",
        title="T",
        type="bug",
        project_id="p",
        created_by="a",
        status=status,
        criteria=criteria,
    )


def test_progress_of_a_done_task_is_one():
    assert task_progress(_task(Status.DONE)) == 1.0


def test_progress_is_criteria_with_evidence_over_total():
    criteria = (Criterion("c1", "x", (PROOF,)), Criterion("c2", "y"), Criterion("c3", "z"))
    assert task_progress(_task(criteria=criteria)) == pytest.approx(1 / 3)


def test_task_without_criteria_has_zero_progress():
    assert task_progress(_task()) == 0.0


def test_container_ignores_cancelled_children():
    children = [
        ChildProgress(Status.DONE, 1.0),
        ChildProgress(Status.IN_PROGRESS, 0.5),
        ChildProgress(Status.CANCELLED, 0.0),
    ]
    assert container_progress(children) == pytest.approx(0.75)


def test_container_without_children_is_zero():
    assert container_progress([]) == 0.0
    assert container_progress([ChildProgress(Status.CANCELLED, 0.0)]) == 0.0


@pytest.mark.parametrize(
    ("children", "expected"),
    [
        ([], EpicStatus.NOT_STARTED),
        ([Status.BACKLOG, Status.READY], EpicStatus.NOT_STARTED),
        ([Status.READY, Status.IN_PROGRESS], EpicStatus.IN_PROGRESS),
        ([Status.BACKLOG, Status.IN_REVIEW], EpicStatus.IN_PROGRESS),
        ([Status.DONE, Status.BACKLOG], EpicStatus.IN_PROGRESS),
        ([Status.DONE, Status.DONE], EpicStatus.COMPLETE),
        ([Status.DONE, Status.CANCELLED], EpicStatus.COMPLETE),
        ([Status.CANCELLED, Status.CANCELLED], EpicStatus.COMPLETE),
    ],
)
def test_epic_status_table(children: list[Status], expected: EpicStatus):
    assert epic_status(children) is expected
