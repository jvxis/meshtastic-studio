"""Mesh Studio: loopback API, in-memory drafts and fail-closed serial access."""
from contextlib import asynccontextmanager, contextmanager, nullcontext
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import threading
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from serial.tools import list_ports
from .schema import DEFINITIONS, OWNER_FIELDS, as_dict, public_schema, redact, prepare, diff
from .device import DeviceSession, write_command
from .demo import DemoDevice
from .messaging import Messaging, MessageDraft, MessageSend
from meshtastic.protobuf import mesh_pb2

ROOT = Path(__file__).resolve().parent.parent


class ConnectBody(BaseModel):
    port: str = Field(min_length=1, max_length=80)


class PreviewBody(BaseModel):
    section: str = Field(max_length=80)
    revision: str = Field(max_length=100)
    values: dict


class ApplyBody(BaseModel):
    token: str = Field(max_length=100)
    confirmation: str = Field(max_length=100)


class Manager(Messaging):
    def __init__(self, allow_writes=False):
        self.allow_writes = allow_writes
        self.device = None
        self.lock = threading.RLock()
        self.epoch = secrets.token_hex(16)
        self.previews = {}
        self.events = []
        self.init_messaging()

    def log(self, action, detail, level="info"):
        self.events.insert(0, {"time": datetime.now(timezone.utc).isoformat(), "action": action,
                               "detail": detail, "level": level})
        self.events = self.events[:100]

    def require(self):
        if not self.device or (not isinstance(self.device, DeviceSession) and not self.device.connected()):
            raise HTTPException(409, "Conecte um dispositivo antes de continuar.")
        return self.device

    @contextmanager
    def communication(self):
        dev = self.require()
        with dev.operation() if isinstance(dev, DeviceSession) else nullcontext(dev) as transport:
            yield transport

    def revision(self, value):
        raw = value.SerializeToString(deterministic=True) if hasattr(value, "SerializeToString") else json.dumps(value, sort_keys=True).encode()
        return hashlib.sha256(self.epoch.encode() + raw).hexdigest()

    def section(self, key):
        value = self.device.entries.get(key)
        if value is None:
            return {"available": False, "values": None, "revision": None}
        obj = as_dict(value) if hasattr(value, "SerializeToString") else copy.deepcopy(value)
        if key == "owner":
            obj = {k: v for k, v in obj.items() if k in OWNER_FIELDS}
        return {"available": True, "values": redact(obj), "revision": self.revision(value)}

    def state(self):
        with self.lock:
            dev = self.device
            return {"session_active": dev is not None,
                    "observed_at": getattr(dev, "observed_at", None),
                    "connected": bool(dev and dev.connected()), "demo": bool(dev and dev.demo),
                    "writes_enabled": bool(dev and (dev.demo or self.allow_writes)),
                    "server_writes_enabled": self.allow_writes, "epoch": self.epoch,
                    "device": dev.summary() if dev else None,
                    "sections": {key: self.section(key) for key in DEFINITIONS} if dev else {},
                    "nodes": dev.nodes() if dev else [], "events": self.events}

    def disconnect(self):
        self.listen_stop.set()
        with self.lock:
            if self.device:
                self.device.close()
                self.log("Desconexão", "Porta liberada.")
            self.device = None
            self.previews.clear()
            self.message_previews.clear()
            self.epoch = secrets.token_hex(16)

    def connect(self, port=None, demo=False):
        with self.lock:
            if self.device:
                raise HTTPException(409, "Desconecte a sessão atual antes de abrir outra.")
            if not demo and port not in {p.device for p in list_ports.comports()}:
                raise HTTPException(400, "Escolha uma porta serial presente nesta máquina.")
            self.device = DemoDevice() if demo else DeviceSession(port)
            self.epoch = secrets.token_hex(16)
            self.log("Demonstração" if demo else "Leitura concluída", "Dispositivo simulado, sem acesso à serial." if demo else f"Leitura de {port} concluída; porta liberada automaticamente. Nenhuma configuração enviada.")
            return self.state()

    def read(self, key):
        with self.lock:
            if key not in DEFINITIONS:
                raise HTTPException(404, "Seção desconhecida.")
            with self.communication() as dev:
                dev.read(key)
            self.log("Consulta", DEFINITIONS[key]["name"])
            return self.state()

    def preview(self, body):
        with self.lock:
            dev = self.require()
            if body.section not in DEFINITIONS or body.section not in dev.entries:
                raise HTTPException(409, "Leia esta seção do dispositivo antes de editá-la.")
            original = dev.entries[body.section]
            if self.revision(original) != body.revision:
                raise HTTPException(409, "A leitura mudou. Releia a seção e refaça o rascunho.")
            target, changes = prepare(body.section, body.values, original)
            if body.section.startswith("channel."):
                role = target.role
                if (body.section == "channel.0" and role != 1) or (body.section != "channel.0" and role == 1):
                    raise HTTPException(400, "O canal 0 deve permanecer como principal; os outros podem ser secundários ou desabilitados.")
            if not changes:
                raise HTTPException(400, "O rascunho não contém alterações.")
            command = write_command(body.section, target)
            # Reserve space for the session passkey appended by the device adapter.
            command.session_passkey = bytes(32)
            if len(command.SerializeToString()) > mesh_pb2.Constants.DATA_PAYLOAD_LEN:
                raise HTTPException(400, "Esta configuração excede o tamanho de um pacote administrativo.")
            warnings = []
            if body.section in {"config.lora", "config.network", "config.bluetooth", "config.security", "config.device"} or body.section.startswith("channel."):
                warnings.append("A mudança pode reiniciar o rádio ou interromper a conexão. A gravação será conferida por uma nova leitura.")
            if any(c["path"] == "is_licensed" for c in changes):
                warnings.append("O modo de radioamador pode mudar o comportamento de criptografia do firmware.")
            self.previews = {k: v for k, v in self.previews.items() if v["expires"] > time.monotonic()}
            if len(self.previews) >= 20:
                self.previews.clear()
            token = secrets.token_urlsafe(32)
            self.previews[token] = {"section": body.section, "revision": body.revision,
                "target": target, "node_id": dev.node_id, "epoch": self.epoch,
                "expires": time.monotonic() + 300}
            return {"token": token, "changes": changes, "warnings": warnings,
                    "confirmation": f"APLICAR {dev.node_id}", "expires_in": 300,
                    "can_apply": dev.demo or self.allow_writes, "demo": dev.demo}

    @contextmanager
    def communication_for_apply(self, body):
        dev = self.require()
        if not dev.demo and not self.allow_writes:
            raise HTTPException(403, "A gravação real está bloqueada no servidor.")
        preview = self.previews.get(body.token)
        if not preview or preview["expires"] < time.monotonic() or preview["epoch"] != self.epoch:
            raise HTTPException(409, "A revisão expirou. Revise o rascunho novamente.")
        if body.confirmation != f"APLICAR {dev.node_id}" or preview["node_id"] != dev.node_id:
            raise HTTPException(400, "A confirmação precisa corresponder ao dispositivo selecionado.")
        with self.communication() as transport:
            yield transport

    def apply(self, body):
        with self.lock:
            with self.communication_for_apply(body) as dev:
                if not dev.demo and not self.allow_writes:
                    raise HTTPException(403, "A gravação real está bloqueada no servidor. Este processo está em modo somente leitura.")
                preview = self.previews.get(body.token)
                if not preview or preview["expires"] < time.monotonic() or preview["epoch"] != self.epoch:
                    raise HTTPException(409, "A revisão expirou. Revise o rascunho novamente.")
                if body.confirmation != f"APLICAR {dev.node_id}" or preview["node_id"] != dev.node_id:
                    raise HTTPException(400, "A confirmação precisa corresponder ao dispositivo conectado.")
                self.previews.pop(body.token)
                key = preview["section"]
                current = dev.read(key)  # Detect edits by another client before sending anything.
                if self.revision(current) != preview["revision"]:
                    raise HTTPException(409, "O dispositivo mudou desde a leitura. Nenhuma alteração foi enviada; atualize e revise novamente.")
                try:
                    actual = dev.write(key, preview["target"])
                    target_dict = as_dict(preview["target"]) if hasattr(actual, "SerializeToString") else preview["target"]
                    actual_dict = as_dict(actual) if hasattr(actual, "SerializeToString") else actual
                    if key == "owner":
                        target_dict = {k: v for k, v in target_dict.items() if k in OWNER_FIELDS}
                        actual_dict = {k: v for k, v in actual_dict.items() if k in OWNER_FIELDS}
                    if diff(target_dict, actual_dict):
                        raise RuntimeError("A releitura não corresponde ao rascunho.")
                except Exception:
                    dev.entries.pop(key, None)
                    self.previews.clear()
                    self.log("Verificação pendente", f"{DEFINITIONS[key]['name']}: envio iniciado, resultado não confirmado. Releia antes de tentar novamente.", "warning")
                    raise HTTPException(502, "A operação foi iniciada, mas não foi possível confirmar a gravação. O dispositivo pode ter reiniciado. Reconecte e releia; não repita a aplicação sem conferir.") from None
                self.previews.clear()
                self.log("Simulação aplicada" if dev.demo else "Gravação verificada", DEFINITIONS[key]["name"], "success")
            return self.state()


def create_app(manager=None):
    manager = manager or Manager(allow_writes=os.getenv("MESH_ALLOW_WRITES", "0") == "1")
    csrf_token = secrets.token_urlsafe(32)

    @asynccontextmanager
    async def lifespan(app):
        yield
        manager.disconnect()

    app = FastAPI(title="Mesh Studio", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.manager = manager
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.middleware("http")
    async def local_access(request: Request, call_next):
        origin = request.headers.get("origin")
        expected = str(request.base_url).rstrip("/")
        if request.headers.get("sec-fetch-site") == "cross-site" or (origin and origin != expected):
            return JSONResponse({"detail": "Acesso permitido somente pela própria interface local."}, status_code=403)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if not secrets.compare_digest(request.headers.get("x-mesh-token", ""), csrf_token):
                return JSONResponse({"detail": "Sessão inválida. Recarregue a página."}, status_code=403)
            try:
                length = int(request.headers.get("content-length", "0"))
            except ValueError:
                return JSONResponse({"detail": "Tamanho inválido."}, status_code=400)
            if length > 131072 or len(await request.body()) > 131072:
                return JSONResponse({"detail": "Requisição muito grande."}, status_code=413)
        response = await call_next(request)
        response.headers.update({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer", "Cross-Origin-Resource-Policy": "same-origin",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; form-action 'self'"})
        return response

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # FastAPI's default validation response can echo submitted passwords.
        return JSONResponse({"detail": "Requisição inválida. Confira os campos e o formato dos dados."}, status_code=422)

    @app.exception_handler(Exception)
    async def device_error(request, exc):
        manager.log("Consulta interrompida", "Verifique a conexão, a disponibilidade da porta e o suporte do firmware.", "warning")
        return JSONResponse({"detail": "Não foi possível concluir a comunicação. Verifique se a porta está livre e o dispositivo conectado. A consulta também pode não ser suportada por este firmware."}, status_code=503)

    # Expected serial failures are handled normally, without an ASGI traceback.
    for error_type in (TimeoutError, RuntimeError, PermissionError, OSError):
        app.add_exception_handler(error_type, device_error)

    @app.get("/api/session")
    def session():
        return {"token": csrf_token, "schema": public_schema(), "state": manager.state()}

    @app.get("/api/ports")
    def ports():
        return [{"port": p.device, "description": p.description, "usb": p.vid is not None} for p in list_ports.comports()]

    @app.get("/api/state")
    def state():
        return manager.state()

    @app.post("/api/connect")
    def connect(body: ConnectBody):
        return manager.connect(body.port)

    @app.post("/api/demo")
    def demo():
        return manager.connect(demo=True)

    @app.post("/api/disconnect")
    def disconnect():
        manager.disconnect()
        return manager.state()

    @app.post("/api/refresh")
    def refresh():
        with manager.lock:
            dev = manager.require()
            port, demo_mode = dev.port, dev.demo
            if demo_mode:
                return manager.state()
            with manager.communication():
                pass
            manager.previews.clear()
            return manager.state()

    @app.post("/api/read/{key}")
    def read(key: str):
        return manager.read(key)

    @app.post("/api/preview")
    def preview(body: PreviewBody):
        return manager.preview(body)

    @app.post("/api/apply")
    def apply(body: ApplyBody):
        return manager.apply(body)

    @app.get("/api/messages")
    def messages():
        return manager.message_state()

    @app.post("/api/messages/preview")
    def preview_message(body: MessageDraft):
        return manager.preview_message(body)

    @app.post("/api/messages/send")
    def send_message(body: MessageSend):
        return manager.send_message(body)

    @app.post("/api/messages/receive")
    def receive_messages():
        return manager.receive_messages()

    @app.post("/api/messages/stop")
    def stop_messages():
        manager.listen_stop.set()
        return {"stopping": True}

    @app.get("/")
    def index():
        return FileResponse(ROOT / "static" / "index.html")

    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    return app


app = create_app()
