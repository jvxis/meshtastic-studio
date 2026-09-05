"""Descriptor driven settings. Secrets never leave the server in clear text."""
import base64
import copy
import math
from google.protobuf import descriptor, json_format, message_factory
from meshtastic.protobuf import localonly_pb2, mesh_pb2, channel_pb2, device_ui_pb2, nanopb_pb2

MASK = "__MESH_SECRET_UNCHANGED__"
SECRET_NAMES = {"psk", "password", "wifi_psk", "private_key", "session_passkey",
                "admin_session_pass_key", "fixed_pin", "pin_code", "username"}
OWNER_FIELDS = {"long_name", "short_name", "is_licensed", "is_unmessagable"}
LABELS = {
    "device": "Dispositivo", "position": "Posição e GPS", "power": "Energia",
    "network": "Wi-Fi e rede", "display": "Display", "lora": "Rádio LoRa",
    "bluetooth": "Bluetooth", "security": "Segurança", "mqtt": "MQTT",
    "serial": "Serial", "external_notification": "Notificações externas",
    "store_forward": "Store & Forward", "range_test": "Teste de alcance",
    "telemetry": "Telemetria", "canned_message": "Mensagens prontas",
    "audio": "Áudio", "remote_hardware": "Hardware remoto", "neighbor_info": "Vizinhos",
    "ambient_lighting": "Iluminação", "detection_sensor": "Sensor de detecção",
    "paxcounter": "Contador de pessoas", "statusmessage": "Mensagem de status",
    "traffic_management": "Gestão de tráfego", "tak": "TAK",
    "owner": "Identificação", "ui": "Interface da tela", "ringtone": "Toque",
    "canned_text": "Textos das mensagens prontas",
}


def is_secret(name):
    return name.lower() in SECRET_NAMES or "password" in name.lower() or "secret" in name.lower()


def as_dict(message):
    return json_format.MessageToDict(message, preserving_proto_field_name=True,
                                    always_print_fields_with_no_presence=True)


def redact(value):
    if isinstance(value, dict):
        return {k: MASK if is_secret(k) and v not in (None, "", 0, []) else redact(v)
                for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def restore_secrets(candidate, original):
    if isinstance(candidate, dict):
        return {k: copy.deepcopy(original[k]) if is_secret(k) and v == MASK and k in original
                else restore_secrets(v, original.get(k, {})) for k, v in candidate.items()}
    if isinstance(candidate, list):
        old = original if isinstance(original, list) else []
        return [restore_secrets(v, old[i] if i < len(old) else {}) for i, v in enumerate(candidate)]
    return candidate


def message_schema(desc, depth=0):
    fields = []
    for field in desc.fields:
        f = {"name": field.name, "secret": is_secret(field.name),
             "repeated": field.is_repeated, "readonly": field.name in {"version", "index"}}
        if field.message_type:
            f["kind"] = "object"
            f["fields"] = message_schema(field.message_type, depth + 1) if depth < 6 else []
        elif field.enum_type:
            f.update(kind="enum", options=[v.name for v in field.enum_type.values],
                     default=field.enum_type.values[0].name)
        elif field.type == descriptor.FieldDescriptor.TYPE_BOOL:
            f.update(kind="bool", default=False)
        elif field.type == descriptor.FieldDescriptor.TYPE_BYTES:
            f.update(kind="bytes", default="")
        elif field.type == descriptor.FieldDescriptor.TYPE_STRING:
            f.update(kind="string", default="")
        else:
            integer = field.type not in (1, 2)
            unsigned = field.type in (4, 6, 7, 13)
            bits = 64 if field.type in (3, 4, 6, 16, 18) else 32
            f.update(kind="integer" if integer else "number", default="0" if integer and bits == 64 else 0)
            if integer:
                f.update(min=str(0 if unsigned else -(2 ** (bits - 1))),
                         max=str(2 ** bits - 1 if unsigned else 2 ** (bits - 1) - 1), bits=bits)
        if field.is_repeated:
            f["default"] = []
        opts = field.GetOptions()
        if opts.HasExtension(nanopb_pb2.nanopb):
            nano = opts.Extensions[nanopb_pb2.nanopb]
            if nano.max_size:
                f["max_bytes"] = nano.max_size - (1 if f["kind"] == "string" else 0)
            if nano.max_count:
                f["max_count"] = nano.max_count
            if nano.int_size and f["kind"] == "integer":
                bits = int(nanopb_pb2.IntSize.Name(nano.int_size).split("_")[1])
                unsigned = field.type in (4, 6, 7, 13)
                f.update(min=str(0 if unsigned else -(2 ** (bits - 1))),
                         max=str(2 ** bits - 1 if unsigned else 2 ** (bits - 1) - 1), bits=bits)
        fields.append(f)
    return fields


def definitions():
    result = {}
    for prefix, cls in [("config", localonly_pb2.LocalConfig), ("module", localonly_pb2.LocalModuleConfig)]:
        for f in cls.DESCRIPTOR.fields:
            if f.message_type:
                key = f"{prefix}.{f.name}"
                result[key] = {"id": key, "name": LABELS.get(f.name, f.name), "group": prefix,
                               "fields": message_schema(f.message_type), "descriptor": f.message_type}
    for key, desc in [("owner", mesh_pb2.User.DESCRIPTOR), ("ui", device_ui_pb2.DeviceUIConfig.DESCRIPTOR)]:
        fields = message_schema(desc)
        if key == "owner":
            fields = [f for f in fields if f["name"] in OWNER_FIELDS]
        result[key] = {"id": key, "name": LABELS[key], "group": "device", "fields": fields, "descriptor": desc}
    for index in range(8):
        key = f"channel.{index}"
        result[key] = {"id": key, "name": f"Canal {index}", "group": "channel",
                       "fields": message_schema(channel_pb2.Channel.DESCRIPTOR),
                       "descriptor": channel_pb2.Channel.DESCRIPTOR}
    for key in ("ringtone", "canned_text"):
        result[key] = {"id": key, "name": LABELS[key], "group": "extra",
                       "fields": [{"name": "text", "kind": "string", "default": "", "secret": False, "repeated": False}],
                       "descriptor": None}
    return result


DEFINITIONS = definitions()


def public_schema():
    return [{k: v for k, v in d.items() if k != "descriptor"} for d in DEFINITIONS.values()]


def validate_types(value, fields, path=""):
    if not isinstance(value, dict):
        raise ValueError("A configuração precisa ser um objeto JSON.")
    allowed = {f["name"]: f for f in fields}
    for key, item in value.items():
        location = f"{path}.{key}".strip(".")
        if key not in allowed:
            raise ValueError(f"Campo desconhecido: {location}")
        f = allowed[key]
        items = item if f["repeated"] else [item]
        if f["repeated"] and not isinstance(item, list):
            raise ValueError(f"{location}: informe uma lista JSON.")
        if f["repeated"] and f.get("max_count") and len(item) > f["max_count"]:
            raise ValueError(f"{location}: no máximo {f['max_count']} itens.")
        for val in items:
            if f["kind"] == "object":
                validate_types(val, f["fields"], location)
            elif f["kind"] == "bool" and not isinstance(val, bool):
                raise ValueError(f"{location}: esperado true ou false.")
            elif f["kind"] == "enum" and val not in f["options"]:
                raise ValueError(f"{location}: opção desconhecida.")
            elif f["kind"] in ("string", "bytes"):
                if not isinstance(val, str):
                    raise ValueError(f"{location}: esperado texto.")
                if f["kind"] == "bytes":
                    try:
                        raw = base64.b64decode(val, validate=True)
                    except Exception:
                        raise ValueError(f"{location}: use Base64 válido.") from None
                else:
                    raw = val.encode("utf-8")
                if f.get("max_bytes") is not None and len(raw) > f["max_bytes"]:
                    raise ValueError(f"{location}: no máximo {f['max_bytes']} bytes.")
            elif f["kind"] == "integer":
                if isinstance(val, bool) or not isinstance(val, (int, str)):
                    raise ValueError(f"{location}: esperado número inteiro.")
                try:
                    n = int(val)
                except (ValueError, TypeError):
                    raise ValueError(f"{location}: esperado número inteiro.") from None
                if not int(f["min"]) <= n <= int(f["max"]):
                    raise ValueError(f"{location}: número fora do intervalo do protocolo.")
            elif f["kind"] == "number" and (isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val)):
                raise ValueError(f"{location}: esperado número finito.")


def diff(before, after, prefix=""):
    result = []
    if isinstance(before, dict) and isinstance(after, dict):
        for k in sorted(before.keys() | after.keys()):
            result += diff(before.get(k), after.get(k), f"{prefix}.{k}".strip("."))
    elif before != after:
        secret = any(is_secret(p) for p in prefix.split("."))
        result.append({"path": prefix, "before": "[protegido]" if secret else redact(before),
                       "after": "[protegido alterado]" if secret else redact(after)})
    return result


def prepare(key, candidate, original):
    definition = DEFINITIONS[key]
    base = as_dict(original) if definition["descriptor"] else copy.deepcopy(original)
    if key == "owner":
        base = {k: v for k, v in base.items() if k in OWNER_FIELDS}
    merged = restore_secrets(candidate, base)
    validate_types(merged, definition["fields"])
    for f in definition["fields"]:
        if f.get("readonly") and merged.get(f["name"]) != base.get(f["name"]):
            raise ValueError(f"O campo {f['name']} é somente leitura.")
    if key == "owner":
        if not merged.get("long_name", "").strip() or not merged.get("short_name", "").strip():
            raise ValueError("Preencha o nome e o nome curto.")
        if len(merged["short_name"]) > 4:
            raise ValueError("O nome curto aceita até 4 caracteres.")
        if len(merged["long_name"].encode()) > 39:
            raise ValueError("O nome aceita até 39 bytes UTF-8.")
    if key.startswith("channel."):
        if len(merged.get("settings", {}).get("name", "").encode()) > 11:
            raise ValueError("O nome do canal aceita até 11 bytes UTF-8.")
        psk = base64.b64decode(merged.get("settings", {}).get("psk", ""))
        if len(psk) not in (0, 1, 16, 32):
            raise ValueError("A chave de canal precisa ter 0, 1, 16 ou 32 bytes.")
    if definition["descriptor"]:
        result = message_factory.GetMessageClass(definition["descriptor"])()
        result.CopyFrom(original)  # Preserve unknown firmware fields.
        for f in definition["fields"]:
            result.ClearField(f["name"])
        try:
            json_format.ParseDict(merged, result, ignore_unknown_fields=False)
        except (ValueError, json_format.ParseError, TypeError):
            raise ValueError("Um valor não é compatível com o formato do protocolo.") from None
        normalized = as_dict(result)
        if key == "owner":
            normalized = {k: v for k, v in normalized.items() if k in OWNER_FIELDS}
    else:
        result = merged
        normalized = merged
    return result, diff(base, normalized)
