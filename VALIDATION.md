# Validação inicial — 5 de setembro de 2026


## Atualização: conectar e receber em uma única conexão

- **123 testes de backend aprovados.** Em Desktop, a conexão inicial é transferida à recepção contínua sem fechar a porta nem repetir o handshake. Testes em transportes USB e TCP simulados verificam uma única abertura para receber, enviar a canais/destinatários e consultar configurações.
- Cobertos também: modo somente leitura, queda sem reconexão implícita, retomada explícita, falha na criação do leitor, falha no handshake, cancelamento durante a conexão inicial e parada na transferência para o leitor. Cada transporte aberto é encerrado uma única vez.
- Navegador aprovado em desktop e celular: seleção Desktop/Leitura pontual, corpo da conexão, estado conectado com recepção, botão Desconectar, envio direto sem modal, preservação de rascunhos e navegação pelas configurações. A página Mensagens não exibe avisos de revisão de configuração. O navegador consulta somente o estado em memória para acompanhar a conexão nas demais páginas.
- Servidor local atualizado na porta 8765. A tentativa no T-Deck físico ainda terminou em timeout no handshake USB, com a porta reconhecida pelo Windows. Portanto, a validação desta mudança com conexão física contínua permanece pendente; a correção evita a abertura duplicada, mas não comprova a recuperação dessa falha de comunicação.
- Nenhuma mensagem real ou gravação de configuração foi enviada durante esta validação. A leitura pública anterior e seus contadores foram preservados em memória; segredos não foram reconstruídos a partir dos valores ocultos.

## Atualização: envio direto de mensagens

- Removida a modal de revisão de mensagens. O botão Enviar e a tecla Enter validam e enviam diretamente; Shift+Enter insere uma quebra de linha. As autorizações de uso único, conferência de destino/canal e bloqueio de escrita continuam no servidor.
- Testes de navegador aprovados em desktop e celular: envio em canal e direto sem modal, escolha do canal de mensagem direta, texto HTML exibido literalmente, Enter/Shift+Enter, limite UTF-8, envio durante escuta ativa e prevenção de submissão duplicada.
- Uma resposta de envio foi retida no teste enquanto o usuário digitava outro rascunho e mudava de conversa. O novo texto e o destinatário original foram preservados. Foram testadas também rejeição de validação e perda de resposta após envio no simulador, sem reenvio automático nem perda do texto original.
- Os textos de envios com erro podem ser recuperados no editor sem substituir um rascunho existente. As explicações de recepção e entrega ficam recolhidas, deixando mais espaço para o histórico.
- Nenhuma mensagem real foi enviada e nenhuma configuração do aparelho foi modificada durante a validação. A atualização do frontend não exige reiniciar o servidor nem encerrar uma escuta ativa existente.

## Atualização: diagnóstico por tipo de conexão

- **111 testes de backend aprovados**, incluindo oito novos casos de falha na conexão inicial e em consultas posteriores. Erros USB/Serial não mencionam TCP; recusas e falhas TCP mantêm as orientações de rede. Exceções internas não são expostas nas respostas nem nos eventos.
- A falha Windows `Cannot configure port` recebe uma orientação específica de inicialização USB, separada de acesso negado/porta ocupada. A escuta ativa utiliza o mesmo diagnóstico por transporte.
- Antes desta correção, a escuta ativa foi validada no T-Deck físico por **40 segundos**, após leitura inicial de 30 seções. A interface web permaneceu utilizável, com envio/revisão e parada disponíveis. Nenhuma mensagem chegou nessa janela; foram enviados **zero pacotes de texto e zero gravações de configuração**. A parada liberou a conexão.
- Em uma tentativa posterior, o Windows voltou a enumerar a porta, mas falhou ao inicializá-la, com erro de dispositivo 31. Reiniciar somente a interface USB pelo Windows não resolveu essa tentativa. A mensagem genérica anterior mencionava TCP mesmo nesse erro serial; essa ambiguidade foi corrigida.

## Atualização: escuta ativa no desktop

- **103 testes de backend aprovados**, com 16 novos casos em transportes USB e TCP simulados: recepção contínua, envio de canal e direto na mesma conexão, recepção durante a espera de confirmação, leitura e aplicação de configurações durante escuta, bloqueio no modo somente leitura, conferência do canal antes de enviar, troca de rádio, parada durante handshake/envio, liberação ao desconectar e queda sem reconexão automática.
- Testes de navegador aprovados em desktop e celular: início da escuta, envio simulado sem parar a recepção, navegação até configurações, consulta de seção, retorno ao chat e parada explícita. Sem erros de JavaScript nem rolagem horizontal.
- A conexão é mantida por uma tarefa no servidor enquanto o leitor da biblioteca entrega os pacotes; a espera contínua não ocupa o bloqueio das operações administrativas. A parada permanece acessível durante handshake e envio.
- Não houve teste físico desta funcionalidade: o T-Deck não estava disponível na COM durante a implementação e seu firmware em MUI recusa TCP. Nenhuma configuração real foi alterada e nenhuma mensagem real foi enviada para validar a escuta ativa.
- README atualizado para diferenciar as conexões breves do modo contínuo, explicar o comportamento ao fechar a aba e preservar a limitação de 300 mensagens em memória.

## Atualização: conexão por rede / TCP

- **87 testes de backend aprovados**, incluindo os testes anteriores, sessões breves por USB e TCP, validação de IP/nome/porta, bloqueio de escrita em modo somente leitura, troca de identidade no mesmo endereço, falhas sem repetição e aviso ao revisar mudanças de rede via TCP.
- Um servidor TCP de teste em loopback exercitou o protocolo binário real da biblioteca: handshake com quadros fragmentados, identificação/configuração do rádio simulado e encerramento da conexão com zero gravações e zero mensagens enviadas. Os fluxos de aplicação/releitura e mensagens foram exercitados com transportes e dados simulados; nenhuma gravação física foi feita.
- O adaptador TCP usa limite de cinco segundos para conexão/socket e desativa a reconexão automática da biblioteca. Ambos os adaptadores enviam cada pacote uma vez, sem a espera indefinida da fila da biblioteca; somente consultas explícitas podem ser repetidas. Grants de escrita são consumidos após envio.
- Navegador aprovado em desktop e celular: selecionar Rede / TCP mostra IP/nome e porta 4403; alternar para USB mostra a lista serial; valores são preservados ao alternar. O corpo enviado à API foi conferido sem conectar a hardware. Os testes anteriores de configurações e mensagens também passaram.
- A tentativa somente de leitura no T-Deck físico foi recusada na porta TCP 4403, antes do handshake. O código da versão `2.7.26.54e0d8d` confirma que o servidor TCP não é iniciado em `displaymode=COLOR` (MUI). O modo de tela, Wi-Fi e demais configurações do aparelho foram preservados. Portanto, o TCP físico desse aparelho permanece sem validação funcional em modo compatível.
- README atualizado com instalação e conexão por IP, reserva DHCP, limitações da MUI e recuperação de confirmação pendente após alterações de rede. Nenhum IP, mensagem ou segredo real foi incluído no repositório.

## Atualização: mensagens de canais e diretas

- **54 testes de backend aprovados**, incluindo envio de canal e direto no simulador, revisão de uso único, mudança de canal após revisão, modo somente leitura, limite UTF-8, destino inválido, falha de envio sem repetição, confirmação tardia, deduplicação, isolamento de mensagens diretas para outros nós e janela de recepção limitada/cancelável.
- Testes de navegador aprovados em desktop e celular: recebimento simulado em canal e conversa direta, composição, revisão, envio simulado, escolha de canal para mensagens diretas e texto contendo HTML exibido sem executar código.
- Leitura e uma janela completa de recepção foram executadas no T-Deck real. A operação de recepção levou **52,3 segundos**, incluindo handshake e 30 segundos de escuta. Terminou com a porta liberada, **zero pacotes de texto enviados e zero gravações de configuração**.
- Nenhuma mensagem chegou nessa janela física. A recepção efetiva de textos e os envios com ACK foram verificados com dados e transporte simulados; a entrega entre rádios reais permanece sem teste nesta validação.
- Não há importação do histórico completo da MUI nem garantia de capturar mensagens enquanto a porta está livre. O histórico fica em memória e é apagado ao encerrar a sessão ou reiniciar o servidor.

## Atualização: conexões breves e campos obsoletos

- **35 testes de backend aprovados**, incluindo liberação da porta após leitura, atualização, aplicação simulada e erros; rejeição de outro rádio na mesma porta; alterações concorrentes pela tela; proteção de campos obsoletos e preservação quando omitidos do JSON.
- Teste de navegador aprovado em desktop e celular, incluindo GPS sem o controle antigo editável, consulta dos campos obsoletos e rejeição de alteração pelo JSON. Nenhuma gravação física nos testes automatizados.
- Na validação real do T-Deck, a leitura inicial levou 12,7 segundos e uma consulta posterior de rede levou 27,2 segundos, incluindo nova conexão. Ambas terminaram com a porta liberada e a leitura preservada. **Zero pacotes de gravação nesta validação**.
- A leitura real continuou indicando Wi-Fi e MQTT habilitados, proxy MQTT desativado e `gps_mode=ENABLED`. Esses valores são configurações, não uma nova prova de conexão com o broker ou de posição GPS obtida.
- O navegador exibiu a leitura real com a porta livre, manteve os controles de consulta disponíveis e mostrou `gps_mode` sem oferecer edição de `gps_enabled`. Navegar pelas páginas não enviou requisições de operação nem reabriu a serial.
- O diagnóstico anterior confirmou que encerrar a conexão serial permitia à Home voltar a atualizar os indicadores de Wi-Fi e MQTT; o proprietário confirmou a recuperação da tela. O novo fluxo aplica essa liberação após cada operação. Ainda pode haver uma pausa da tela enquanto a operação está em andamento.

Os registros abaixo descrevem a versão inicial, antes dessas melhorias.

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
