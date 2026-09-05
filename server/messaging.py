"""Explicit send reviews and cancellable, bounded reception windows."""
import secrets
import threading
import time

from fastapi import HTTPException
from pydantic import BaseModel, Field

from .messages import MAX_TEXT_BYTES


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

    def message_state(self):
        # Do not take the radio lock: polling and Stop must work during reception.
        dev = self.device
        return {"messages": dev.messages.snapshot() if dev else [],
                "listening": self.listening, "max_bytes": MAX_TEXT_BYTES,
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
        self.listen_stop.clear()
        self.listening = True
        try:
            with self.lock:
                with self.communication() as dev:
                    if dev.demo:
                        dev.simulate_incoming()
                    else:
                        self.listen_stop.wait(30)
        finally:
            self.listening = False
            self.message_busy.release()
        return self.message_state()
