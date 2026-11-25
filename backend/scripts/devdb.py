"""Run a throwaway PostgreSQL cluster for local development, without Docker.

The cluster lives in backend/.devdb, listens on 127.0.0.1:5434, and trusts local connections,
so it never touches a system PostgreSQL service or its password.

    python scripts/devdb.py start                    # init on first run, then start; creates both databases
    python scripts/devdb.py stop
    python scripts/devdb.py status
    python scripts/devdb.py make-private             # copy the installed PostgreSQL into backend/.pgsql
    python scripts/devdb.py install-pgvector <dir>   # add a built pgvector to that private copy

Phase 2 needs the pgvector extension. Installing it into a system PostgreSQL usually needs admin
rights, so this script can run from a private copy of the PostgreSQL binaries instead
(backend/.pgsql, gitignored). When the private copy exists it is always preferred.

Building pgvector on Windows (needs Visual Studio Build Tools with the C++ workload):

    git clone --branch v0.8.7 https://github.com/pgvector/pgvector.git
    "C:\\Program Files (x86)\\Microsoft Visual Studio\\<ver>\\BuildTools\\VC\\Auxiliary\\Build\\vcvars64.bat"
    set "PGROOT=C:\\Program Files\\PostgreSQL\\17"
    nmake /F Makefile.win
    python scripts/devdb.py install-pgvector path\\to\\pgvector

On Linux and macOS, install your distribution's pgvector package instead (or use Docker).
Set PG_BIN if the system binaries are not on PATH (e.g. "C:/Program Files/PostgreSQL/17/bin").
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / ".devdb"
LOG = ROOT / ".devdb.log"
PRIVATE = ROOT / ".pgsql"
PORT = os.environ.get("DEVDB_PORT", "5434")
DATABASES = ("ai_qa_studio", "ai_qa_studio_test")


def _system_bin(name: str) -> Path | None:
    candidates: list[Path] = []
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
                return p
    return None


def _bin(name: str) -> str:
    for suffix in ("", ".exe"):
        private = PRIVATE / "bin" / f"{name}{suffix}"
        if private.exists():
            return str(private)
    found = _system_bin(name)
    if found is None:
        sys.exit(f"Cannot find {name}. Install PostgreSQL 16+ or set PG_BIN.")
    return str(found)


def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, text=True, capture_output=True)  # noqa: S603


def _is_running() -> bool:
    return _run(_bin("pg_ctl"), "-D", str(DATA), "status", check=False).returncode == 0


def start() -> None:
    if not (DATA / "PG_VERSION").exists():
        print(f"initialising cluster in {DATA}")
        _run(_bin("initdb"), "-D", str(DATA), "-U", "postgres", "-A", "trust", "-E", "UTF8", "--no-locale")
    if not _is_running():
        # The server must not inherit this process's stdio, or callers reading our output hang.
        subprocess.run(  # noqa: S603
            [_bin("pg_ctl"), "-D", str(DATA), "-l", str(LOG), "-w",
             "-o", f"-p {PORT} -c listen_addresses=127.0.0.1", "start"],
            check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )  # fmt: skip
    psql = _bin("psql")
    base = (psql, "-h", "127.0.0.1", "-p", PORT, "-U", "postgres")
    for db in DATABASES:
        exists = _run(*base, "-tAc", f"SELECT 1 FROM pg_database WHERE datname = '{db}'")
        if exists.stdout.strip() != "1":
            _run(*base, "-c", f'CREATE DATABASE "{db}"')
            print(f"created database {db}")
    has_vector = _run(*base, "-d", DATABASES[0], "-tAc",
                      "SELECT 1 FROM pg_available_extensions WHERE name = 'vector'").stdout.strip()  # fmt: skip
    print(f"dev database ready: postgresql+psycopg://postgres@127.0.0.1:{PORT}/ai_qa_studio")
    print(f"binaries: {Path(psql).parent}")
    if has_vector != "1":
        print(
            "WARNING: pgvector is not available; Phase 2 migrations will fail. See the notes at the top of this file."
        )


def stop() -> None:
    subprocess.run([_bin("pg_ctl"), "-D", str(DATA), "stop", "-m", "fast"], check=False)  # noqa: S603


def status() -> None:
    subprocess.run([_bin("pg_ctl"), "-D", str(DATA), "status"], check=False)  # noqa: S603


def make_private() -> None:
    """Copy the system PostgreSQL bin/lib/share into backend/.pgsql (no admin rights needed)."""
    pg_ctl = _system_bin("pg_ctl")
    if pg_ctl is None:
        sys.exit("Cannot find an installed PostgreSQL to copy. Set PG_BIN.")
    source = pg_ctl.parent.parent
    if PRIVATE.exists():
        sys.exit(f"{PRIVATE} already exists; delete it first to recreate it.")
    was_running = (DATA / "PG_VERSION").exists() and _is_running()
    if was_running:
        stop()
    for part in ("bin", "lib", "share"):
        print(f"copying {source / part}")
        shutil.copytree(source / part, PRIVATE / part)
    print(f"private PostgreSQL ready in {PRIVATE}")
    if was_running:
        start()


def install_pgvector(build_dir: str) -> None:
    """Copy a built pgvector (vector.dll or vector.so, vector.control, sql/vector--*.sql) into backend/.pgsql."""
    src = Path(build_dir)
    if not PRIVATE.exists():
        sys.exit("Run `python scripts/devdb.py make-private` first.")
    library = next((src / n for n in ("vector.dll", "vector.so", "vector.dylib") if (src / n).exists()), None)
    if library is None or not (src / "vector.control").exists():
        sys.exit(f"{src} does not look like a built pgvector directory (need vector.dll/.so and vector.control).")
    extension_dir = PRIVATE / "share" / "extension"
    shutil.copy2(library, PRIVATE / "lib" / library.name)
    shutil.copy2(src / "vector.control", extension_dir / "vector.control")
    scripts = list((src / "sql").glob("vector--*.sql"))
    for script in scripts:
        shutil.copy2(script, extension_dir / script.name)
    print(f"installed pgvector ({library.name}, {len(scripts)} SQL scripts) into {PRIVATE}")
    if (DATA / "PG_VERSION").exists() and _is_running():
        print("restart the dev database to load it: python scripts/devdb.py stop && python scripts/devdb.py start")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "start"
    if command == "install-pgvector":
        if len(sys.argv) < 3:
            sys.exit("usage: devdb.py install-pgvector <pgvector build dir>")
        install_pgvector(sys.argv[2])
    else:
        {"start": start, "stop": stop, "status": status, "make-private": make_private}.get(command, start)()
