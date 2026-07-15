from __future__ import annotations

import hashlib
import io
import shutil
import subprocess
import time
import wave
from pathlib import Path

import av
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings
from app.inference import InferencePipeline
from app.main import create_app
from app.singing import SeedVCRunner

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


def webm_opus_bytes(duration: float = 0.7) -> bytes:
    buffer = io.BytesIO()
    frame_count = round(duration / 0.02)
    with av.open(buffer, mode="w", format="webm") as output:
        stream = output.add_stream("libopus", rate=48000)
        stream.layout = "mono"
        for _ in range(frame_count):
            frame = av.AudioFrame(format="s16", layout="mono", samples=960)
            frame.sample_rate = 48000
            frame.planes[0].update(b"\x00\x00" * 960)
            for packet in stream.encode(frame):
                output.mux(packet)
        for packet in stream.encode(None):
            output.mux(packet)
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
        stt_model="openai/whisper-small",
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
        if index == 0:
            filename = "sample-0.webm"
            content = webm_opus_bytes()
            content_type = "audio/webm;codecs=opus"
        else:
            filename = f"sample-{index}.wav"
            content = wav_bytes()
            content_type = "audio/wav"
        response = client.post(
            f"/v1/voice-profiles/{profile_id}/samples",
            headers=HEADERS,
            data={"prompt_text": f"샘플 문장 {index + 1}입니다."},
            files={"audio": (filename, content, content_type)},
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

        capabilities = client.get("/v1/recording-capabilities", headers=HEADERS)
        assert capabilities.status_code == 200
        assert capabilities.json()["preferred_mime_types"][0] == "audio/webm;codecs=opus"
        assert capabilities.json()["page_recording_upload"] == {
            "method": "PUT",
            "path_template": "/v1/books/{book_id}/pages/{page_number}/recording",
            "audio_field": "audio",
            "additional_fields": ["profile_id"],
        }

        profile_id = create_ready_profile(client)
        profile = client.get(f"/v1/voice-profiles/{profile_id}", headers=HEADERS).json()
        assert profile["status"] == "ready"
        assert profile["sample_count"] == 5
        assert len(list((tmp_path / "audio" / "profiles").glob("*.wav"))) == 1
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
        assert manifest["mode"] == "manual"
        assert manifest["default_source"] == "clarified"
        assert manifest["source_toggle_enabled"] is True
        assert manifest["transition_budget_ms"] == 300
        assert manifest["pages"][0]["version"] == 2
        assert manifest["pages"][0]["available_sources"] == ["original", "clarified"]
        assert manifest["pages"][1]["clarified_url"] is None
        assert manifest["pages"][1]["available_sources"] == []

        catalog = client.get("/v1/singing-lullabies/catalog", headers=HEADERS)
        assert catalog.status_code == 200
        assert len(catalog.json()) == 1
        assert catalog.json()[0]["id"] == "little-star-english"
        assert catalog.json()[0]["title"] == "작은별_영문"
        source = catalog.json()[0]
        assert source["recording_license"] == "CC0 1.0"
        source_audio = client.get(source["audio_url"], headers=HEADERS)
        assert source_audio.status_code == 200
        assert source_audio.headers["content-type"].startswith("audio/wav")
        response = client.post(
            "/v1/singing-lullabies/conversions",
            headers=HEADERS,
            json={
                "source_id": source["id"],
                "profile_id": profile_id,
                "repeat_count": 2,
                "timer_minutes": 15,
            },
        )
        assert response.status_code == 202, response.text
        assert wait_job(client, response.json()["job_id"])["status"] == "succeeded"
        conversions = client.get("/v1/singing-lullabies/conversions", headers=HEADERS).json()
        assert len(conversions) == 1
        conversion = conversions[0]
        assert conversion["title"] == source["title"]
        assert conversion["diffusion_steps"] == 10
        assert client.get(conversion["audio_url"], headers=HEADERS).status_code == 200
        singing_plan = client.post(
            f"/v1/singing-lullabies/conversions/{conversion['id']}/playback-plan",
            headers=HEADERS,
            json={},
        )
        assert singing_plan.status_code == 200
        assert singing_plan.json()["repeat_count"] == 2
        assert singing_plan.json()["timer_seconds"] == 900

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
        playback_plan = client.post(
            f"/v1/lullabies/{lullaby['id']}/playback-plan",
            headers=HEADERS,
            json={},
        )
        assert playback_plan.status_code == 200
        assert playback_plan.json() == {
            "lullaby_id": lullaby["id"],
            "mode": "automatic",
            "audio_url": lullaby["playable_url"],
            "repeat_count": 3,
            "loop": True,
            "timer_seconds": 1200,
            "stop_on_timer": True,
        }
        assert lullaby["delete_url"] == f"/v1/lullabies/{lullaby['id']}"
        assert client.delete(lullaby["delete_url"], headers=HEADERS).status_code == 204
        remaining = client.get("/v1/library", headers=HEADERS).json()
        assert {item["kind"] for item in remaining} == {"book"}
        assert (
            client.delete(
                f"/v1/singing-lullabies/conversions/{conversion['id']}", headers=HEADERS
            ).status_code
            == 204
        )


def test_media_recorder_webm_can_be_uploaded_to_page_pipeline(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        profile_id = create_ready_profile(client)
        book = client.post(
            "/v1/books",
            headers=HEADERS,
            json={
                "title": "브라우저 녹음 동화",
                "pages": [{"page_number": 1, "text": "아기 돼지 삼 형제 이야기예요."}],
            },
        )
        assert book.status_code == 201

        recording = client.put(
            f"/v1/books/{book.json()['id']}/pages/1/recording",
            headers=HEADERS,
            data={"profile_id": profile_id},
            files={
                "audio": (
                    "page-1.webm",
                    webm_opus_bytes(),
                    "audio/webm;codecs=opus",
                )
            },
        )
        assert recording.status_code == 202, recording.text
        assert wait_job(client, recording.json()["job_id"])["status"] == "succeeded"

        detail = client.get(f"/v1/books/{book.json()['id']}", headers=HEADERS).json()
        assert detail["pages"][0]["recording"]["status"] == "succeeded"
        original_url = detail["pages"][0]["recording"]["original_url"]
        assert client.get(original_url, headers=HEADERS).status_code == 200


def test_recording_synthesizes_corrected_spoken_intent(monkeypatch, tmp_path: Path) -> None:
    spoken_transcript = "아빠가 오느른 조금 느저써"
    corrected_intent = "아빠가 오늘은 조금 늦었어."
    synthesized_texts: list[str] = []

    def transcribe(
        _pipeline: InferencePipeline,
        _audio_path: Path,
        _expected_text: str | None = None,
    ) -> str:
        return spoken_transcript

    def correct_sentence(
        _pipeline: InferencePipeline,
        transcript: str,
        expected_text: str | None = None,
    ) -> str:
        assert transcript == spoken_transcript
        assert expected_text is None
        return corrected_intent

    def synthesize(
        pipeline: InferencePipeline,
        text: str,
        _reference_path: Path,
        output_path: Path,
        _emotion: str = "중립",
    ) -> None:
        synthesized_texts.append(text)
        pipeline._write_mock_wav(output_path, 0.7)

    monkeypatch.setattr(InferencePipeline, "transcribe", transcribe)
    monkeypatch.setattr(InferencePipeline, "correct_sentence", correct_sentence)
    monkeypatch.setattr(InferencePipeline, "synthesize", synthesize)

    with make_client(tmp_path) as client:
        profile_id = create_ready_profile(client)
        response = client.post(
            "/v1/books",
            headers=HEADERS,
            json={
                "title": "발화 의도 테스트",
                "author": "담음",
                "pages": [{"page_number": 1, "text": "달님이 환하게 웃었어요."}],
            },
        )
        book_id = response.json()["id"]
        response = client.put(
            f"/v1/books/{book_id}/pages/1/recording",
            headers=HEADERS,
            data={"profile_id": profile_id},
            files={"audio": ("page.wav", wav_bytes(), "audio/wav")},
        )
        assert response.status_code == 202
        assert wait_job(client, response.json()["job_id"])["status"] == "succeeded"

        book = client.get(f"/v1/books/{book_id}", headers=HEADERS).json()
        recording = book["pages"][0]["recording"]
        assert recording["transcript"] == spoken_transcript
        assert recording["corrected_text"] == corrected_intent
        assert recording["corrected_text"] != book["pages"][0]["text"]
        assert synthesized_texts[-1] == corrected_intent


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


def test_stt_adapter_integrity_and_health_contract(tmp_path: Path) -> None:
    settings = Settings(
        environment="test",
        api_key=API_KEY,
        data_dir=tmp_path,
        inference_backend="mock",
    )
    adapter = settings.resolved_stt_adapter_dir / "adapter_model.safetensors"
    assert adapter.is_file()
    assert hashlib.sha256(adapter.read_bytes()).hexdigest() == settings.stt_adapter_sha256

    with TestClient(create_app(settings)) as client:
        response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["models"]["stt"] == (
        "openai/whisper-small+whisper-small-lora-dysarthria"
    )


def test_stt_rejects_tampered_adapter(tmp_path: Path) -> None:
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir()
    (adapter_dir / "adapter_config.json").write_text("{}", encoding="utf-8")
    (adapter_dir / "adapter_model.safetensors").write_bytes(b"tampered")
    settings = Settings(
        environment="test",
        api_key=API_KEY,
        data_dir=tmp_path / "data",
        inference_backend="real",
        stt_adapter_dir=adapter_dir,
    )
    pipeline = InferencePipeline(settings)
    try:
        pipeline._load_stt()
    except RuntimeError as exc:
        assert str(exc) == "STT LoRA 어댑터 무결성 검증에 실패했습니다"
    else:
        raise AssertionError("변조된 STT 어댑터가 거부되지 않았습니다")


def test_seedvc_runner_forces_cpu_and_sanitizes_secrets(monkeypatch, tmp_path: Path) -> None:
    runtime = tmp_path / "seed-vc"
    runtime.mkdir()
    (runtime / "inference.py").write_text("# pinned Seed-VC", encoding="utf-8")
    python = runtime / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    base_python = tmp_path / "base-python"
    base_python.write_text("", encoding="utf-8")
    python.symlink_to(base_python)
    source = tmp_path / "source.wav"
    reference = tmp_path / "data" / "audio" / "profiles" / "reference.wav"
    reference.parent.mkdir(parents=True)
    source.write_bytes(wav_bytes())
    reference.write_bytes(wav_bytes())
    output = tmp_path / "data" / "audio" / "seedvc" / "generated" / "result.wav"
    settings = Settings(
        environment="test",
        api_key=API_KEY,
        data_dir=tmp_path / "data",
        inference_backend="real",
        seedvc_runtime_dir=runtime,
    )
    captured: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["environment"] = kwargs["env"]
        work = Path(command[command.index("--output") + 1])
        shutil.copyfile(source, work / "converted.wav")
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setenv("DAMEUM_API_KEY", "must-not-leak")
    monkeypatch.setattr(SeedVCRunner, "_verify_runtime", lambda *_: None)
    monkeypatch.setattr("app.singing.subprocess.run", fake_run)
    SeedVCRunner(settings).convert(source, reference, output, 10, 0)

    command = captured["command"]
    environment = captured["environment"]
    assert command[0] == str(python)
    assert "--f0-condition" in command and command[command.index("--f0-condition") + 1] == "True"
    assert "--fp16" in command and command[command.index("--fp16") + 1] == "False"
    assert environment["CUDA_VISIBLE_DEVICES"] == "-1"
    assert "DAMEUM_API_KEY" not in environment
    assert output.read_bytes() == source.read_bytes()


def test_seedvc_long_source_is_split_for_cpu_memory(tmp_path: Path) -> None:
    source = tmp_path / "long-source.wav"
    source.write_bytes(wav_bytes(7.0))
    work = tmp_path / "work"
    work.mkdir()

    chunks = SeedVCRunner._split_source(source, work)

    assert len(chunks) == 3
    durations = []
    for chunk in chunks:
        with wave.open(str(chunk), "rb") as audio:
            durations.append(audio.getnframes() / audio.getframerate())
    assert max(durations) <= 3.2
    assert 6.9 <= sum(durations) <= 7.1
