import argparse
import json
from pathlib import Path

from uribap_api.main import app

DEFAULT_OUTPUT = Path("openapi/openapi.json")


def export_openapi(output: Path = DEFAULT_OUTPUT, *, check: bool = False) -> bool:
    document = app.openapi()
    rendered = json.dumps(document, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if check:
        return output.exists() and output.read_text(encoding="utf-8") == rendered
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    return 0 if export_openapi(args.output, check=args.check) else 1


if __name__ == "__main__":
    raise SystemExit(main())
