from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: seedvc_cpu_bridge.py <seed-vc-inference.py> [args]")
    inference_script = Path(sys.argv[1]).resolve(strict=True)
    if inference_script.name != "inference.py":
        raise SystemExit("Seed-VC inference.py만 실행할 수 있습니다")

    import torch

    # 공식 스크립트가 CUDA·MPS를 선택하지 않도록 별도 프로세스 안에서 CPU를 강제한다.
    torch.cuda.is_available = lambda: False
    if hasattr(torch.backends, "mps"):
        torch.backends.mps.is_available = lambda: False
    sys.path.insert(0, str(inference_script.parent))
    sys.argv = [str(inference_script), *sys.argv[2:]]
    runpy.run_path(str(inference_script), run_name="__main__")


if __name__ == "__main__":
    main()
