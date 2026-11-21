"""Guard legal batch status transitions."""

from typing import Literal

BatchStatus = Literal["processing", "completed", "rejected", "failed"]
ArchiveStatus = Literal["pending", "archived", "failed", "abandoned"]

BATCH_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "processing": frozenset({"completed", "rejected", "failed"}),
    "completed": frozenset(),
    "rejected": frozenset(),
    "failed": frozenset(),
}
ARCHIVE_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"archived", "failed", "abandoned"}),
    "archived": frozenset(),
    "failed": frozenset(),
    "abandoned": frozenset(),
}


def transition_batch_status(batch: object, target: BatchStatus) -> None:
    current = str(getattr(batch, "status"))
    validate_batch_status_transition(current, target)
    batch.status = target


def transition_archive_status(batch: object, target: ArchiveStatus) -> None:
    current = str(getattr(batch, "archive_status"))
    validate_archive_status_transition(current, target)
    batch.archive_status = target


def validate_batch_status_transition(current: str, target: BatchStatus) -> None:
    if current != target and target not in BATCH_STATUS_TRANSITIONS.get(current, frozenset()):
        raise ValueError(f"Illegal batch status transition: {current} -> {target}")


def validate_archive_status_transition(current: str, target: ArchiveStatus) -> None:
    if current != target and target not in ARCHIVE_STATUS_TRANSITIONS.get(current, frozenset()):
        raise ValueError(f"Illegal archive status transition: {current} -> {target}")
