"""
Read-only OBS runtime context bridge.

This module reads OBS WebSocket v5 metadata only. It never starts/stops
recording, changes scenes, mutes sources, stores frames, or stores audio.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import ssl
import struct
import uuid
from datetime import datetime, timezone
from typing import Any


DEFAULT_HOST = os.environ.get("OBS_WEBSOCKET_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("OBS_WEBSOCKET_PORT", "4455"))
DEFAULT_PASSWORD = os.environ.get("OBS_WEBSOCKET_PASSWORD", "")
DEFAULT_TIMEOUT = float(os.environ.get("OBS_WEBSOCKET_TIMEOUT", "1.5"))


class OBSContextError(RuntimeError):
    pass


class _OBSWebSocket:
    def __init__(self, host: str, port: int, password: str, timeout: float):
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout
        self.sock: socket.socket | ssl.SSLSocket | None = None

    def __enter__(self) -> "_OBSWebSocket":
        raw = socket.create_connection((self.host, self.port), timeout=self.timeout)
        raw.settimeout(self.timeout)
        self.sock = raw
        self._handshake()
        self._identify()
        return self

    def __exit__(self, *_exc: object) -> None:
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass

    def _handshake(self) -> None:
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET / HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self._send_raw(request.encode("ascii"))
        response = self._recv_until(b"\r\n\r\n")
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise OBSContextError("OBS WebSocket handshake failed")

    def _identify(self) -> None:
        hello = self.recv_json()
        if hello.get("op") != 0:
            raise OBSContextError("OBS WebSocket did not send Hello")
        data = hello.get("d") or {}
        auth_payload = data.get("authentication")
        identify_data: dict[str, Any] = {"rpcVersion": min(int(data.get("rpcVersion", 1)), 1)}
        if auth_payload:
            if not self.password:
                raise OBSContextError("OBS WebSocket requires a password; set OBS_WEBSOCKET_PASSWORD")
            identify_data["authentication"] = _obs_auth(
                self.password,
                str(auth_payload.get("salt", "")),
                str(auth_payload.get("challenge", "")),
            )
        self.send_json({"op": 1, "d": identify_data})
        identified = self.recv_json()
        if identified.get("op") != 2:
            raise OBSContextError("OBS WebSocket identification failed")

    def request(self, request_type: str, request_data: dict | None = None) -> dict:
        request_id = str(uuid.uuid4())
        self.send_json({
            "op": 6,
            "d": {
                "requestType": request_type,
                "requestId": request_id,
                "requestData": request_data or {},
            },
        })
        while True:
            message = self.recv_json()
            if message.get("op") != 7:
                continue
            data = message.get("d") or {}
            if data.get("requestId") != request_id:
                continue
            status = data.get("requestStatus") or {}
            if not status.get("result"):
                raise OBSContextError(f"{request_type}: {status.get('comment') or status.get('code') or 'request failed'}")
            return data.get("responseData") or {}

    def send_json(self, payload: dict) -> None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        header = bytearray([0x81])
        length = len(data)
        if length < 126:
            header.append(0x80 | length)
        elif length <= 0xFFFF:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        mask = os.urandom(4)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self._send_raw(bytes(header) + mask + masked)

    def recv_json(self) -> dict:
        payload = self._recv_frame()
        return json.loads(payload.decode("utf-8"))

    def _recv_frame(self) -> bytes:
        first = self._recv_exact(2)
        opcode = first[0] & 0x0F
        length = first[1] & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]
        masked = bool(first[1] & 0x80)
        mask = self._recv_exact(4) if masked else b""
        data = self._recv_exact(length)
        if masked:
            data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        if opcode == 8:
            raise OBSContextError("OBS WebSocket closed")
        if opcode == 9:
            self._send_raw(b"\x8a\x80" + os.urandom(4))
            return self._recv_frame()
        return data

    def _send_raw(self, data: bytes) -> None:
        if self.sock is None:
            raise OBSContextError("socket not connected")
        self.sock.sendall(data)

    def _recv_exact(self, size: int) -> bytes:
        if self.sock is None:
            raise OBSContextError("socket not connected")
        chunks = bytearray()
        while len(chunks) < size:
            chunk = self.sock.recv(size - len(chunks))
            if not chunk:
                raise OBSContextError("OBS WebSocket connection closed")
            chunks.extend(chunk)
        return bytes(chunks)

    def _recv_until(self, marker: bytes) -> bytes:
        if self.sock is None:
            raise OBSContextError("socket not connected")
        chunks = bytearray()
        while marker not in chunks:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise OBSContextError("OBS WebSocket connection closed during handshake")
            chunks.extend(chunk)
        return bytes(chunks)


def _obs_auth(password: str, salt: str, challenge: str) -> str:
    secret = base64.b64encode(hashlib.sha256((password + salt).encode("utf-8")).digest())
    return base64.b64encode(hashlib.sha256(secret + challenge.encode("utf-8")).digest()).decode("ascii")


def get_obs_context(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    password: str = DEFAULT_PASSWORD,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict:
    observed_at = datetime.now(timezone.utc).isoformat()
    base = {
        "available": False,
        "host": host,
        "port": port,
        "scene": None,
        "recording": None,
        "recording_duration_seconds": None,
        "streaming": None,
        "virtual_camera": None,
        "sources": [],
        "microphone_activity": "unknown",
        "desktop_audio_activity": "unknown",
        "profile": None,
        "scene_collection": None,
        "last_obs_error": None,
        "observed_at": observed_at,
        "raw_video_stored": False,
        "raw_audio_stored": False,
        "write_permissions": False,
    }
    try:
        with _OBSWebSocket(host, port, password, timeout) as obs:
            version = obs.request("GetVersion")
            scene = obs.request("GetCurrentProgramScene")
            record = obs.request("GetRecordStatus")
            stream = obs.request("GetStreamStatus")
            virtual_cam = obs.request("GetVirtualCamStatus")
            scene_list = obs.request("GetSceneList")
            inputs = obs.request("GetInputList")
            try:
                profiles = obs.request("GetProfileList")
            except Exception:
                profiles = {}
            try:
                collections = obs.request("GetSceneCollectionList")
            except Exception:
                collections = {}

            scene_name = scene.get("currentProgramSceneName")
            sources = []
            if scene_name:
                try:
                    items = obs.request("GetSceneItemList", {"sceneName": scene_name}).get("sceneItems", [])
                except Exception:
                    items = []
                for item in items:
                    sources.append({
                        "name": item.get("sourceName"),
                        "visible": bool(item.get("sceneItemEnabled")),
                    })

            audio_inputs = inputs.get("inputs", [])
            mic_status = _audio_activity_status(audio_inputs, "mic")
            desktop_status = _audio_activity_status(audio_inputs, "desktop")

            base.update({
                "available": True,
                "obs_version": version.get("obsVersion"),
                "websocket_version": version.get("obsWebSocketVersion"),
                "scene": scene_name,
                "recording": bool(record.get("outputActive")),
                "recording_duration_seconds": _duration_ms_to_seconds(record.get("outputDuration")),
                "streaming": bool(stream.get("outputActive")),
                "virtual_camera": bool(virtual_cam.get("outputActive")),
                "sources": sources,
                "microphone_activity": mic_status,
                "desktop_audio_activity": desktop_status,
                "profile": profiles.get("currentProfileName"),
                "scene_collection": collections.get("currentSceneCollectionName") or scene_list.get("currentSceneCollectionName"),
            })
    except Exception as exc:
        base["last_obs_error"] = f"{type(exc).__name__}: {exc}"
    return base


def _duration_ms_to_seconds(value: Any) -> int | None:
    try:
        return int(int(value) / 1000)
    except Exception:
        return None


def _audio_activity_status(inputs: list[dict], needle: str) -> str:
    matched = []
    for item in inputs:
        name = str(item.get("inputName", "")).lower()
        kind = str(item.get("inputKind", "")).lower()
        if needle in name or needle in kind or ("audio" in kind and needle == "desktop"):
            matched.append(item)
    if not matched:
        return "unavailable"
    return "present"


if __name__ == "__main__":
    print(json.dumps(get_obs_context(), indent=2))
