import pytest

from kairos.domain.model import ItemKind, Task, can_parent, is_blank
from kairos.domain.status import Status

K = ItemKind
# parent -> the child kinds it may hold (design §6.1: Project > Epic > Task > Subtask,
# a task may hang directly from a project).
ALLOWED: dict[ItemKind | None, set[ItemKind]] = {
    None: {K.PROJECT},
    K.PROJECT: {K.EPIC, K.TASK},
    K.EPIC: {K.TASK},
    K.TASK: {K.SUBTASK},
    K.SUBTASK: set(),
}


@pytest.mark.parametrize("parent", [None, *ItemKind])
@pytest.mark.parametrize("child", list(ItemKind))
def test_can_parent_matrix(parent: ItemKind | None, child: ItemKind):
    assert can_parent(parent, child) is (child in ALLOWED[parent])


@pytest.mark.parametrize("text", [None, "", "  \n\t"])
def test_blank_texts(text: str | None):
    assert is_blank(text)


def test_non_blank_text():
    assert not is_blank(" x ")


def test_task_defaults_to_proposed_and_unassigned():
    task = Task(id="t1", title="T", type="bug", project_id="p1", created_by="a1")
    assert task.status is Status.PROPOSED
    assert task.assignee is None
    assert task.criteria == () and task.blocked_by == frozenset()
