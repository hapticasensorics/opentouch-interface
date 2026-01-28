from __future__ import annotations

import os
import shlex
import subprocess
import sys
import threading
import time
import logging
import shutil
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import viewer_config
from .cache import DEFAULT_CACHE_DIR, get_or_create_rrd


app = FastAPI(title="OpenTouch Rerun Session Service")
logger = logging.getLogger(__name__)


@dataclass
class SessionRecord:
    session_id: str
    process: subprocess.Popen
    viewer_command: List[str]
    viewer_args: List[str]
    created_at: float
    loaded_rrd: Optional[Path] = None
    last_loaded_at: Optional[float] = None


_sessions: Dict[str, SessionRecord] = {}
_sessions_lock = threading.Lock()


class CreateSessionRequest(BaseModel):
    rrd_path: Optional[str] = None
    touch_path: Optional[str] = None
    viewer_args: List[str] = Field(default_factory=list)
    use_cache: bool = True


class LoadSessionRequest(BaseModel):
    rrd_path: Optional[str] = None
    touch_path: Optional[str] = None
    use_cache: bool = True
    replace_viewer: bool = True


class SessionInfo(BaseModel):
    session_id: str
    pid: Optional[int]
    status: str
    created_at: float
    loaded_rrd: Optional[str]
    last_loaded_at: Optional[float]


class PlaybackState(BaseModel):
    state: str = "unknown"
    time_s: Optional[float] = None


class SessionState(BaseModel):
    session: SessionInfo
    playback: PlaybackState


class DeleteSessionResponse(BaseModel):
    session_id: str
    status: str


def _parse_viewer_command() -> List[str]:
    raw = os.getenv("OPENTOUCH_RERUN_VIEWER_CMD")
    if raw:
        command = shlex.split(raw)
        if command:
            return command

    resolved = shutil.which("rerun")
    if resolved:
        return [resolved]

    venv_candidate = Path(sys.executable).with_name("rerun")
    if venv_candidate.exists():
        return [str(venv_candidate)]

    return [sys.executable, "-m", "rerun"]


def _default_viewer_args() -> List[str]:
    raw = os.getenv("OPENTOUCH_RERUN_VIEWER_ARGS", "")
    return shlex.split(raw) if raw else []


def _viewer_arg_present(args: List[str], flag: str) -> bool:
    if flag in args:
        return True
    prefix = f"{flag}="
    return any(arg.startswith(prefix) for arg in args)


def _allocate_grpc_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
        handle.bind(("127.0.0.1", 0))
        return int(handle.getsockname()[1])


def _normalize_viewer_args(viewer_args: List[str]) -> List[str]:
    args = list(viewer_args)
    if _viewer_arg_present(args, "--port") or _viewer_arg_present(args, "--connect"):
        return args
    args.extend(["--port", str(_allocate_grpc_port())])
    return args


def _spawn_viewer(
    rrd_path: Optional[Path],
    viewer_args: List[str],
    extra_inputs: Optional[List[Path]] = None,
) -> subprocess.Popen:
    command = _parse_viewer_command() + viewer_args
    inputs: List[Path] = []
    if extra_inputs:
        inputs.extend([path for path in extra_inputs if path is not None])
    if rrd_path is not None:
        inputs.append(rrd_path)
    command.extend(str(path) for path in inputs)

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        time.sleep(0.2)
        if process.poll() is not None:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Rerun viewer exited before the session could start. "
                    f"Command: {shlex.join(command)}"
                ),
            )
        return process
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Rerun viewer command not found: {command[0]}",
        ) from exc


def _terminate_process(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _session_status(process: subprocess.Popen) -> str:
    return "running" if process.poll() is None else "exited"


def _session_info(record: SessionRecord) -> SessionInfo:
    return SessionInfo(
        session_id=record.session_id,
        pid=record.process.pid,
        status=_session_status(record.process),
        created_at=record.created_at,
        loaded_rrd=str(record.loaded_rrd) if record.loaded_rrd else None,
        last_loaded_at=record.last_loaded_at,
    )


def _convert_touch_to_rrd(touch_path: Path, rrd_path: Path) -> None:
    """Convert a .touch file to .rrd using the rerun CLI implementation."""
    try:
        from opentouch_interface.rerun import cli as rerun_cli  # type: ignore

        convert = getattr(rerun_cli, "convert_touch_to_rrd", None)
        if callable(convert):
            convert(str(touch_path), str(rrd_path))
            return

        convert = getattr(rerun_cli, "touch_to_rrd", None)
        if callable(convert):
            convert(str(touch_path), str(rrd_path))
            return

        main = getattr(rerun_cli, "main", None)
        if callable(main):
            try:
                main([str(touch_path), str(rrd_path)])
                return
            except TypeError:
                pass
    except Exception:
        pass

    subprocess.run(
        [
            sys.executable,
            "-m",
            "opentouch_interface.rerun.cli",
            str(touch_path),
            str(rrd_path),
        ],
        check=True,
    )


def _resolve_rrd_path(
    rrd_path: Optional[str],
    touch_path: Optional[str],
    use_cache: bool,
) -> Optional[Path]:
    if rrd_path:
        resolved = Path(rrd_path).expanduser().resolve()
        if not resolved.exists():
            raise HTTPException(status_code=404, detail=f"RRD not found: {resolved}")
        return resolved

    if touch_path:
        resolved_touch = Path(touch_path).expanduser().resolve()
        if not resolved_touch.exists():
            raise HTTPException(
                status_code=404, detail=f"Touch file not found: {resolved_touch}"
            )

        if use_cache:
            return get_or_create_rrd(resolved_touch, _convert_touch_to_rrd)

        output_path = resolved_touch.with_suffix(".rrd")
        _convert_touch_to_rrd(resolved_touch, output_path)
        return output_path

    return None


def _viewer_app_id() -> str:
    return os.getenv("OPENTOUCH_RERUN_APP_ID", viewer_config.DEFAULT_APP_ID)


def _resolve_blueprint_path() -> Optional[Path]:
    disable = os.getenv("OPENTOUCH_RERUN_DISABLE_BLUEPRINT", "").lower()
    if disable in {"1", "true", "yes", "on"}:
        return None
    try:
        return viewer_config.save_blueprint(DEFAULT_CACHE_DIR, _viewer_app_id())
    except Exception as exc:
        logger.warning("Failed to build Rerun viewer blueprint: %s", exc)
        return None


@app.post("/sessions", response_model=SessionInfo)
def create_session(request: CreateSessionRequest) -> SessionInfo:
    rrd_path = _resolve_rrd_path(request.rrd_path, request.touch_path, request.use_cache)
    viewer_args = _normalize_viewer_args(_default_viewer_args() + request.viewer_args)
    blueprint_path = _resolve_blueprint_path()
    process = _spawn_viewer(rrd_path, viewer_args, [blueprint_path] if blueprint_path else None)

    session_id = uuid4().hex
    record = SessionRecord(
        session_id=session_id,
        process=process,
        viewer_command=_parse_viewer_command(),
        viewer_args=viewer_args,
        created_at=time.time(),
        loaded_rrd=rrd_path,
        last_loaded_at=time.time() if rrd_path else None,
    )

    with _sessions_lock:
        _sessions[session_id] = record

    return _session_info(record)


@app.post("/sessions/{session_id}/load", response_model=SessionInfo)
def load_session(session_id: str, request: LoadSessionRequest) -> SessionInfo:
    with _sessions_lock:
        record = _sessions.get(session_id)

    if record is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    rrd_path = _resolve_rrd_path(request.rrd_path, request.touch_path, request.use_cache)
    if rrd_path is None:
        raise HTTPException(status_code=400, detail="Provide rrd_path or touch_path")

    if record.process.poll() is None:
        if not request.replace_viewer:
            raise HTTPException(
                status_code=409,
                detail="Session already running; set replace_viewer to true",
            )
        _terminate_process(record.process)

    blueprint_path = _resolve_blueprint_path()
    viewer_args = _normalize_viewer_args(record.viewer_args)
    process = _spawn_viewer(rrd_path, viewer_args, [blueprint_path] if blueprint_path else None)
    with _sessions_lock:
        if session_id not in _sessions:
            _terminate_process(process)
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        record.process = process
        record.viewer_args = viewer_args
        record.loaded_rrd = rrd_path
        record.last_loaded_at = time.time()

    return _session_info(record)


@app.get("/sessions/{session_id}/state", response_model=SessionState)
def get_session_state(session_id: str) -> SessionState:
    with _sessions_lock:
        record = _sessions.get(session_id)

    if record is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    session_info = _session_info(record)
    playback = PlaybackState()
    return SessionState(session=session_info, playback=playback)


@app.delete("/sessions/{session_id}", response_model=DeleteSessionResponse)
def delete_session(session_id: str) -> DeleteSessionResponse:
    with _sessions_lock:
        record = _sessions.pop(session_id, None)

    if record is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    _terminate_process(record.process)

    return DeleteSessionResponse(session_id=session_id, status="closed")


@app.on_event("shutdown")
def _shutdown_sessions() -> None:
    with _sessions_lock:
        records = list(_sessions.values())
        _sessions.clear()

    for record in records:
        _terminate_process(record.process)
