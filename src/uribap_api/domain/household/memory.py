from enum import StrEnum


class MemoryKind(StrEnum):
    LIKE = "like"
    DISLIKE = "dislike"
    RESTRICTION = "restriction"
    GOAL = "goal"
    NOTE = "note"
