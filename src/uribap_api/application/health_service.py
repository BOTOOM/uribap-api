from sqlalchemy import Engine

from uribap_api.infrastructure.database import check_database


def database_is_ready(engine: Engine) -> bool:
    return check_database(engine)
