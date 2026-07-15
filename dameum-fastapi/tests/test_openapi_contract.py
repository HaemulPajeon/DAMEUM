from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

HTTP_METHODS = {"get", "post", "put", "delete", "patch"}
CONTRACT_PATH = Path(__file__).parents[1] / "docs" / "openapi.json"


def openapi_document(tmp_path: Path) -> dict:
    settings = Settings(
        environment="test",
        api_key="openapi-test-key-with-at-least-32-characters",
        data_dir=tmp_path,
        inference_backend="mock",
    )
    return create_app(settings).openapi()


def operations(document: dict):
    for path, path_item in document["paths"].items():
        for method, operation in path_item.items():
            if method in HTTP_METHODS:
                yield path, method, operation


def test_openapi_is_frontend_ready(tmp_path: Path) -> None:
    document = openapi_document(tmp_path)
    api_operations = list(operations(document))
    operation_ids = [operation["operationId"] for _, _, operation in api_operations]

    assert document["openapi"].startswith("3.1.")
    assert len(api_operations) == 36
    assert len(operation_ids) == len(set(operation_ids))
    assert document["components"]["securitySchemes"]["APIKeyHeader"] == {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
        "description": "로컬 FastAPI와 프론트엔드가 공유하는 32자 이상의 API 키",
    }

    for path, _, operation in api_operations:
        assert operation.get("summary")
        assert operation.get("description")
        assert operation.get("tags")
        if path.startswith("/v1"):
            assert operation["security"] == [{"APIKeyHeader": []}]
            assert "401" in operation["responses"]
            assert "422" in operation["responses"]
            assert "500" in operation["responses"]


def test_binary_media_contract(tmp_path: Path) -> None:
    document = openapi_document(tmp_path)

    audio_paths = [
        "/v1/voice-profiles/{profile_id}/preview/audio",
        "/v1/books/{book_id}/pages/{page_number}/audio",
        "/v1/lullabies/{lullaby_id}/audio",
        "/v1/singing-lullabies/catalog/{source_id}/audio",
        "/v1/singing-lullabies/conversions/{conversion_id}/audio",
    ]
    for path in audio_paths:
        responses = document["paths"][path]["get"]["responses"]
        response = responses["200"]
        assert set(response["content"]) == {"audio/wav"}
        assert {"Accept-Ranges", "Content-Range", "ETag"} <= set(response["headers"])
        assert set(responses["206"]["content"]) == {"audio/wav"}
        assert set(responses["416"]["content"]) == {"text/plain"}

    image = document["paths"]["/v1/books/{book_id}/pages/{page_number}/image"]["get"]["responses"][
        "200"
    ]
    assert set(image["content"]) == {"image/webp"}
    assert "ETag" in image["headers"]


def test_committed_openapi_snapshot_is_current(tmp_path: Path) -> None:
    committed = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert committed == openapi_document(tmp_path), (
        "OpenAPI 계약이 변경되었습니다. "
        "`uv run python -m scripts.export_openapi`를 실행해 스냅샷을 갱신하세요."
    )


def test_local_swagger_serves_the_same_contract(tmp_path: Path) -> None:
    settings = Settings(
        environment="local",
        api_key="swagger-test-key-with-at-least-32-characters",
        data_dir=tmp_path,
        inference_backend="mock",
    )
    with TestClient(create_app(settings)) as client:
        docs_response = client.get("/docs")
        schema_response = client.get("/openapi.json")

    assert docs_response.status_code == 200
    assert "Swagger UI" in docs_response.text
    assert docs_response.headers["x-frame-options"] == "DENY"
    assert schema_response.status_code == 200
    assert schema_response.json() == create_app(settings).openapi()
