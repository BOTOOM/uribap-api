from collections.abc import Generator

from fastapi import Request
from sqlalchemy.orm import Session

from uribap_api.infrastructure.database import get_db_session
from uribap_api.infrastructure.logging import get_request_id


def get_session(request: Request) -> Generator[Session]:
    session_factory = request.app.state.session_factory
    yield from get_db_session(session_factory)


def request_id() -> str:
    return get_request_id()
