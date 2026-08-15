import os
import sys
from pathlib import Path


def maybe_set_local_trace() -> None:
    """Enable the local debugger only when explicitly requested."""
    if os.environ.get("ELMES_DEBUGGER") != "1":
        return

    klee_code_dir = Path.home() / "klee_code"
    if str(klee_code_dir) not in sys.path:
        sys.path.append(str(klee_code_dir))

    try:
        import python_code.borrowed_klee_python_code.pdb as local_pdb
    except ModuleNotFoundError:
        return

    local_pdb.set_trace()
