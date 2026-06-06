from pathlib import Path
import sys


def ensure_xcpc_core_on_path() -> None:
    try:
        import xcpc  # noqa: F401
        return
    except ModuleNotFoundError:
        pass

    core_root = Path(__file__).resolve().parents[2] / "xcpc-core"
    if core_root.exists():
        sys.path.insert(0, str(core_root))
