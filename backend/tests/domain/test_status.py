from kairos.domain.status import CLOSED, ORDER, Status


def test_order_is_the_lifecycle():
    assert ORDER == (
        Status.PROPOSED,
        Status.BACKLOG,
        Status.READY,
        Status.IN_PROGRESS,
        Status.IN_REVIEW,
        Status.DONE,
    )


def test_closed_statuses():
    assert frozenset({Status.DONE, Status.CANCELLED}) == CLOSED
