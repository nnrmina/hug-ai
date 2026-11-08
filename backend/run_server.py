"""Clean single-process launcher for YAXIN AI FastAPI server on Windows."""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def free_port_8000(port: int = 8000) -> None:
    """Terminate any stale previous uvicorn/python process holding the target port on Windows."""
    my_pid = str(os.getpid())
    try:
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "TCP"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        pids_to_kill = set()
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[1].endswith(f":{port}") and parts[3] == "LISTENING":
                pid = parts[4]
                if pid != "0" and pid != my_pid:
                    pids_to_kill.add(pid)
        for pid in pids_to_kill:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", pid],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
    except Exception:
        pass


if __name__ == "__main__":
    free_port_8000(8000)
    import uvicorn
    from app.main import app

    uvicorn.run(app, host="0.0.0.0", port=8000)

