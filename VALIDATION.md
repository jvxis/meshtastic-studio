# Validação inicial — 5 de setembro de 2026

## Testes sem hardware

- `python -m pytest -q`: **27 testes aprovados**. Dois avisos de depreciação de dependências do cliente de testes; nenhuma falha.
- `python tests/browser_smoke.py`: aprovado no Chrome, em desktop 1440 px e tela pequena de 390 px, sem erros de JavaScript ou rolagem horizontal da página.
- `node --check static/app.js`: aprovado.
- Fluxos de navegador exercitados: conexão simulada, formulário, JSON avançado, preservação de segredos, listas inválidas, revisão, confirmação digitada, aplicação simulada com releitura, descarte, canais, busca de nós e extras.
- Casos de proteção: bloqueio de gravação real, token falso/expirado/reutilizado, confirmação de outro nó, leitura desatualizada, falha de verificação, Host/Origin/CSRF, limites nanopb, valores inválidos, preservação de campos protobuf desconhecidos e rejeição de comandos de reset/reboot/mensagens na serial.
- Consultas que expiram são repetidas no máximo uma vez. Gravações não recebem repetição automática pelo aplicativo.

## Leitura real

Dispositivo consultado: T-Deck por USB/serial, firmware `2.7.26.54e0d8d`.

- A conexão inicial retornou **30 seções** de configurações.
- Consultas sob demanda adicionaram a configuração da tela, o toque e o módulo de mensagem de status: **33 seções disponíveis de um catálogo de 36**.
- `module.traffic_management`, `module.tak` e os textos de mensagens prontas (`canned_text`) não responderam dentro do limite de consulta. Isso não permite concluir, isoladamente, se o recurso está ausente ou indisponível no estado atual. Permanecem sem edição até uma leitura bem-sucedida.
- As releituras bem-sucedidas de LoRa, rede, segurança e identificação coincidiram com os respectivos estados iniciais verificados durante a sessão.
- O painel real foi aberto no Chrome, com navegação entre todas as áreas.
- Um rascunho de limite de saltos foi revisado no navegador. O botão de aplicação permaneceu desabilitado; o rascunho foi descartado. A revisão da configuração LoRa continuou idêntica antes e depois.
- **Zero pacotes de gravação foram enviados à serial em todas as conexões de validação.** O servidor permaneceu com `MESH_ALLOW_WRITES=0`.

## Limites da verificação

A aplicação de configurações reais não foi testada, atendendo à instrução de não modificar o dispositivo. O fluxo de envio e conferência foi testado com um dispositivo simulado; suporte de firmware, comportamento após reinício e limites específicos de hardware precisam ser verificados quando uma gravação real for autorizada.

O repositório irmão `../python` permaneceu sem alterações. Dados e screenshots da sessão real ficam apenas em `artifacts/`, ignorada pelo Git. Nenhuma senha, chave privada ou configuração integral foi exportada para esses arquivos.

## Preparação da publicação

Os 27 testes também passaram em um ambiente virtual novo, instalado exclusivamente com `requirements-dev.txt` e o pacote `meshtastic==2.7.11` do PyPI, sem instalar a biblioteca do repositório irmão. A imagem incluída no README usa exclusivamente dados fictícios do simulador.

O teste de navegador passou nesse ambiente limpo. O instalador PowerShell também foi executado sobre uma cópia independente do projeto, criando sua própria `.venv` e iniciando o catálogo de 36 seções com gravação bloqueada e nenhum hardware conectado. Para esse teste, a política `RemoteSigned` foi definida somente no processo PowerShell de teste; nenhuma política persistente do Windows foi alterada. O README inclui comandos manuais para máquinas em que scripts são bloqueados.
