from dataclasses import dataclass


@dataclass(slots=True)
class DomainError(Exception):
    code: str
    title: str
    detail: str
    status_code: int = 400

    def __str__(self) -> str:
        return self.detail
