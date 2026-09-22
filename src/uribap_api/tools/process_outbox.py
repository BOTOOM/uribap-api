"""Process pending email outbox entries once.

Usage: uv run python -m uribap_api.tools.process_outbox [--limit N]

With ``email_delivery_enabled`` false (the default) every pending intent is
marked ``suppressed`` with an ``email_delivery_intent`` audit row and no SMTP
connection is opened.
"""

import argparse

from uribap_api.application.event_service import process_outbox
from uribap_api.config import get_settings
from uribap_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Dispatch email outbox intents.")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        result = process_outbox(session, settings, limit=args.limit)
    print(
        "outbox: "
        f"claimed={result.claimed} suppressed={result.suppressed} "
        f"sent={result.sent} failed={result.failed}"
    )


if __name__ == "__main__":
    main()
