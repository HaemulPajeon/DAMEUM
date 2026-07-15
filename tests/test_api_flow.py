from __future__ import annotations

import io
import time
import wave
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings
from app.inference import InferencePipeline
from app.main import create_app

API_KEY = "test-api-key-that-is-longer-than-thirty-two-bytes"
HEADERS = {"X-API-Key": API_KEY}


def wav_bytes(duration: float = 0.7) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\x00\x00" * int(16000 * duration))
    return buffer.getvalue()


def image_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), color=(120, 180, 220)).save(buffer, "PNG")
    return buffer.getvalue()


def wait_job(client: TestClient, job_id: str) -> dict:
    for _ in range(100):
        response = client.get(f"/v1/jobs/{job_id}", headers=HEADERS)
        assert response.status_code == 200
        job = response.json()
        if job["status"] in {"succeeded", "failed"}:
            return job
        time.sleep(0.02)
    raise AssertionError("작업이 제한 시간 안에 끝나지 않았습니다")


def make_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        environment="test",
        api_key=API_KEY,
        data_dir=tmp_path,
        inference_backend="mock",
        cors_origins=["http://localhost:3000"],
    )
    return TestClient(create_app(settings))


def create_ready_profile(client: TestClient) -> str:
    response = client.post(
        "/v1/voice-profiles",
        headers=HEADERS,
        json={
            "name": "아빠 목소리",
            "source_kind": "current_voice",
            "consent_owner_name": "지훈",
            "consent_confirmed": True,
        },
    )
    assert response.status_code == 201
    profile_id = response.json()["id"]
    for index in range(5):
        response = client.post(
            f"/v1/voice-profiles/{profile_id}/samples",
            headers=HEADERS,
            data={"prompt_text": f"샘플 문장 {index + 1}입니다."},
            files={"audio": (f"sample-{index}.wav", wav_bytes(), "audio/wav")},
        )
        assert response.status_code == 201, response.text
    response = client.post(
        f"/v1/voice-profiles/{profile_id}/preview",
        headers=HEADERS,
        json={"text": "사랑하는 우리 아이야, 좋은 아침이야."},
    )
    assert response.status_code == 202
    assert wait_job(client, response.json()["job_id"])["status"] == "succeeded"
    return profile_id


def test_complete_local_demo_flow(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        assert client.get("/health/live").json() == {"status": "ok"}
        assert client.get("/v1/library").status_code == 401

        profile_id = create_ready_profile(client)
        profile = client.get(f"/v1/voice-profiles/{profile_id}", headers=HEADERS).json()
        assert profile["status"] == "ready"
        assert profile["sample_count"] == 5
        preview = client.get(profile["preview_url"], headers=HEADERS)
        assert preview.status_code == 200
        assert preview.headers["content-type"].startswith("audio/wav")

        response = client.post(
            "/v1/books",
            headers=HEADERS,
            json={
                "title": "달님 안녕",
                "author": "담음",
                "pages": [
                    {"page_number": 1, "text": "달님이 환하게 웃었어요."},
                    {"page_number": 2, "text": "아기도 방긋 웃었어요."},
                ],
            },
        )
        assert response.status_code == 201
        book_id = response.json()["id"]
        response = client.put(
            f"/v1/books/{book_id}/pages/1/image",
            headers=HEADERS,
            files={"image": ("page.png", image_bytes(), "image/png")},
        )
        assert response.status_code == 204

        response = client.put(
            f"/v1/books/{book_id}/pages/1/recording",
            headers=HEADERS,
            data={"profile_id": profile_id},
            files={"audio": ("page.wav", wav_bytes(), "audio/wav")},
        )
        assert response.status_code == 202, response.text
        assert wait_job(client, response.json()["job_id"])["status"] == "succeeded"

        book = client.get(f"/v1/books/{book_id}", headers=HEADERS).json()
        recording = book["pages"][0]["recording"]
        assert recording["corrected_text"] == "달님이 환하게 웃었어요."
        assert recording["emotion"] == "기쁨"
        assert client.get(recording["original_url"], headers=HEADERS).status_code == 200
        clarified = client.get(recording["clarified_url"], headers=HEADERS)
        assert clarified.status_code == 200
        assert clarified.headers["accept-ranges"] == "bytes"
        partial = client.get(
            recording["clarified_url"],
            headers={**HEADERS, "Range": "bytes=0-31"},
        )
        assert partial.status_code == 206
        assert len(partial.content) == 32
        assert partial.headers["content-range"].startswith("bytes 0-31/")

        response = client.put(
            f"/v1/books/{book_id}/pages/1/recording",
            headers=HEADERS,
            data={"profile_id": profile_id},
            files={"audio": ("page-new.wav", wav_bytes(0.8), "audio/wav")},
        )
        assert response.status_code == 202
        assert wait_job(client, response.json()["job_id"])["status"] == "succeeded"
        manifest = client.get(f"/v1/books/{book_id}/playback-manifest", headers=HEADERS).json()
        assert manifest["pages"][0]["version"] == 2
        assert manifest["pages"][1]["clarified_url"] is None

        response = client.post(
            "/v1/lullabies",
            headers=HEADERS,
            json={
                "profile_id": profile_id,
                "title": "잘 자라 우리 아가",
                "lyrics": "잘 자라 우리 아가, 포근한 꿈을 꾸렴.",
                "repeat_count": 3,
                "timer_minutes": 20,
            },
        )
        assert response.status_code == 202
        assert wait_job(client, response.json()["job_id"])["status"] == "succeeded"
        library = client.get("/v1/library", headers=HEADERS).json()
        assert {item["kind"] for item in library} == {"book", "lullaby"}
        lullaby = next(item for item in library if item["kind"] == "lullaby")
        assert client.get(lullaby["playable_url"], headers=HEADERS).status_code == 200


def test_upload_and_consent_validation(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.post(
            "/v1/voice-profiles",
            headers=HEADERS,
            json={
                "name": "동의 없음",
                "source_kind": "family_donation",
                "consent_owner_name": "가족",
                "consent_confirmed": False,
            },
        )
        assert response.status_code == 422

        response = client.post(
            "/v1/voice-profiles",
            headers=HEADERS,
            json={
                "name": "기증 음성",
                "source_kind": "family_donation",
                "consent_owner_name": "가족",
                "consent_confirmed": True,
            },
        )
        profile_id = response.json()["id"]
        response = client.post(
            f"/v1/voice-profiles/{profile_id}/samples",
            headers=HEADERS,
            data={"prompt_text": "안녕하세요."},
            files={"audio": ("fake.wav", b"not-an-audio", "audio/wav")},
        )
        assert response.status_code == 415
        response = client.post(
            f"/v1/voice-profiles/{profile_id}/preview",
            headers=HEADERS,
            json={},
        )
        assert response.status_code == 409


def test_real_model_label_order_and_original_format(monkeypatch, tmp_path: Path) -> None:
    assert InferencePipeline._normalize_emotion("LABEL_0") == "기쁨"
    assert InferencePipeline._normalize_emotion("LABEL_1") == "슬픔"
    assert InferencePipeline._normalize_emotion("LABEL_2") == "분노"
    assert InferencePipeline._normalize_emotion("LABEL_3") == "불안"
    assert InferencePipeline._normalize_emotion("LABEL_4") == "당황"
    assert InferencePipeline._normalize_emotion("LABEL_5") == "상처"

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"choices": [{"message": {"content": "달님이 환하게 웃었어요"}}]}

    class FakeClient:
        def __init__(self, **_: object):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def post(self, *_: object, **__: object) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("app.inference.httpx.Client", FakeClient)
    settings = Settings(
        environment="test",
        api_key=API_KEY,
        data_dir=tmp_path,
        inference_backend="real",
    )
    pipeline = InferencePipeline(settings)
    expected = "달님이 환하게 웃었어요."
    assert pipeline.correct_sentence("달님이 환하게 우떠요", expected) == expected
