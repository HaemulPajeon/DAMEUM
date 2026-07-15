from __future__ import annotations

import platform
import subprocess

from app.config import Settings

REPOSITORY = "https://github.com/Plachtaa/seed-vc.git"


def run(command: list[str]) -> None:
    # 저장소에 고정된 설치 명령만 shell 없이 실행한다.
    subprocess.run(command, check=True)  # noqa: S603


def main() -> None:
    settings = Settings()
    runtime = settings.resolved_seedvc_runtime_dir
    if not runtime.exists():
        runtime.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--no-checkout", REPOSITORY, str(runtime)])
    run(["git", "-C", str(runtime), "fetch", "origin", settings.seedvc_commit])
    run(["git", "-C", str(runtime), "checkout", "--detach", settings.seedvc_commit])
    if not settings.seedvc_python_path.is_file():
        run(["uv", "venv", "--python", "3.10", str(runtime / ".venv")])
    requirements = "requirements-mac.txt" if platform.system() == "Darwin" else "requirements.txt"
    python = str(settings.seedvc_python_path)
    torch_command = [
        "uv",
        "pip",
        "install",
        "--python",
        python,
        "torch==2.4.1",
        "torchvision==0.19.1",
        "torchaudio==2.4.1",
    ]
    if platform.system() == "Windows":
        torch_command.extend(["--index-url", "https://download.pytorch.org/whl/cpu"])
    run(torch_command)
    packages = [
        line.strip()
        for line in (runtime / requirements).read_text(encoding="utf-8").splitlines()
        if line.strip()
        and not line.startswith("--")
        and not line.startswith(("torch ", "torch==", "torchvision", "torchaudio"))
    ]
    run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            python,
            *packages,
        ]
    )
    print(f"Seed-VC CPU 런타임 설치 완료: {runtime} ({settings.seedvc_commit})")


if __name__ == "__main__":
    main()
