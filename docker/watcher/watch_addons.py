#!/usr/bin/env python3

import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver


ADDONS_DIR = Path(os.getenv("ADDONS_DIR", "/mnt/extra-addons")).resolve()
DB_NAME = os.getenv("ODOO_DB_NAME", "odoo16")
DEBOUNCE_SECONDS = float(os.getenv("WATCHER_DEBOUNCE_SECONDS", "3"))
IGNORED_PARTS = {"__pycache__", ".git", ".idea", ".vscode"}
IGNORED_SUFFIXES = {".pyc", ".pyo", ".swp", ".tmp"}
TRACKED_SUFFIXES = {
    ".css",
    ".csv",
    ".js",
    ".json",
    ".po",
    ".py",
    ".rst",
    ".scss",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
IMPORTANT_FILENAMES = {"__init__.py", "__manifest__.py"}

pending_updates = {}
pending_lock = threading.Lock()
update_lock = threading.Lock()


def run_psql(query: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PGPASSWORD"] = env.get("ODOO_DB_PASSWORD", "")
    return subprocess.run(
        [
            "psql",
            "-h",
            env.get("ODOO_DB_HOST", "db"),
            "-p",
            env.get("ODOO_DB_PORT", "5432"),
            "-U",
            env.get("ODOO_DB_USER", "odoo"),
            "-d",
            DB_NAME,
            "-tAc",
            query,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def is_database_ready() -> bool:
    result = run_psql("SELECT 1 FROM ir_module_module LIMIT 1;")
    return result.returncode == 0


def wait_for_database_ready() -> None:
    while not is_database_ready():
        print("[watcher] waiting for Odoo database initialization", flush=True)
        time.sleep(5)
    print("[watcher] Odoo database is ready for module updates", flush=True)


def find_module_name(changed_path: Path) -> Optional[str]:
    try:
        relative = changed_path.resolve().relative_to(ADDONS_DIR)
    except ValueError:
        return None

    current = ADDONS_DIR.joinpath(*relative.parts[:1])
    if not current.exists():
        return None

    if (current / "__manifest__.py").exists():
        return current.name

    for parent in changed_path.resolve().parents:
        if parent == ADDONS_DIR:
            break
        if (parent / "__manifest__.py").exists():
            return parent.name
    return None


def should_track(path: Path) -> bool:
    if any(part in IGNORED_PARTS for part in path.parts):
        return False
    if path.suffix in IGNORED_SUFFIXES:
        return False
    return path.suffix in TRACKED_SUFFIXES or path.name in IMPORTANT_FILENAMES


def queue_update(module_name: str) -> None:
    with pending_lock:
        pending_updates[module_name] = time.time()
    print(f"[watcher] change detected in module '{module_name}', queued update", flush=True)


def run_update(module_name: str) -> None:
    command = [
        "odoo",
        "-c",
        "/etc/odoo/odoo.conf",
        "-d",
        DB_NAME,
        "-u",
        module_name,
        "--stop-after-init",
    ]
    with update_lock:
        print(f"[watcher] updating module '{module_name}'", flush=True)
        result = subprocess.run(command, check=False)
        if result.returncode == 0:
            print(f"[watcher] module '{module_name}' updated successfully", flush=True)
        else:
            print(
                f"[watcher] module '{module_name}' update failed with code {result.returncode}",
                flush=True,
            )


def update_worker() -> None:
    while True:
        time.sleep(1)
        ready_modules = []
        now = time.time()
        with pending_lock:
            for module_name, last_change in list(pending_updates.items()):
                if now - last_change >= DEBOUNCE_SECONDS:
                    ready_modules.append(module_name)
                    del pending_updates[module_name]
        for module_name in ready_modules:
            run_update(module_name)


class AddonChangeHandler(FileSystemEventHandler):
    def on_any_event(self, event) -> None:
        if event.is_directory:
            return
        changed_path = Path(event.src_path)
        if not should_track(changed_path):
            return
        module_name = find_module_name(changed_path)
        if module_name:
            queue_update(module_name)


def main() -> None:
    print(f"[watcher] watching addons in {ADDONS_DIR}", flush=True)
    print(f"[watcher] target database: {DB_NAME}", flush=True)
    wait_for_database_ready()
    worker_thread = threading.Thread(target=update_worker, daemon=True)
    worker_thread.start()

    observer = PollingObserver(timeout=1)
    observer.schedule(AddonChangeHandler(), str(ADDONS_DIR), recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
