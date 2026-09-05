"""Actionable transport errors without exposing raw exceptions or device secrets."""
from serial import SerialException


def communication_error(error, transport=None):
    message = str(error).lower()
    timed_out = isinstance(error, TimeoutError) or 'timed out' in message or 'não respondeu a tempo' in message
    if isinstance(error, SerialException):
        transport = 'serial'
    if transport == 'serial':
        if 'cannot configure port' in message:
            return ('O Windows reconhece a porta, mas não conseguiu inicializar a comunicação USB/Serial. '
                    'Desconecte e reconecte o cabo de dados; se persistir, desligue e ligue o rádio com o cabo conectado.')
        if 'could not open port' in message and ('access is denied' in message or 'acesso negado' in message):
            return ('Não foi possível abrir a porta USB/Serial: acesso negado ou porta ocupada. '
                    'Feche outros clientes e monitores seriais que utilizem esse rádio e tente novamente.')
        if timed_out:
            return ('O rádio não respondeu pela conexão USB/Serial dentro do prazo. Confira se ele está ligado '
                    'e se outro cliente ou a interface do aparelho está ocupando a API. A consulta também pode não ser suportada pelo firmware.')
        return ('Não foi possível concluir a comunicação USB/Serial. Confira o cabo de dados, se a porta ainda '
                'aparece em Buscar portas e se outros clientes estão usando o rádio.')
    if transport == 'tcp':
        if isinstance(error, ConnectionRefusedError):
            return ('O dispositivo recusou a conexão TCP. Confira o IP e a porta (normalmente 4403). '
                    'O firmware pode não oferecer esse serviço; no T-Deck examinado, ele fica desativado no modo MUI.')
        return ('Não foi possível concluir a comunicação TCP. Confira o IP, a porta, o acesso pela rede e o Wi-Fi '
                'do rádio. Alguns firmwares desativam o TCP no modo MUI; outro cliente também pode estar ocupando a API.')
    return 'Não foi possível concluir a comunicação com o rádio. Confira a conexão e o suporte do firmware para esta operação.'
