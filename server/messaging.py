"""Reviewed sends, bounded reception and explicit continuous desktop listening."""
from contextlib import nullcontext
import secrets
import threading
import time

from fastapi import HTTPException
from pydantic import BaseModel, Field

from .messages import MAX_TEXT_BYTES
from .device import DeviceSession
from .errors import communication_error


class MessageDraft(BaseModel):
    text: str = Field(min_length=1, max_length=233)
    channel: int = Field(ge=0, le=7, strict=True)
    destination: str | None = Field(default=None, pattern=r"^![0-9a-f]{8}$")


class MessageSend(BaseModel):
    token: str = Field(min_length=1, max_length=100)


class Messaging:
    def init_messaging(self):
        self.message_previews = {}
        self.message_busy = threading.Lock()
        self.listen_stop = threading.Event()
        self.listening = False
        self.active_thread = None
        self.active_stop = threading.Event()
        self.active_transport = None
        self.active_phase = 'off'
        self.active_error = ''
        self.disconnecting = False

    def message_state(self):
        # Do not take the radio lock: polling and Stop must work during reception.
        dev = self.device
        return {"messages": dev.messages.snapshot() if dev else [],
                "listening": self.listening or self.active_phase in ('starting', 'active', 'stopping'),
                "listen_mode": 'active' if self.active_thread else 'window' if self.listening else 'off',
                "active_phase": self.active_phase, "listen_error": self.active_error,
                "max_bytes": MAX_TEXT_BYTES,
                "can_send": bool(dev and (dev.demo or self.allow_writes)),
                "epoch": self.epoch}

    def check_message(self, dev, draft):
        if not draft.text.strip() or len(draft.text.encode("utf-8")) > MAX_TEXT_BYTES or '\x00' in draft.text:
            raise HTTPException(400, f"Escreva uma mensagem de até {MAX_TEXT_BYTES} bytes UTF-8, sem caracteres nulos.")
        channel = dev.entries.get(f"channel.{draft.channel}")
        if channel is None or channel.role not in (1, 2):
            raise HTTPException(409, "Escolha um canal habilitado e já lido.")
        if draft.destination:
            if draft.destination in {dev.node_id, '!00000000', '!ffffffff'}:
                raise HTTPException(400, "Escolha outro nó para a mensagem direta.")
            if draft.destination not in {n['id'] for n in dev.nodes()}:
                raise HTTPException(400, "O destinatário precisa estar na lista de nós conhecidos.")
        lora = dev.entries.get('config.lora')
        if lora is None or not lora.tx_enabled:
            raise HTTPException(409, "A transmissão LoRa está desabilitada ou ainda não foi consultada.")
        return self.revision(channel), self.revision(lora)

    def preview_message(self, draft):
        with self.lock:
            dev = self.require()
            channel_rev, lora_rev = self.check_message(dev, draft)
            if not dev.demo and not self.allow_writes:
                raise HTTPException(403, "O envio de mensagens está bloqueado no modo somente leitura.")
            self.message_previews = {k: v for k, v in self.message_previews.items() if v['expires'] > time.monotonic()}
            if len(self.message_previews) >= 20:
                self.message_previews.clear()
            token = secrets.token_urlsafe(32)
            self.message_previews[token] = {"draft": draft, "epoch": self.epoch, "node_id": dev.node_id,
                "channel_rev": channel_rev, "lora_rev": lora_rev, "expires": time.monotonic() + 300}
            return {"token": token, "text": draft.text, "destination": draft.destination,
                    "channel": draft.channel, "bytes": len(draft.text.encode('utf-8')), "demo": dev.demo}

    def send_message(self, body):
        if not self.message_busy.acquire(blocking=False):
            raise HTTPException(409, "Pare a recepção ou aguarde o envio atual.")
        try:
            with self.lock:
                selected = self.require()
                if not selected.demo and not self.allow_writes:
                    raise HTTPException(403, "O envio de mensagens está bloqueado no modo somente leitura.")
                review = self.message_previews.pop(body.token, None)
                if not review or review['epoch'] != self.epoch or review['node_id'] != selected.node_id or review['expires'] < time.monotonic():
                    raise HTTPException(409, "Revisão de mensagem inválida ou expirada. Revise novamente.")
                draft = review['draft']
                # Connection and fresh channel checks happen before any text packet is authorized.
                with self.communication() as dev:
                    if dev is self.active_transport and not dev.demo:
                        dev.read(f'channel.{draft.channel}')
                        dev.read('config.lora')
                    if self.check_message(dev, draft) != (review['channel_rev'], review['lora_rev']):
                        raise HTTPException(409, "O canal ou o rádio mudou. Nenhuma mensagem enviada; releia e revise novamente.")
                    box = selected.messages
                    item_id = box.outgoing(draft.text, draft.destination, draft.channel, dev.node_id)
                    try:
                        dev.send_text(draft.text, draft.destination, draft.channel, box, item_id)
                    except Exception:
                        box.update(item_id, status='unknown')
                        raise HTTPException(502, "Resultado do envio desconhecido. Confira o histórico; o app não repetirá o envio.") from None
                self.log('Mensagem simulada' if selected.demo else 'Envio de mensagem', 'Consulte o resultado na conversa.')
            return self.message_state()
        finally:
            self.message_busy.release()

    def receive_messages(self):
        if not self.message_busy.acquire(blocking=False):
            raise HTTPException(409, "Já existe uma operação de mensagens em andamento.")
        try:
            with self.lock:
                if self.active_thread or self.disconnecting:
                    raise HTTPException(409, "Pare a escuta ativa antes de iniciar uma janela de recepção.")
                self.listen_stop.clear()
                self.listening = True
                with self.communication() as dev:
                    if dev.demo:
                        dev.simulate_incoming()
                    else:
                        self.listen_stop.wait(30)
        finally:
            self.listening = False
            self.message_busy.release()
        return self.message_state()

    def start_active_listening(self):
        if not self.message_busy.acquire(blocking=False):
            raise HTTPException(409, "Aguarde a operação de mensagens atual.")
        try:
            with self.lock:
                self.require()
                if self.active_thread or self.disconnecting:
                    raise HTTPException(409, "A escuta ativa já está iniciando, em andamento ou encerrando.")
                self.active_stop.clear()
                self.active_error = ''
                self.active_phase = 'starting'
                self.active_thread = threading.Thread(target=self._listen_active, name='desktop reception', daemon=True)
                self.active_thread.start()
                return self.message_state()
        finally:
            self.message_busy.release()

    def stop_reception(self):
        # Must remain usable while a handshake or a send owns the radio lock.
        self.listen_stop.set()
        self.active_stop.set()
        if self.active_thread:
            self.active_phase = 'stopping'

    def _listen_active(self):
        context = None
        entered = False
        failure = False
        error_detail = ''
        selected = None
        try:
            with self.lock:
                if self.active_stop.is_set():
                    return
                selected = self.require()
                context = selected.operation() if isinstance(selected, DeviceSession) else nullcontext(selected)
                dev = context.__enter__()
                entered = True
                self.active_transport = dev
                self.active_phase = 'stopping' if self.active_stop.is_set() else 'active'
                if dev.demo:
                    dev.simulate_incoming()
                self.log('Escuta ativa', 'Conexão mantida aberta para receber e enviar pelo desktop.')
            # The library's reader delivers incoming packets; do not hold the
            # manager lock here, so navigation, sends and settings remain usable.
            while not self.active_stop.wait(.25):
                with self.lock:
                    if not dev.connected():
                        raise ConnectionError('Reception transport closed')
        except Exception as error:
            failure = not self.active_stop.is_set()
            error_detail = communication_error(error, 'tcp' if getattr(selected, 'host', None) else 'serial')
        finally:
            with self.lock:
                self.active_transport = None
                try:
                    if entered:
                        context.__exit__(None, None, None)
                except Exception as error:
                    failure = True
                    error_detail = communication_error(error, 'tcp' if getattr(selected, 'host', None) else 'serial')
                self.active_phase = 'error' if failure else 'off'
                self.active_error = (f'A escuta foi interrompida. {error_detail} Inicie novamente quando a conexão estiver disponível; não houve reconexão automática.' if failure else '')
                self.active_thread = None
                self.log('Escuta interrompida' if failure else 'Escuta encerrada',
                         self.active_error or 'Conexão liberada; histórico preservado.', 'warning' if failure else 'info')
