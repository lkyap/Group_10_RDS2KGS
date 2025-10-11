#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Graph pipeline + yFiles front-end launcher with GUI prompts.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Callable, Dict, Optional

import tkinter as tk
from tkinter import ttk, messagebox
import shutil

WORKSPACE_ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = WORKSPACE_ROOT / "yfiles-vue-integration-basic-master"
DIST_DIR = FRONTEND_DIR / "dist"
VENV_DIR = WORKSPACE_ROOT / ".venv"
CRED_FILE = WORKSPACE_ROOT / "cred.env"
DEFAULT_PREVIEW_PORT = 4173


# ---------------------------------------------------------------------------
# Helpers for filesystem / env management
# ---------------------------------------------------------------------------


def _python_in_venv() -> Path:
    script_dir = "Scripts" if os.name == "nt" else "bin"
    exe_name = "python.exe" if os.name == "nt" else "python"
    return VENV_DIR / script_dir / exe_name


def _pip_in_venv() -> Path:
    script_dir = "Scripts" if os.name == "nt" else "bin"
    exe_name = "pip.exe" if os.name == "nt" else "pip"
    return VENV_DIR / script_dir / exe_name


def read_existing_credentials() -> Dict[str, str]:
    if not CRED_FILE.exists():
        return {}
    result: Dict[str, str] = {}
    for line in CRED_FILE.read_text(encoding="utf-8").splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def write_cred_env(openai_key: str, neo4j_uri: str, neo4j_user: str, neo4j_password: str) -> None:
    content = "\n".join(
        [
            f"NEO4J_URI={neo4j_uri}",
            f"NEO4J_USER={neo4j_user}",
            f"NEO4J_PASSWORD={neo4j_password}",
            f"OPENAI_API_KEY={openai_key}",
        ]
    )
    CRED_FILE.write_text(content + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Command execution
# ---------------------------------------------------------------------------


def run_command(
    cmd: list[str],
    cwd: Path,
    env: Optional[Dict[str, str]] = None,
    log: Optional[Callable[[str], None]] = None,
) -> None:
    resolved_cmd = cmd.copy()
    if os.name == "nt" and resolved_cmd:
        candidate = shutil.which(resolved_cmd[0])
        if candidate:
            resolved_cmd[0] = candidate
        else:
            local_path = Path(resolved_cmd[0])
            if local_path.exists():
                resolved_cmd[0] = str(local_path)
            else:
                fallbacks = []
                program_files = os.environ.get("ProgramFiles")
                program_files_x86 = os.environ.get("ProgramFiles(x86)")
                if program_files:
                    fallbacks.append(Path(program_files) / "nodejs" / f"{resolved_cmd[0]}.cmd")
            if program_files_x86:
                fallbacks.append(Path(program_files_x86) / "nodejs" / f"{resolved_cmd[0]}.cmd")
            for fallback in fallbacks:
                if fallback.exists():
                    resolved_cmd[0] = str(fallback)
                    break
            else:
                raise FileNotFoundError(
                    f"Command '{resolved_cmd[0]}' was not found. Ensure it is installed and on PATH."
                )

    display = " ".join(cmd)
    if log:
        log(f"$ {display}")
    process = subprocess.Popen(
        resolved_cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )
    assert process.stdout is not None
    for line in process.stdout:
        if log:
            log(line.rstrip())
    process.stdout.close()
    return_code = process.wait()
    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, cmd)


def ensure_virtualenv(log: Callable[[str], None]) -> Path:
    if not VENV_DIR.exists():
        log("Creating Python virtual environment...")
        run_command([sys.executable, "-m", "venv", str(VENV_DIR)], cwd=WORKSPACE_ROOT, log=log)
    else:
        log("Virtual environment already present.")

    python_path = _python_in_venv()
    pip_path = _pip_in_venv()

    log("Installing Python dependencies (requirements.txt)...")
    run_command([str(pip_path), "install", "-r", "requirements.txt"], cwd=WORKSPACE_ROOT, log=log)
    return python_path


def run_pipeline(python_exe: Path, env: Dict[str, str], log: Callable[[str], None]) -> None:
    log("Running knowledge-graph pipeline (main.py)...")
    run_command([str(python_exe), "main.py"], cwd=WORKSPACE_ROOT, env=env, log=log)


def ensure_node_dependencies(log: Callable[[str], None]) -> None:
    node_modules = FRONTEND_DIR / "node_modules"
    if node_modules.exists():
        log("Node dependencies already installed.")
        return
    log("Installing Node dependencies (npm install)...")
    run_command(["npm", "install"], cwd=FRONTEND_DIR, log=log)


def build_frontend(log: Callable[[str], None]) -> None:
    log("Building yFiles front-end (npm run build)...")
    run_command(["npm", "run", "build"], cwd=FRONTEND_DIR, log=log)


def start_preview_server(python_exe: Path, log: Callable[[str], None], port: int = DEFAULT_PREVIEW_PORT):
    if not DIST_DIR.exists():
        raise RuntimeError("Front-end build output (dist/) not found.")
    log(f"Starting preview server on http://127.0.0.1:{port}/ ...")
    server_cmd = [
        str(python_exe),
        "-m",
        "http.server",
        str(port),
        "--bind",
        "127.0.0.1",
    ]
    return subprocess.Popen(
        server_cmd,
        cwd=str(DIST_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# ---------------------------------------------------------------------------
# Tkinter GUI
# ---------------------------------------------------------------------------


class LauncherApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Knowledge Graph End-to-End Launcher")
        self.root.geometry("760x600")

        self.openai_var = tk.StringVar()
        self.neo4j_uri_var = tk.StringVar(value="bolt://localhost:7687")
        self.neo4j_user_var = tk.StringVar(value="neo4j")
        self.neo4j_password_var = tk.StringVar()

        self._running = False
        self.server_proc: Optional[subprocess.Popen] = None
        self.python_exe: Optional[Path] = None

        self._build_layout()
        self._load_defaults()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # UI ------------------------------------------------------------------

    def _build_layout(self) -> None:
        padding = {"padx": 12, "pady": 6}

        frame = ttk.LabelFrame(self.root, text="Credentials")
        frame.pack(fill="x", **padding)

        ttk.Label(frame, text="OpenAI API Key:").grid(row=0, column=0, sticky="e", padx=6, pady=4)
        ttk.Entry(frame, textvariable=self.openai_var, width=50, show="•").grid(
            row=0, column=1, sticky="we", padx=6, pady=4
        )

        ttk.Label(frame, text="Neo4j URI:").grid(row=1, column=0, sticky="e", padx=6, pady=4)
        ttk.Entry(frame, textvariable=self.neo4j_uri_var, width=40).grid(
            row=1, column=1, sticky="we", padx=6, pady=4
        )

        ttk.Label(frame, text="Neo4j User:").grid(row=2, column=0, sticky="e", padx=6, pady=4)
        ttk.Entry(frame, textvariable=self.neo4j_user_var, width=40).grid(
            row=2, column=1, sticky="we", padx=6, pady=4
        )

        ttk.Label(frame, text="Neo4j Password:").grid(row=3, column=0, sticky="e", padx=6, pady=4)
        ttk.Entry(frame, textvariable=self.neo4j_password_var, width=40, show="•").grid(
            row=3, column=1, sticky="we", padx=6, pady=4
        )

        frame.columnconfigure(1, weight=1)

        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill="x", **padding)

        self.run_button = ttk.Button(button_frame, text="Run End-to-End", command=self._run_async)
        self.run_button.pack(side="left")

        self.stop_button = ttk.Button(button_frame, text="Stop UI Server", command=self._stop_server, state="disabled")
        self.stop_button.pack(side="left", padx=(10, 0))

        ttk.Button(button_frame, text="Open Output Folder", command=self._open_output_folder).pack(
            side="left", padx=(10, 0)
        )
        ttk.Button(button_frame, text="Quit", command=self._on_close).pack(side="right")

        log_frame = ttk.LabelFrame(self.root, text="Activity Log")
        log_frame.pack(fill="both", expand=True, **padding)

        self.log_text = tk.Text(log_frame, wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=6, pady=6)

        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(self.root, textvariable=self.status_var, anchor="w").pack(fill="x", padx=12, pady=(0, 12))

    def _load_defaults(self) -> None:
        creds = read_existing_credentials()
        if "OPENAI_API_KEY" in creds:
            self.openai_var.set(creds["OPENAI_API_KEY"])
        if "NEO4J_URI" in creds:
            self.neo4j_uri_var.set(creds["NEO4J_URI"])
        if "NEO4J_USER" in creds:
            self.neo4j_user_var.set(creds["NEO4J_USER"])
        if "NEO4J_PASSWORD" in creds:
            self.neo4j_password_var.set(creds["NEO4J_PASSWORD"])

    # Logging --------------------------------------------------------------

    def log(self, message: str) -> None:
        def append():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

        self.root.after(0, append)

    def set_status(self, text: str) -> None:
        self.root.after(0, lambda: self.status_var.set(text))

    # Actions --------------------------------------------------------------

    def _run_async(self) -> None:
        if self._running:
            return
        openai_key = self.openai_var.get().strip()
        if not openai_key:
            messagebox.showerror("Missing value", "Please enter an OpenAI API key.")
            return
        neo4j_password = self.neo4j_password_var.get().strip()
        if not neo4j_password:
            messagebox.showerror("Missing value", "Please enter the Neo4j password.")
            return

        self._running = True
        self.run_button.configure(state="disabled")
        self.set_status("Running pipeline...")
        self.log("=== Starting end-to-end run ===")

        thread = threading.Thread(target=self._run_pipeline, daemon=True)
        thread.start()

    def _run_pipeline(self) -> None:
        try:
            openai_key = self.openai_var.get().strip()
            neo4j_uri = self.neo4j_uri_var.get().strip()
            neo4j_user = self.neo4j_user_var.get().strip()
            neo4j_password = self.neo4j_password_var.get().strip()

            self.log("Writing cred.env ...")
            write_cred_env(openai_key, neo4j_uri, neo4j_user, neo4j_password)

            python_exe = ensure_virtualenv(self.log)
            self.python_exe = python_exe

            env = os.environ.copy()
            env.update(
                {
                    "OPENAI_API_KEY": openai_key,
                    "NEO4J_URI": neo4j_uri,
                    "NEO4J_USER": neo4j_user,
                    "NEO4J_PASSWORD": neo4j_password,
                }
            )

            run_pipeline(python_exe, env, self.log)
            ensure_node_dependencies(self.log)
            build_frontend(self.log)

            server_proc = start_preview_server(python_exe, self.log)
            self.server_proc = server_proc
            url = f"http://127.0.0.1:{DEFAULT_PREVIEW_PORT}/"
            self.log(f"Opening {url} ...")
            webbrowser.open(url)
            self.set_status("UI server running. Close this window or press 'Stop UI Server' when finished.")
            self.root.after(0, lambda: self.stop_button.configure(state="normal"))
            self.log("=== End-to-end run complete ===")
        except subprocess.CalledProcessError as exc:
            msg = f"Command failed (exit code {exc.returncode}): {' '.join(exc.cmd)}"
            self.log(f"ERROR: {msg}")
            self._show_error(msg)
            self.set_status("Failed")
        except Exception as exc:  # pylint: disable=broad-except
            self.log(f"ERROR: {exc}")
            self._show_error(str(exc))
            self.set_status("Failed")
        finally:
            self._running = False
            self.root.after(0, lambda: self.run_button.configure(state="normal"))

    def _stop_server(self) -> None:
        if not self.server_proc:
            return
        self.log("Stopping preview server...")
        self.server_proc.terminate()
        try:
            self.server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.server_proc.kill()
        self.server_proc = None
        self.stop_button.configure(state="disabled")
        self.set_status("Server stopped.")

    def _open_output_folder(self) -> None:
        path = (WORKSPACE_ROOT / "extracted_output").resolve()
        path.mkdir(exist_ok=True)
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _show_error(self, message: str) -> None:
        self.root.after(0, lambda: messagebox.showerror("Execution failed", message))

    def _on_close(self) -> None:
        if self._running:
            if not messagebox.askyesno("Confirm exit", "Pipeline is running. Stop and exit anyway?"):
                return
        if self.server_proc:
            self._stop_server()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    app = LauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
