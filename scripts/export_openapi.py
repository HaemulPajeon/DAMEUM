from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from app.config import Settings
from app.main import create_app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="프론트엔드 공유용 OpenAPI JSON을 생성합니다.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/openapi.json"),
        help="출력 경로(기본값: docs/openapi.json)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with tempfile.TemporaryDirectory(prefix="dameum-openapi-") as data_dir:
        settings = Settings(
            environment="test",
            api_key="openapi-export-key-with-at-least-32-characters",
            data_dir=Path(data_dir),
            inference_backend="mock",
        )
        document = create_app(settings).openapi()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"OpenAPI 계약 생성 완료: {args.output} ({len(document['paths'])} paths)")


if __name__ == "__main__":
    main()
