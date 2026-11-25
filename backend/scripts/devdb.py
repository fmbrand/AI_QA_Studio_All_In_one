"""Run a throwaway PostgreSQL cluster for local development, without Docker.

Uses the PostgreSQL server binaries already installed on the machine (initdb, pg_ctl).
The cluster lives in backend/.devdb, listens on 127.0.0.1:5434, and trusts local connections,
so it never touches a system PostgreSQL service or its password.

    python scripts/devdb.py start    # init on first run, then start; creates both databases
    python scripts/devdb.py stop
    python scripts/devdb.py status

Set PG_BIN if the binaries are not on PATH (e.g. "C:/Program Files/PostgreSQL/17/bin").
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / ".devdb"
LOG = ROOT / ".devdb.log"
PORT = os.environ.get("DEVDB_PORT", "5434")
DATABASES = ("ai_qa_studio", "ai_qa_studio_test")


def _bin(name: str) -> str:
    candidates = []
    if os.environ.get("PG_BIN"):
        candidates.append(Path(os.environ["PG_BIN"]) / name)
    found = shutil.which(name)
    if found:
        candidates.append(Path(found))
    for base in (Path("C:/Program Files/PostgreSQL"), Path("/usr/lib/postgresql")):
        if base.exists():
            for version in sorted(base.iterdir(), reverse=True):
                candidates.append(version / "bin" / name)
    for c in candidates:
        for suffix in ("", ".exe"):
            p = Path(str(c) + suffix)
            if p.exists():
                return str(p)
    sys.exit(f"Cannot find {name}. Install PostgreSQL 16+ or set PG_BIN.")


def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, text=True, capture_output=True)  # noqa: S603


def start() -> None:
    if not (DATA / "PG_VERSION").exists():
        print(f"initialising cluster in {DATA}")
        _run(_bin("initdb"), "-D", str(DATA), "-U", "postgres", "-A", "trust", "-E", "UTF8", "--no-locale")
    if _run(_bin("pg_ctl"), "-D", str(DATA), "status", check=False).returncode != 0:
        # The server must not inherit this process's stdio, or callers reading our output hang.
        subprocess.run(  # noqa: S603
            [
                _bin("pg_ctl"),
                "-D",
                str(DATA),
                "-l",
                str(LOG),
                "-w",
                "-o",
                f"-p {PORT} -c listen_addresses=127.0.0.1",
                "start",
            ],
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    psql = _bin("psql")
    for db in DATABASES:
        exists = _run(
            psql,
            "-h",
            "127.0.0.1",
            "-p",
            PORT,
            "-U",
            "postgres",
            "-tAc",
            f"SELECT 1 FROM pg_database WHERE datname = '{db}'",
        )
        if exists.stdout.strip() != "1":
            _run(psql, "-h", "127.0.0.1", "-p", PORT, "-U", "postgres", "-c", f'CREATE DATABASE "{db}"')
            print(f"created database {db}")
    print(f"dev database ready: postgresql+psycopg://postgres@127.0.0.1:{PORT}/ai_qa_studio")


def stop() -> None:
    subprocess.run([_bin("pg_ctl"), "-D", str(DATA), "stop", "-m", "fast"], check=False)  # noqa: S603


def status() -> None:
    subprocess.run([_bin("pg_ctl"), "-D", str(DATA), "status"], check=False)  # noqa: S603


if __name__ == "__main__":
    {"start": start, "stop": stop, "status": status}.get(sys.argv[1] if len(sys.argv) > 1 else "start", start)()
