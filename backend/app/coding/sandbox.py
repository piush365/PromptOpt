"""Run untrusted Python in a sandbox: a subprocess in a fresh temp dir, with a wall-clock timeout, CPU / memory /
file-size rlimits, and (with bubblewrap) no network and a read-only system.

    res = run_python({"main.py": code}, timeout=5)        # res.status: ok / error / timeout / memory / output_limit
    res.stdout, res.stderr, res.sandbox                   # sandbox: "bwrap" or "rlimits-only"

Isolation:
* bubblewrap (`bwrap`, used when installed): new user/pid/net/ipc/uts namespaces (`--unshare-all`), so there is no
  network at all; `/usr` read-only, a private `/tmp`, the temp dir mounted at `/work` and nothing else of the host
  (no home directory, no project, no `.env`); environment cleared; dies with its parent.
* rlimits (always): address space (memory), CPU seconds, file size, number of open files, no core dumps, and the
  number of processes (the user's current processes and threads + EXTRA_PROCESSES, since RLIMIT_NPROC counts all of
  the user's tasks), so a fork bomb stops quickly.
* timeout: the whole process group is killed when the wall-clock timeout passes.
* stdout/stderr go to files in the temp dir (capped by the file-size limit), so a print loop cannot fill memory.
Without bwrap (`rlimits-only`), code still runs in a temp dir with a cleared environment and the limits above, but it
CAN reach the network and read the user's files: `SANDBOX_REQUIRE_BWRAP=1` (the default) refuses to run then.
Code is never run any other way.
"""
import os
import resource
import shutil
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

PYTHON = "/usr/bin/python3"           # the system interpreter (stdlib only), not the project venv
TIMEOUT = 5.0                         # wall-clock seconds
MEMORY_MB = 512                       # address-space limit (Python itself needs ~30 MB)
FILE_MB = 4                           # largest file the code may write, stdout/stderr included
MAX_OUTPUT_CHARS = 20_000             # what is returned of stdout/stderr
EXTRA_PROCESSES = 32                  # processes the code may start (RLIMIT_NPROC counts all of the user's)
BWRAP = shutil.which("bwrap")
REQUIRE_BWRAP = os.getenv("SANDBOX_REQUIRE_BWRAP", "1") == "1"


@dataclass
class RunResult:
    status: str                 # ok | error | timeout | memory | output_limit
    returncode: int | None
    stdout: str
    stderr: str
    seconds: float
    sandbox: str                # bwrap | rlimits-only

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def sandbox_kind() -> str:
    return "bwrap" if BWRAP else "rlimits-only"


def _user_processes() -> int:
    """The user's tasks (processes and their threads): what RLIMIT_NPROC counts."""
    uid, n = os.getuid(), 0
    for d in Path("/proc").iterdir():
        if d.name.isdigit():
            try:
                if d.stat().st_uid == uid:
                    n += sum(1 for _ in (d / "task").iterdir())
            except OSError:
                pass
    return n


def _limits(timeout: float, memory_mb: int, file_mb: int):
    nproc = _user_processes() + EXTRA_PROCESSES

    def apply() -> None:
        mem = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        cpu = int(timeout) + 1
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
        size = file_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_FSIZE, (size, size))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_NPROC, (nproc, nproc))
    return apply


def _command(work: Path, entry: str) -> list[str]:
    py = [PYTHON, "-I", "-B", entry]                     # isolated mode: no user site, no PYTHON* variables
    if not BWRAP:
        return py
    return [BWRAP, "--unshare-all", "--die-with-parent", "--new-session",
            "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib",
            "--symlink", "usr/lib64", "/lib64", "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
            "--bind", str(work), "/work", "--chdir", "/work",
            "--clearenv", "--setenv", "PATH", "/usr/bin", "--setenv", "HOME", "/work",
            "--setenv", "LANG", "C.UTF-8", *py]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:MAX_OUTPUT_CHARS]
    except FileNotFoundError:
        return ""


def run_python(files: dict[str, str], entry: str = "main.py", stdin: str = "", timeout: float = TIMEOUT,
               memory_mb: int = MEMORY_MB, file_mb: int = FILE_MB) -> RunResult:
    """Write `files` into a fresh temp dir and run `python entry` there, sandboxed. Never raises for the code's own
    failures: they come back as the status."""
    if BWRAP is None and REQUIRE_BWRAP:
        raise RuntimeError("bubblewrap (bwrap) is not installed and SANDBOX_REQUIRE_BWRAP=1: refusing to run code "
                           "without network isolation. Install bubblewrap, or set SANDBOX_REQUIRE_BWRAP=0 to accept "
                           "rlimits-only isolation (see app/coding/sandbox.py).")
    with tempfile.TemporaryDirectory(prefix="promptopt-run-") as tmp:
        work = Path(tmp)
        for name, text in files.items():
            (work / name).write_text(text, encoding="utf-8")
        (work / "stdin.txt").write_text(stdin, encoding="utf-8")
        env = {"PATH": "/usr/bin", "HOME": str(work), "LANG": "C.UTF-8"}
        start = time.perf_counter()
        with open(work / "stdin.txt", "rb") as fin, open(work / ".stdout", "wb") as fout, \
                open(work / ".stderr", "wb") as ferr:
            proc = subprocess.Popen(_command(work, entry), cwd=work, env=env, stdin=fin, stdout=fout, stderr=ferr,
                                    preexec_fn=_limits(timeout, memory_mb, file_mb), start_new_session=True)
            try:
                rc = proc.wait(timeout=timeout)
                timed_out = False
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                rc, timed_out = proc.wait(), True
        seconds = time.perf_counter() - start
        out, err = _read(work / ".stdout"), _read(work / ".stderr")
    if timed_out or rc in (-signal.SIGXCPU, -signal.SIGKILL) and seconds >= timeout * 0.9:
        status = "timeout"
    elif "MemoryError" in err or rc in (-signal.SIGSEGV, -signal.SIGABRT) and "memory" in err.lower():
        status = "memory"
    elif rc == -signal.SIGXFSZ or "File too large" in err:
        status = "output_limit"
    else:
        status = "ok" if rc == 0 else "error"
    return RunResult(status, rc, out, err, round(seconds, 3), sandbox_kind())
