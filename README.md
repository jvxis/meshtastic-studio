# Mesh Studio

Web app local, em português, para consultar e editar configurações de um Meshtastic conectado por USB/serial. A interface tem painel do dispositivo, nós conhecidos, formulários gerados pelo protocolo, editor JSON e revisão de rascunhos.

**A inicialização padrão bloqueia gravações reais no servidor e na camada serial.** É possível editar e revisar rascunhos sem enviá-los ao rádio. O simulador permite testar uma aplicação completa sem conectar hardware.

![Painel do Mesh Studio com dados fictícios de demonstração](docs/images/demo-desktop.png)

## Instalação passo a passo no Windows

O app roda no computador ao qual o rádio está conectado. Não é necessário instalar Node.js, compilar o frontend ou baixar outro repositório.

### 1. Instale os pré-requisitos

- **Python 3.11 a 3.14**. Python 3.12 é uma opção compatível. No instalador do Python para Windows, habilite **Add python.exe to PATH**.
- **Git**, para baixar e atualizar o projeto.
- Um navegador atualizado. O dispositivo físico é opcional para explorar o simulador.

Depois da instalação, abra uma nova janela do **PowerShell** e confira:

```powershell
python --version
git --version
```

Se um comando não for encontrado, confira a instalação e o PATH antes de continuar. A primeira instalação precisa de internet para baixar as dependências Python.

### 2. Baixe o projeto

No PowerShell, entre na pasta em que deseja guardar o projeto e execute:

```powershell
git clone https://github.com/jvxis/meshtastic-studio.git
cd meshtastic-studio
```

### 3. Instale e inicie

```powershell
.\start.ps1
```

Na primeira execução, o script cria o ambiente isolado `.venv` e instala `requirements.txt`, incluindo a biblioteca Meshtastic do PyPI. Aguarde a mensagem do servidor com o endereço local e **deixe essa janela aberta**.

O modo padrão é somente leitura. Se o Windows bloquear a execução de scripts PowerShell, use a [instalação manual](#instalação-manual-no-windows) abaixo; ela não exige mudar a política de execução.

### 4. Abra o app

Acesse **http://127.0.0.1:8765** no navegador da mesma máquina.

Clique em **Explorar demonstração** para testar a interface com dados fictícios. No simulador, até as aplicações de configurações são fictícias.

### 5. Conecte seu rádio

1. Conecte o Meshtastic por USB usando um cabo com transmissão de dados.
2. Feche outros programas que estejam usando a porta serial, inclusive clientes web conectados por USB.
3. Se estiver no simulador, clique primeiro em **Desconectar**.
4. Na visão geral, clique em **Buscar portas**, selecione a porta COM correspondente ao seu equipamento e clique em **Conectar dispositivo**.
5. Aguarde a leitura. A conexão inicial pode levar cerca de 40 segundos, dependendo do dispositivo e do número de nós armazenados.

Ao concluir, o app **libera automaticamente a porta serial** e mantém uma cópia da leitura na memória. Você pode navegar e preparar rascunhos com a porta livre. Cada consulta ou aplicação abre uma conexão breve e a encerra ao terminar, inclusive em caso de falha.

Explore as configurações pelo menu lateral. Se uma seção não veio na conexão inicial, use **Consultar seção**. O firmware pode não implementar todas as seções descritas pelo protocolo.

### 6. Encerrar e usar novamente

A porta já é liberada depois de cada operação. Use **Encerrar sessão** para remover a leitura da memória do servidor e os rascunhos da página atual; no simulador, use **Desconectar**. No terminal do servidor, pressione **Ctrl+C** para encerrar o app.

Nas próximas utilizações, abra o PowerShell na pasta `meshtastic-studio` e execute novamente:

```powershell
.\start.ps1
```

## Instalação manual no Windows

Após baixar o projeto e entrar em sua pasta, execute estes comandos no PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:MESH_ALLOW_WRITES = "0"
.\.venv\Scripts\python.exe -m uvicorn server.app:app --host 127.0.0.1 --port 8765 --no-access-log
```

Não é necessário ativar o ambiente virtual. Abra **http://127.0.0.1:8765**, mantenha o terminal aberto e siga os passos de conexão descritos acima.

## Linux e macOS

A validação com rádio físico desta versão foi feita no Windows. Para executar o app em Linux ou macOS com Python 3.11 a 3.14:

```bash
git clone https://github.com/jvxis/meshtastic-studio.git
cd meshtastic-studio
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
MESH_ALLOW_WRITES=0 .venv/bin/python -m uvicorn server.app:app --host 127.0.0.1 --port 8765 --no-access-log
```

Abra **http://127.0.0.1:8765**. Os nomes das portas e suas permissões dependem do sistema operacional. No Linux, o suporte a `venv` pode precisar ser instalado pelo gerenciador de pacotes da distribuição. Não é necessário executar o app como administrador/root.

## Atualizar a instalação

Encerre o servidor e execute na pasta do projeto:

```powershell
git pull --ff-only
.\start.ps1 -Install
```

O parâmetro `-Install` reinstala/verifica as dependências. O script também verifica mudanças em `requirements.txt` e tenta novamente a instalação quando uma tentativa anterior não foi concluída.

Na instalação manual, depois de `git pull --ff-only`, execute novamente o comando `pip install -r requirements.txt` usando o Python da `.venv`.

## Solução de problemas

| Situação | Como resolver |
| --- | --- |
| `python` ou `git` não encontrado | Confira a instalação e o PATH; abra um novo terminal. |
| Script PowerShell bloqueado | Use a instalação manual acima. |
| Falha ao baixar dependências | Confira a conexão com a internet e tente `./start.ps1 -Install` novamente. |
| Navegador mostra conexão recusada | Confira se o terminal do servidor continua aberto e se você está acessando o endereço na mesma máquina. |
| Porta 8765 ocupada | Encerre a outra instância ou execute `./start.ps1 -Port 8766` e abra `http://127.0.0.1:8766`. |
| Nenhuma porta serial encontrada | Confira o cabo de dados, a conexão USB e se o sistema operacional reconhece o dispositivo. Depois use **Buscar portas**. |
| Porta serial ocupada | Desconecte outros clientes ou monitores seriais que estejam usando o equipamento. |
| Consulta sem resposta | Verifique a conexão e o suporte do firmware. O app repete uma consulta de leitura no máximo uma vez. |
| Aplicação de rascunho bloqueada | Esse é o comportamento padrão. Consulte a seção seguinte para habilitar gravações em uma sessão futura. |

## Cobertura

O catálogo desta versão possui **36 seções e 254 campos principais** no protocolo, além de campos de estruturas internas. Campos marcados como obsoletos pelo protocolo ficam em uma área recolhida, somente para consulta, e não aparecem como controles editáveis:

| Área | Configurações |
| --- | --- |
| Dispositivo | Nome, nome curto, identificação, papel, GPS/posição, energia, display e segurança |
| Rádio | Região, perfil, parâmetros LoRa, transmissão, slot e limite de saltos |
| Conexões | Wi-Fi/rede, Bluetooth, MQTT e módulo serial |
| Módulos | Todas as 16 seções descritas por `LocalModuleConfig`, incluindo telemetria, mensagens prontas, notificações, iluminação, sensores, status, gestão de tráfego e TAK |
| Canais | Oito índices, nome, papel, chave, uplink/downlink e opções de posição |
| Tela e extras | `DeviceUIConfig`, textos de mensagens prontas e toque RTTTL, consultados sob demanda |
| Consulta | Hardware, firmware, bateria, conectividade, nós conhecidos, origem MQTT e registro de atividades da sessão |

O catálogo é gerado dos descritores Protocol Buffers da biblioteca instalada. **Existir no protocolo não significa ser implementado pelo firmware conectado.** Seções não recebidas permanecem indisponíveis até uma consulta bem-sucedida. Os limites de tipos, enumerações, tamanhos de strings/bytes e quantidades conhecidos pelos descritores nanopb são validados; regras adicionais dependem do firmware.

Configurações acessíveis apenas pelo aplicativo de tela, recursos proprietários e comandos sem uma consulta correspondente não têm cobertura garantida. Esta versão não fornece atualização de firmware, factory reset, reinicialização, desligamento, envio de mensagens, modificação de nós remotos ou localização fixa enviada como pacote separado. Ela edita as configurações retornadas pela API local. A configuração de GPS/posição está incluída, mas isso não equivale a todas as ações administrativas de posição.

## Rascunhos e aplicação

1. Leia uma seção e edite os campos ou o JSON avançado.
2. Clique em **Revisar alterações**. O servidor valida o rascunho e retorna a comparação, sem gravar nada.
3. Em modo de leitura, o botão de aplicação permanece bloqueado. No simulador, digite a confirmação apresentada para testar a aplicação fictícia.
4. Para uma gravação real futura, encerre a sessão e inicie explicitamente:

   ```powershell
   .\start.ps1 -AllowWrites
   ```

5. Releia o dispositivo, prepare e revise o rascunho, digite `APLICAR !id-do-dispositivo` e clique em **Aplicar ao dispositivo**.

A interface não pode habilitar a gravação do processo em execução. O servidor exige uma revisão de uso único, com validade de cinco minutos, vinculada à sessão e ao nó. Antes do envio, reconecta na porta selecionada, confere a identidade do rádio, relê a seção e rejeita alterações concorrentes, inclusive as feitas no menu do aparelho. A releitura, o envio e a verificação usam a mesma conexão breve. Revisar um rascunho não abre a serial. Apenas o comando exato revisado recebe uma autorização temporária na serial. Depois do envio, uma nova consulta precisa confirmar os valores. Uma confirmação de entrega (ACK), isoladamente, não é tratada como sucesso de gravação.

Cada aplicação modifica **uma seção**. Não há transação atômica entre várias seções nem rollback automático. Uma mudança pode reiniciar o dispositivo ou interromper a conexão. Se a verificação falhar, a interface informa resultado não confirmado e exige nova leitura; não repete a gravação automaticamente.

## T-Deck: tela, GPS e conectividade

A [Meshtastic UI compartilha a Client API com os clientes externos](https://meshtastic.org/docs/configuration/device-uis/meshtasticui/#accessing-the-client-api). Uma conexão serial mantida aberta pode impedir que a Home atualize indicadores como Wi-Fi e MQTT. Por isso o Mesh Studio libera a porta ao terminar cada operação, sem depender de fechar a aba ou de um temporizador de inatividade. Durante uma consulta ou aplicação a tela ainda pode pausar por alguns instantes; uma nova conexão pode levar cerca de 40 segundos. Não há atualização contínua em segundo plano. O app mostra o horário da última consulta ao rádio; cada seção mantém sua última leitura, e a telemetria pode ser mais antiga.

- **GPS:** use `gps_mode`. O antigo `gps_enabled` é obsoleto e seu valor não indica o estado atual do GPS. GPS habilitado não garante coordenadas: é necessário obter uma posição dos satélites.
- **Campos obsoletos:** o formulário os apresenta somente em “Campos obsoletos · somente leitura”. Alterações pelo JSON/API são rejeitadas; omitir esses campos preserva o valor existente, inclusive em estruturas internas. A indicação vem do protocolo instalado, não de uma detecção completa das capacidades de cada firmware.
- **Wi-Fi e MQTT:** “Habilitado” descreve a configuração salva, não confirma conexão efetiva. O painel identifica esses valores como configuração da última leitura. `proxy_to_client_enabled` escolhe entre MQTT pela internet do aplicativo e MQTT pela rede do próprio rádio; não controla a ativação do Wi-Fi.
- **Heap e LVGL na Home:** mostram memória livre do firmware e da interface gráfica, respectivamente, em bytes e porcentagem livre no T-Deck. O ícone cinza indica que a atualização do monitor de memória está pausada. Um toque curto no ícone alterna a atualização; ele não desliga a memória nem a interface. Esse comportamento foi conferido no [código da interface usada pelo firmware 2.7.26](https://github.com/meshtastic/device-ui/blob/1c45ebc7433acb8ba3fe96a6f7deca9c43fa54cf/source/graphics/TFT/TFTView_320x240.cpp#L1517).

## Dados e acesso

- Servidor restrito a `127.0.0.1`; sem publicação externa, serviços de nuvem ou fontes carregadas da internet.
- Validação de Host/Origin e token por processo nas operações da API.
- Senhas, PSKs, PINs e chaves privadas retornam como `__MESH_SECRET_UNCHANGED__`. Esse marcador preserva o valor no servidor, inclusive em edições de outros campos da mesma seção.
- Rascunhos ficam na memória da página, sem `localStorage`. A leitura fica na memória do servidor, sem banco de dados.
- A exportação JSON contém segredos ocultos: é um relatório de consulta, **não um backup restaurável**.
- O contador “gravações na serial” contabiliza pacotes de modificação efetivamente enviados nesta sessão, somando suas conexões breves. Consultas, handshake, heartbeat e desconexão não são gravações de configuração.
- O registro de nós pode conter dados antigos e entradas MQTT. Não representa uma lista de rádios atualmente ao alcance direto.

## Desenvolvimento e testes

Backend: Python/FastAPI e Meshtastic. Frontend: HTML, CSS e JavaScript sem etapa de compilação. A interface chama apenas a API local.

Para desenvolver usando uma cópia local da biblioteca Meshtastic, instale-a explicitamente na `.venv` depois das dependências, por exemplo: `.\.venv\Scripts\python.exe -m pip install ../python`. Esse passo é opcional e não faz parte da instalação normal do app.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tests/browser_smoke.py
```

O teste de navegador usa o Google Chrome instalado e inicia um servidor próprio em porta temporária. **Todos os testes automatizados de edição/gravação usam um dispositivo simulado; não abrem portas COM.** Screenshots de verificação são gravadas em `artifacts/`, ignorada pelo Git.

Veja [VALIDATION.md](VALIDATION.md) para os resultados de testes e a verificação de leitura com o T-Deck.

| Arquivo | Responsabilidade |
| --- | --- |
| `server/schema.py` | Catálogo, validação, proteção de segredos e comparação |
| `server/device.py` | Serial protegida, consultas e comandos administrativos |
| `server/app.py` | API local, sessões, revisão e verificação de aplicação |
| `server/demo.py` | Dispositivo fictício para exploração e testes |
| `static/` | Interface responsiva em português |
| `tests/` | Testes de segurança, fluxo de aplicação e navegador |

O projeto usa a biblioteca Meshtastic, licenciada sob GPL-3.0-only. Este repositório é distribuído sob a mesma licença; veja `LICENSE`.
