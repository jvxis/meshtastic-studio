import { createChat } from './messages.js';
const $ = (selector, root = document) => root.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const clone = value => structuredClone(value);
const MASK = '__MESH_SECRET_UNCHANGED__';
const paths = {
  mesh:'M4 17V6l8 9 8-9v11M4 21h16', home:'m3 10 9-7 9 7M5 9v11h14V9M9 20v-7h6v7',
  radio:'M12 13v8M8 21h8M5 5a10 10 0 0 0 0 12M19 5a10 10 0 0 1 0 12M8 8a6 6 0 0 0 0 6M16 8a6 6 0 0 1 0 6M12 10v1',
  link:'m10 13 4-4M8 16l-2 2a4 4 0 0 1-5-5l5-5a4 4 0 0 1 5 0M16 8l2-2a4 4 0 0 1 5 5l-5 5a4 4 0 0 1-5 0',
  device:'M7 3h10v18H7zM10 17h4M9 6h6v7H9z', modules:'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
  channels:'M4 7h16M4 17h16M8 4v6M16 14v6', nodes:'M5 4h4v4H5zM16 15h4v4h-4zM3 16h4v4H3zM9 6h8v9M7 18h9M7 8v8',
  screen:'M3 4h18v13H3zM8 21h8M12 17v4', lock:'M6 11h12v10H6zM8 11V7a4 4 0 0 1 8 0v4M12 15v2',
  arrow:'M5 12h14m-5-5 5 5-5 5', refresh:'M20 7v5h-5M4 17v-5h5M6 7a7 7 0 0 1 12-1l2 3M4 15l2 3a7 7 0 0 0 12-1',
  battery:'M2 6h17v12H2zM22 10v4M5 9h10v6H5z', clock:'M12 8v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0',
  check:'m5 12 4 4L19 6', shield:'M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6zM8 12l3 3 5-6',
  usb:'M12 21V3m-3 3 3-3 3 3M12 16l-6-4V8M12 12l6-4V5M4 6h4v2H4zM16 3h4v2h-4z',
  wifi:'M3 8a15 15 0 0 1 18 0M6 12a10 10 0 0 1 12 0M9 16a5 5 0 0 1 6 0M12 20h.01',
  bluetooth:'M7 7l10 10-5 4V3l5 4L7 17', download:'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5',
  search:'M10 3a7 7 0 1 1 0 14 7 7 0 0 1 0-14m5 12 6 6', close:'m6 6 12 12M6 18 18 6',
  menu:'M4 6h16M4 12h16M4 18h16', code:'m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18',
  file:'M5 3h9l5 5v13H5zM14 3v6h5M9 13h6M9 17h6', warning:'m12 3 10 18H2zM12 9v5M12 17h.01',
  cloud:'M6 18a5 5 0 1 1 0-10 6 6 0 0 1 12-1 5 5 0 0 1 0 11z', plug:'M8 3v5M16 3v5M6 8h12v3a6 6 0 0 1-12 0zM12 17v4',
  settings:'M4 6h16M4 12h16M4 18h16M8 4v4M16 10v4M10 16v4', eye:'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
};
const icon = name => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name] || paths.settings}"/></svg>`;
const titles = {messages:'Mensagens',overview:'Visão geral',radio:'Rádio LoRa',connections:'Conexões',device:'Dispositivo',modules:'Módulos',channels:'Canais',nodes:'Nós da rede',screen:'Interface e extras',drafts:'Rascunhos'};
const navGroups = [
  ['CONTROLE', [['overview','home'],['messages','file'],['radio','radio'],['connections','link'],['device','device'],['modules','modules']]],
  ['REDE & PERSONALIZAÇÃO', [['channels','channels'],['nodes','nodes'],['screen','screen'],['drafts','file']]],
];
const labels = {long_name:'Nome do dispositivo',short_name:'Nome curto',is_licensed:'Modo radioamador',is_unmessagable:'Ocultar opção de mensagem',
  role:'Papel na rede',use_preset:'Usar perfil de rádio',modem_preset:'Perfil do modem',region:'Região',hop_limit:'Limite de saltos',
  tx_enabled:'Transmissão habilitada',tx_power:'Potência configurada (dBm)',channel_num:'Slot de frequência',bandwidth:'Largura de banda',spread_factor:'Fator de espalhamento',coding_rate:'Taxa de codificação',
  sx126x_rx_boosted_gain:'Ganho de recepção reforçado',frequency_offset:'Deslocamento de frequência',override_frequency:'Frequência personalizada',
  wifi_enabled:'Wi-Fi habilitado',wifi_ssid:'Nome da rede Wi-Fi',wifi_psk:'Senha do Wi-Fi',eth_enabled:'Ethernet habilitada',address_mode:'Modo de endereço',ntp_server:'Servidor NTP',
  enabled:'Habilitado',mode:'Modo',fixed_pin:'PIN fixo',address:'Endereço do servidor',username:'Usuário',password:'Senha',encryption_enabled:'Criptografia dos pacotes',json_enabled:'Formato JSON',tls_enabled:'Conexão TLS',
  proxy_to_client_enabled:'Proxy pelo aplicativo',root:'Tópico raiz',map_reporting_enabled:'Publicação no mapa',name:'Nome',psk:'Chave do canal',uplink_enabled:'Enviar ao MQTT',downlink_enabled:'Receber do MQTT',
  settings:'Configurações',module_settings:'Opções do canal',position_precision:'Precisão da posição',is_muted:'Silenciar canal',index:'Índice',
  gps_enabled:'GPS habilitado',gps_mode:'Modo do GPS',position_broadcast_secs:'Intervalo de posição (s)',fixed_position:'Posição fixa',gps_update_interval:'Intervalo de GPS (s)',position_flags:'Informações de posição (bitmask)',
  device_update_interval:'Intervalo de telemetria (s)',environment_measurement_enabled:'Sensores ambientais',environment_update_interval:'Intervalo ambiental (s)',
  screen_on_secs:'Tempo de tela ligada (s)',screen_brightness:'Brilho da tela',screen_timeout:'Tempo limite da tela',screen_lock:'Bloqueio de tela',settings_lock:'Bloqueio de configurações',pin_code:'Código PIN',
  theme:'Tema',language:'Idioma',text:'Conteúdo',node_info_broadcast_secs:'Intervalo de identificação (s)',tzdef:'Fuso horário',rebroadcast_mode:'Modo de retransmissão',
  private_key:'Chave privada',public_key:'Chave pública',admin_key:'Chaves de administradores',serial_enabled:'Serial habilitada',
};
const hints = {gps_mode:'Controla o GPS. ENABLED permite buscar satélites; coordenadas só aparecem após obter uma posição válida.',
  proxy_to_client_enabled:'Ativo: MQTT usa a internet do aplicativo no celular. Desativado: o rádio usa sua própria conexão de rede. Não controla o Wi-Fi.',
  tx_power:'Valor configurado. A potência efetiva depende do hardware e do firmware.',
  channel_num:'Slot de frequência do rádio, diferente do índice de um canal de mensagens.',
  region:'A região determina os parâmetros usados pelo firmware.',
  use_preset:'Quando ativo, o perfil determina os parâmetros de modulação.',
  position_flags:'Campo de bits do protocolo. Use o valor numérico desejado.',
  text:'Mensagens prontas: separe as opções com |. Toque: use uma sequência RTTTL.',
  public_key:'Formato Base64. A chave pública não é uma senha.',
};
let connectionType = 'serial', connectionHost = '', connectionPort = '4403', selectedPort = '';
let csrf = '', schema = [], state = {session_active:false,connected:false,sections:{},nodes:[],events:[]}, ports = [], page = 'overview', selected = '', drafts = {}, busy = false, applying = false, jsonMode = false, fieldSearch = '', nodeSearch = '', errors = {}, preview = null, toastTimer;
const sectionValue = key => state.sections[key]?.values || {};
const valueAt = (obj, path) => path.split('.').reduce((v,k) => v?.[k], obj);
function setAt(obj, path, value) { const keys = path.split('.'); let dest = obj; keys.slice(0,-1).forEach(k => { if (!dest[k] || typeof dest[k] !== 'object') dest[k] = {}; dest = dest[k]; }); dest[keys.at(-1)] = value; }
function notify(message, error=false) { const el = $('#toast'); el.textContent = message; el.className = `visible${error?' error':''}`; clearTimeout(toastTimer); toastTimer=setTimeout(()=>el.className='', error?11000:5000); }
async function api(path, body) { const response=await fetch(`/api/${path}`, {method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json','X-Mesh-Token':csrf},body:body===undefined?undefined:JSON.stringify(body)}); const result=await response.json(); if(!response.ok){const error=new Error(typeof result.detail==='string'?result.detail:'Os dados enviados não são válidos.');error.status=response.status;throw error;} return result; }
async function task(action, message) { if(busy)return; busy=true; render(); try { await action(); if(message)notify(message); } catch(e){ notify(e.message,true); } finally {busy=false;render();} }
function transportLabel(){return state.device?.transport==='tcp'?'Rede / TCP':'USB / serial';}
function portOptions() { return ports.map(p=>`<option value="${esc(p.port)}" ${(selectedPort?p.port===selectedPort:p.usb)?'selected':''}>${esc(p.port)} · ${esc(p.description)}</option>`).join('') || '<option value="">Nenhuma porta encontrada</option>'; }
function button(action,label,ic='arrow',kind='',extra=''){return `<button class="btn ${kind}" data-action="${action}" ${busy?'disabled':''} ${extra}>${icon(ic)}${label}</button>`;}
function writesAllowed(){return state.demo||state.server_writes_enabled;}
function modePill(){return state.demo?'<span class="pill amber">Demonstração</span>':`<span class="pill ${writesAllowed()?'amber':'green'}">${icon('lock')}${writesAllowed()?'Gravação habilitada':'Somente leitura'}</span>`;}
function deck(){return `<div class="device-picture" aria-hidden="true"><div class="deck"><div class="deck-screen">${icon('radio')} MESHTASTIC<div class="screen-line"></div><div class="screen-line short"></div></div><div class="keyboard">${'<i></i>'.repeat(28)}</div></div></div>`;}
function go(next, key=''){page=next;selected=key;fieldSearch='';jsonMode=false;render();window.scrollTo({top:0});}
function dirty(key){return drafts[key] && (errors[key] || JSON.stringify(drafts[key].values)!==JSON.stringify(drafts[key].original));}
function dirtyKeys(){return Object.keys(drafts).filter(dirty);}
function heading(title,description,actions=''){return `<div class="page-heading"><div><h1>${esc(title)}</h1><p>${esc(description)}</p></div>${actions?`<div class="actions">${actions}</div>`:''}</div>`;}
function snapshotNotice(){
  if(state.active_phase==='active')return `<div class="status-strip">${icon('radio')}<span><b>Escuta ativa.</b> A conexão fica aberta para receber e enviar pelo desktop. Consultas e alterações usam a mesma conexão. Use Desconectar em Mensagens para liberar o rádio.</span></div>`;
  if(['starting','stopping'].includes(state.active_phase))return '<div class="status-strip"><b>Escuta ativa em transição.</b> Aguarde a conexão ou o encerramento da comunicação atual.</div>';
if(state.session_active&&!state.demo&&state.connection_mode==='desktop')return '<div class="status-strip"><b>Rádio desconectado.</b> A leitura está salva. Abra Mensagens e use Conectar ao rádio para retomar.</div>';
if(state.session_active&&!state.demo&&(busy||applying))return '<div class="status-strip"><b>Operação em andamento.</b> A conexão será encerrada ao concluir. Durante a recepção, use Parar recepção para encerrar antes.</div>';return state.session_active&&!state.demo?`<div class="status-strip">${icon('usb')}<span><b>Conexão encerrada automaticamente.</b> Você está vendo a última leitura${state.observed_at?' de '+esc(new Date(state.observed_at).toLocaleString('pt-BR')):''}. Consultas e aplicações reconectam por alguns instantes; durante esse período a tela do rádio pode pausar as atualizações.</span></div>`:'';}
function statusStrip(){return snapshotNotice()+ `<div class="status-strip ${state.demo?'demo':''}">${icon(state.demo?'code':'shield')}<span>${state.demo?'<b>Ambiente de demonstração.</b> Todos os dados são fictícios; as alterações são simuladas.':writesAllowed()?'<b>Gravação habilitada.</b> Cada seção exige revisão e confirmação antes do envio.':'<b>Você está em modo de leitura.</b> Explore e prepare rascunhos. A gravação no dispositivo está bloqueada.'}</span><span class="end">${state.device?`${state.device.write_packets} gravações de configuração`:'ACESSO LOCAL'}</span></div>`;}
function render(){
  const current=state.device;
  $('#app').innerHTML=`${busy?'<div class="busy-overlay" role="progressbar" aria-label="Operação em andamento"></div>':''}<div class="layout"><aside class="sidebar"><div class="brand"><span class="logo">${icon('mesh')}</span>Mesh Studio</div><div class="brand-sub">LOCAL CONTROL</div>${navGroups.map(([label,items])=>`<div class="nav-label">${label}</div><nav class="nav" aria-label="${label}">${items.map(([id,ic])=>`<button data-page="${id}" class="${page===id?'active':''}" ${page===id?'aria-current="page"':''}>${icon(ic)}${titles[id]}${id==='drafts'&&dirtyKeys().length?`<span class="badge-number">${dirtyKeys().length}</span>`:''}</button>`).join('')}</nav>`).join('')}<div class="sidebar-bottom"><div class="device-mini"><span class="eyebrow"><i class="dot ${state.connected?'':'off'}"></i>${state.demo?'SIMULADOR':state.session_active?(state.active_phase==='active'?'ESCUTA ATIVA':busy?'OPERAÇÃO EM ANDAMENTO':'DESCONECTADO · LEITURA SALVA'):'SEM SESSÃO'}</span><div class="mini-title">${esc(current?.name || 'Seu próximo ponto na rede')}</div><span class="mono tiny muted">${esc(current?`${current.id} · ${current.port}`:'USB / serial ou Rede / TCP')}</span></div><div class="footer-note">${icon('lock')}Dados locais. Sem nuvem.</div></div></aside><main class="main"><header class="topbar"><div class="breadcrumb"><button class="btn ghost mobile-menu" data-action="menu" aria-label="Abrir menu">${icon('menu')}</button><span>Workspace</span><span>/</span><b>${titles[page]}</b></div><div class="top-status"><span class="local-label muted"><i class="dot"></i>localhost</span>${modePill()}</div></header><div class="content">${page==='overview'?overview():page==='messages'?heading('Mensagens','Converse nos canais e diretamente com os nós da rede.')+chat.render(state,busy):page==='nodes'?nodesPage():page==='channels'&&!selected?channelsPage():page==='drafts'?draftsPage():settingsPage()}<footer class="page-foot"><span>Mesh Studio <span class="muted">/</span> Feito para explorar sua rede.</span><span>${state.demo?'DADOS DE DEMONSTRAÇÃO':state.session_active?`Última leitura · ${esc(current.port)} · ${state.active_phase==='active'?'escuta ativa':busy?'operação em andamento':'conexão encerrada'}`:'Conexão direta com o seu Meshtastic'}</span></footer></div></main></div>`;
  bind();
}
function overview(){
  const d=state.device, metrics=d?.metrics||{}, lora=sectionValue('config.lora');
  const actions=d?(state.session_active?button('refresh','Atualizar leitura','refresh','ghost'):'')+button('disconnect',state.demo?'Desconectar':'Encerrar sessão','plug','ghost'):button('ports','Buscar portas','refresh','ghost');
  const minutes=metrics.uptimeSeconds===undefined?null:Math.floor(metrics.uptimeSeconds/60);
  const uptime=minutes===null?'—':minutes>=60?`${Math.floor(minutes/60)}<small> h </small>${minutes%60}<small> min</small>`:`${minutes}<small> min</small>`;
  const battery=metrics.batteryLevel===undefined?'—':metrics.batteryLevel>100?'USB':`${metrics.batteryLevel}<small> %</small>`;
  return heading('Sua rede, sob controle.','Conheça seu dispositivo. Explore cada ajuste. Mantenha tudo por perto.',actions)+statusStrip()+(!state.session_active?`<section class="card empty-connect"><div><span class="eyebrow">COMECE PELA CONEXÃO</span><h2 style="margin-top:14px">Um rádio. Todas as possibilidades.</h2><p>Selecione a conexão e conecte seu rádio para receber mensagens, enviar e ajustar as configurações.</p><div class="connect-fields"><label>Tipo de conexão<select id="connection-type" ${busy?'disabled':''}><option value="serial" ${connectionType==='serial'?'selected':''}>USB / Serial</option><option value="tcp" ${connectionType==='tcp'?'selected':''}>Rede / TCP</option></select></label>${connectionType==='tcp'?`<label>IP ou nome do rádio<input id="tcp-host" value="${esc(connectionHost)}" placeholder="192.168.1.50" maxlength="253" autocomplete="off" spellcheck="false" ${busy?'disabled':''}></label><label>Porta TCP<input id="tcp-port" type="number" min="1" max="65535" step="1" value="${esc(connectionPort)}" ${busy?'disabled':''}></label>`:`<label>Porta serial<select id="port-select" class="port-select" ${busy?'disabled':''}>${portOptions()}</select></label>`}</div>${connectionType==='tcp'?'<p class="field-hint">Use o endereço do rádio na rede, sem http://. A porta padrão é 4403. Wi-Fi deve estar configurado previamente. Alguns firmwares, incluindo o T-Deck 2.7.26 com MUI, desativam o servidor TCP nesse modo de tela.</p>':''}<div class="actions">${button('connect',busy?'Conectando…':'Conectar dispositivo','plug','primary')}${button('demo','Explorar demonstração','arrow','ghost')}</div></div>${deck()}</section>`:'')+`<section class="cards" aria-label="Indicadores"><article class="card"><div class="metric-head">Bateria ${icon('battery')}</div><div class="metric-value">${battery}</div><div class="metric-foot">${metrics.voltage!==undefined?`${metrics.voltage.toFixed(2)} V <span>· leitura do dispositivo</span>`:'Aguardando telemetria'}</div><div class="battery-track"><i style="width:${Math.max(0,Math.min(100,metrics.batteryLevel||0))}%"></i></div></article><article class="card"><div class="metric-head">Nós conhecidos ${icon('nodes')}</div><div class="metric-value">${d?state.nodes.length:'—'}</div><div class="metric-foot">Registros locais, incluindo MQTT</div></article><article class="card"><div class="metric-head">Perfil do rádio ${icon('radio')}</div><div class="metric-value" style="font-size:24px">${esc(lora.modem_preset?.replaceAll('_',' ')||'—')}</div><div class="metric-foot">${lora.region?`${esc(lora.region)} <span>· slot ${esc(lora.channel_num)}</span>`:'Aguardando configuração'}</div></article><article class="card"><div class="metric-head">Tempo ligado ${icon('clock')}</div><div class="metric-value">${uptime}</div><div class="metric-foot">Última telemetria recebida</div></article></section>`+(d?`<div class="dashboard-grid"><section class="card"><div class="card-heading"><h2>Seu dispositivo</h2><span class="pill green"><i class="dot"></i>${state.demo?'Simulado':state.connected?'Conexão aberta':'Conexão encerrada'}</span></div><div class="device-hero">${deck()}<div class="device-info"><span class="eyebrow">${esc(d.metadata.hw_model?.replaceAll('_',' ')||'MESHTASTIC')}</span><div class="device-name">${esc(d.name)}</div><div class="mono">${esc(d.id)}</div><div class="actions"><span class="pill">${esc(d.metadata.role||'CLIENT')}</span><span class="pill">${esc(d.short_name)}</span></div></div></div><dl class="kv-grid"><div><dt>Firmware</dt><dd class="mono">${esc(d.metadata.firmware_version||'—')}</dd></div><div><dt>Conexão local</dt><dd>${esc(d.port)} · ${state.demo?'Simulação':transportLabel()}</dd></div><div><dt>Limite de saltos</dt><dd>${esc(lora.hop_limit??'—')} hops</dd></div><div><dt>Posição GPS</dt><dd>${d.position?.latitude!==undefined?`${esc(d.position.latitude)}, ${esc(d.position.longitude)}`:'Sem coordenadas na leitura'}</dd></div></dl></section><section class="card"><div class="card-heading"><h2>Configuração de conectividade</h2>${icon('link')}</div>${connection(d.transport==='tcp'?'wifi':'usb',transportLabel(),d.port,state.connected,state.demo?'Simulado':state.connected?'Em uso':'Conexão encerrada')}${connection('wifi','Wi-Fi',sectionValue('config.network').wifi_enabled?sectionValue('config.network').wifi_ssid:'Conexão sem fio',sectionValue('config.network').wifi_enabled)}${connection('bluetooth','Bluetooth',sectionValue('config.bluetooth').mode?.replaceAll('_',' ')||'Bluetooth Low Energy',sectionValue('config.bluetooth').enabled)}${connection('cloud','MQTT',sectionValue('module.mqtt').address||'Ponte com a internet',sectionValue('module.mqtt').enabled)}<p class="field-hint">Habilitado na configuração não confirma conexão com a rede ou com o broker. Estes são os valores da última leitura.</p><button class="link-row" data-page="connections">Explorar conexões ${icon('arrow')}</button></section></div>`:'')+`<div class="section-title"><h2>Explore seu Meshtastic</h2><p>Do essencial aos detalhes</p></div><section class="shortcuts">${shortcut('radio','radio','Configurações do rádio','Perfil, região e transmissão')}${shortcut('channels','channels','Seus canais','Comunicação e compartilhamento')}${shortcut('modules','modules','Módulos e sensores','Telemetria, mensagens e mais')}</section><div class="section-title"><h2>Atividade desta sessão</h2><p>Últimos eventos</p></div><section class="card events">${events()}</section>`;
}
function connection(ic,title,sub,enabled,status){return `<div class="connection-row"><div class="icon-box">${icon(ic)}</div><div style="min-width:0"><div class="row-title">${title}</div><div class="tiny muted" style="overflow-wrap:anywhere">${esc(sub||'—')}</div></div><span class="pill ${enabled?'green':''}">${status||(enabled?'Habilitado':'Desabilitado')}</span></div>`;}
function shortcut(target,ic,title,desc){return `<button class="card shortcut" data-page="${target}"><div class="icon-box">${icon(ic)}</div><div><h3>${title}</h3><p>${desc}</p></div>${icon('arrow').replace('<svg','<svg class="arrow"')}</button>`;}
function events(){return state.events.length?state.events.slice(0,5).map(e=>`<div class="event">${icon(e.level==='warning'?'warning':'check')}<div>${esc(e.action)}<p>${esc(e.detail)}</p></div><time>${new Date(e.time).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})}</time></div>`).join(''):'<div class="event muted">Nenhuma operação nesta sessão. Conecte um dispositivo para começar.</div>';}
function categoryKeys(){if(page==='radio')return ['config.lora'];if(page==='connections')return ['config.network','config.bluetooth','module.mqtt','module.serial'];if(page==='device')return ['owner','config.device','config.position','config.power','config.display','config.security'];if(page==='modules')return schema.filter(s=>s.group==='module').map(s=>s.id);if(page==='screen')return ['ui','canned_text','ringtone'];if(page==='channels')return schema.filter(s=>s.group==='channel').map(s=>s.id);return [];}
function settingsPage(){
  const keys=categoryKeys();if(!keys.includes(selected))selected=keys[0];const def=schema.find(s=>s.id===selected);if(!def)return '';
  const entry=state.sections[selected], draft=drafts[selected], data=draft?.values||entry?.values||{};
  return (page==='screen'?'<section class="card"><h2>Heap e LVGL na Home do T-Deck</h2><p>Heap mostra a memória livre do firmware; LVGL mostra a memória livre da interface gráfica. Os números são bytes livres e porcentagem livre. O ícone cinza indica que a atualização desse monitor está pausada. Um toque curto no ícone de memória alterna a atualização; não liga ou desliga a memória nem a interface.</p></section>':'')+heading(titles[page],page==='screen'?'Configurações adicionais são consultadas sob demanda, conforme suporte do firmware.':'Edite um rascunho e compare cada mudança antes de aplicar.')+statusStrip()+`<div class="section-tabs" role="group" aria-label="Seções">${keys.map(k=>{const s=schema.find(s=>s.id===k);return `<button class="section-tab ${k===selected?'selected':''}" data-section="${k}">${esc(s.name)}${dirty(k)?'<i class="draft-dot"></i>':''}<span class="count">${s.fields.length}</span></button>`;}).join('')}</div><div class="editor-toolbar"><label class="search">${icon('search')}<input id="field-search" placeholder="Buscar um parâmetro…" aria-label="Buscar parâmetro" value="${esc(fieldSearch)}"></label><div class="actions">${button('json',jsonMode?'Formulário':'JSON avançado',jsonMode?'settings':'code','ghost')}${button('read-section','Reler seção','refresh','ghost',state.session_active?'':'disabled')}</div></div><section class="card editor-panel"><div class="editor-head"><div><h2>${esc(def.name)}</h2><p>${esc(def.id)} · ${def.fields.length} campos principais no protocolo</p></div><span class="pill ${entry?.available?'green':''}">${entry?.available?'Leitura disponível':'Ainda não lido'}</span></div>${entry?.available?(jsonMode?`<div class="editor-json"><p class="field-hint" style="margin-bottom:12px">Edite somente os valores desejados. O marcador ${esc(MASK)} preserva o segredo atual. Excluir um campo editável redefine seu valor padrão. Campos obsoletos são preservados; alterações neles são rejeitadas.</p><textarea id="json-editor" aria-label="Configuração JSON" spellcheck="false">${esc(draft?.jsonText??JSON.stringify(data,null,2))}</textarea></div>`:`<div class="form-grid">${renderFields(def.fields,data)}</div>${legacyFields(def.fields,data)}`):`<div class="empty">${icon('device')}<h3>${state.session_active?'Consulte esta configuração':'Conecte seu dispositivo'}</h3><p>${state.session_active?'Esta seção não veio na leitura inicial. Faça uma consulta local.<br>Se o firmware não a suportar, a edição permanecerá indisponível.':'Abra a visão geral para conectar por USB ou TCP, ou iniciar a demonstração.'}</p>${state.session_active?button('read-section','Consultar seção','download','primary'):button('overview','Ir para a conexão','plug','primary')}</div>`}<p class="form-error ${errors[selected]?'':'hidden'}" id="form-error" role="alert">${esc(errors[selected]||'')}</p></section><div id="draft-slot">${draftBar()}</div><p class="export-note">Os campos são gerados a partir do protocolo instalado. A disponibilidade e os limites efetivos dependem do firmware do dispositivo. Segredos existentes ficam protegidos.</p>`;
}
function legacyFields(fields,data,prefix=''){
  const rows=[];
  for(const f of fields){
    const path=prefix?`${prefix}.${f.name}`:f.name;
    if(f.deprecated)rows.push(`<div class="field"><span class="field-code">${esc(path)}</span><span>${esc(f.secret?'[protegido]':JSON.stringify(valueAt(data,path)??null))}</span><p class="field-hint">${esc(f.hint)}</p></div>`);
    else if(f.kind==='object'&&!f.repeated){const nested=legacyFields(f.fields,data,path);if(nested)rows.push(nested);}
  }
  return rows.length?`<details class="legacy-fields"><summary>Campos obsoletos · somente leitura</summary><p class="field-hint">Mantidos para compatibilidade. Não use esses valores como indicadores do estado atual.</p>${rows.join('')}</details>`:'';
}
function renderFields(fields,data,prefix=''){
  return fields.filter(f=>!f.deprecated).map(f=>{
    const path=prefix?`${prefix}.${f.name}`:f.name, value=valueAt(data,path), label=labels[f.name]||f.name.replaceAll('_',' ').replace(/^./,x=>x.toUpperCase());
    if(fieldSearch && !(path+' '+label).toLowerCase().includes(fieldSearch.toLowerCase()) && f.kind!=='object')return '';
    if(f.kind==='object'&&!f.repeated){const children=renderFields(f.fields,data,path);return children?`<fieldset><legend>${esc(label)} <span class="field-code">${esc(path)}</span></legend>${children}</fieldset>`:'';}
    const attr=`data-field="${esc(path)}" data-kind="${f.kind}" data-bits="${f.bits||0}" ${f.readonly?'disabled':''}`;
    const title=`<span class="field-label">${esc(label)}${f.secret?icon('lock'):''}${f.readonly?'<span class="muted tiny">leitura</span>':''}</span><span class="field-code">${esc(path)}</span>`;
    if(f.kind==='bool'&&!f.repeated)return `<label class="switch-row"><span>${title}</span><input type="checkbox" class="switch" ${attr} ${value===true?'checked':''} aria-label="${esc(label)}"></label>`;
    let control;
    if(f.repeated)control=`<textarea rows="3" data-repeated="true" ${attr} aria-label="${esc(label)}" spellcheck="false">${esc(drafts[selected]?.rawFields?.[path]??JSON.stringify(value??[],null,2))}</textarea><span class="field-hint">Lista JSON${f.kind==='bytes'?' de valores Base64':''}${f.max_count?` · máximo de ${f.max_count} itens`:''}.</span>`;
    else if(f.kind==='enum')control=`<select ${attr} aria-label="${esc(label)}">${f.options.includes(value)||value===undefined?'':`<option selected value="${esc(value)}">${esc(value)} · firmware</option>`}${f.options.map(option=>`<option ${(value??f.default)===option?'selected':''}>${esc(option)}</option>`).join('')}</select>`;
    else if(f.secret)control=`<div class="secret-control"><input type="password" ${attr} data-secret="true" value="${value===MASK?'':esc(value??'')}" placeholder="${value===MASK?'Configurado · digite para substituir':'Não configurado'}" autocomplete="new-password" aria-label="${esc(label)}"><button class="btn ghost" data-clear="${esc(path)}" data-clear-kind="${f.kind}" title="Limpar este valor no rascunho" aria-label="Limpar ${esc(label)}">${icon('close')}</button></div><span class="field-hint">${value===MASK?'O valor existente será preservado enquanto você não o substituir.':'Novo valor apenas no rascunho.'}</span>`;
    else if(f.name==='text')control=`<textarea rows="5" ${attr} aria-label="${esc(label)}">${esc(value??'')}</textarea>`;
    else control=`<input type="${['integer','number'].includes(f.kind)&&f.bits!==64?'number':'text'}" ${attr} ${f.kind==='number'?'step="any"':''} value="${esc(value??f.default??'')}" aria-label="${esc(label)}" ${f.kind==='bytes'?'spellcheck="false"':''}>`;
    return `<label class="field ${f.repeated?'repeated':''}">${title}${control}${hints[f.name]?`<span class="field-hint">${hints[f.name]}</span>`:f.kind==='bytes'?'<span class="field-hint">Bytes codificados em Base64.</span>':''}</label>`;
  }).join('')||(!prefix?'<p class="muted">Nenhum parâmetro encontrado.</p>':'');
}
function draftBar(){const count=dirtyKeys().length;return dirty(selected)?`<div class="draft-bar"><span class="draft-dot"></span><div><h3>Rascunho de ${esc(schema.find(s=>s.id===selected)?.name)}</h3><p>As alterações ainda não foram enviadas ao dispositivo.</p></div><div class="actions">${button('discard','Descartar','close','ghost')}${button('review','Revisar alterações','eye','primary',errors[selected]?'disabled':'')}</div></div>`:count?`<p class="export-note">${count} seção(ões) com rascunho. Acesse Rascunhos para revisar.</p>`:'';}
function ensureDraft(){if(!drafts[selected])drafts[selected]={values:clone(sectionValue(selected)),original:clone(sectionValue(selected)),revision:state.sections[selected].revision,rawFields:{},fieldErrors:{}};return drafts[selected];}
function updateDraftUI(){const slot=$('#draft-slot');if(slot){slot.innerHTML=draftBar();bindActions(slot);}const error=$('#form-error');if(error){error.textContent=errors[selected]||'';error.classList.toggle('hidden',!errors[selected]);}}
function nodesPage(){const nodes=state.nodes.filter(n=>(n.name+' '+n.id+' '+n.hardware).toLowerCase().includes(nodeSearch.toLowerCase()));return heading('Os pontos da sua rede.',`${state.nodes.length} registros conhecidos. Um registro não confirma que o nó está online ou ao alcance direto.`,button('sync-state','Atualizar lista','refresh','ghost'))+statusStrip()+`<div class="editor-toolbar"><label class="search">${icon('search')}<input id="node-search" placeholder="Buscar nome, ID ou hardware…" aria-label="Buscar nós" value="${esc(nodeSearch)}"></label><span class="muted small">${nodes.length} resultado(s)</span></div><section class="card editor-panel table-wrap"><table class="node-table"><thead><tr><th>DISPOSITIVO</th><th>HARDWARE</th><th>ORIGEM REGISTRADA</th><th>SNR</th><th>SALTOS</th><th>ÚLTIMO REGISTRO</th></tr></thead><tbody>${nodes.map(n=>`<tr><td><div class="node-name">${esc(n.name)} ${n.local?'<span class="pill green">Você</span>':''}</div><div class="node-id mono">${esc(n.id)}</div></td><td class="tiny">${esc(n.hardware)}</td><td><span class="pill ${n.local?'green':''}">${n.local?'Local':n.via_mqtt?'MQTT':'Sem marca MQTT'}</span></td><td>${n.snr===null||n.snr===undefined?'—':`${Number(n.snr).toFixed(1)} dB`}</td><td>${esc(n.hops??'—')}</td><td class="small muted">${n.last_heard?esc(new Date(n.last_heard*1000).toLocaleString('pt-BR')):'—'}</td></tr>`).join('')||'<tr><td colspan="6" class="empty">Nenhum nó para mostrar.</td></tr>'}</tbody></table></section>`;}
function channelsPage(){return heading('Conversas no mesmo canal.','Veja os canais disponíveis e prepare mudanças de nome, chave e integração MQTT.')+statusStrip()+`<section class="channels-grid">${schema.filter(s=>s.group==='channel').map(s=>{const e=state.sections[s.id],v=e?.values,active=v&&v.role!=='DISABLED';return `<button class="card channel-card ${active?'':'disabled'}" data-section="${s.id}"><div class="card-heading"><span class="channel-index mono">CH / ${s.id.split('.')[1].padStart(2,'0')}</span><span class="pill ${active?'green':''}">${!v?'Não lido':v.role==='PRIMARY'?'Principal':v.role==='SECONDARY'?'Secundário':'Desabilitado'}</span></div><h2>${esc(v?.settings?.name||(active?'Canal padrão':'Canal disponível'))}</h2><p class="tiny muted">${v?.settings?.psk===MASK?'Chave protegida':active?'Sem chave configurada':'Configure após consultar'}</p><div class="channel-footer"><span>${dirty(s.id)?'Rascunho pendente':active?`MQTT ↑ ${v.settings?.uplink_enabled?'sim':'não'} · ↓ ${v.settings?.downlink_enabled?'sim':'não'}`:'Explorar configuração'}</span>${icon('arrow')}</div></button>`;}).join('')}</section>`;}
function draftsPage(){const keys=dirtyKeys();return heading('Uma mudança de cada vez.','Revise e aplique cada seção individualmente. Rascunhos ficam apenas na memória desta página.',button('export','Exportar leitura','download','ghost',state.session_active?'':'disabled'))+statusStrip()+`<section class="card">${keys.length?keys.map(k=>`<div class="connection-row"><div class="icon-box">${icon('file')}</div><div><h3>${esc(schema.find(s=>s.id===k)?.name)}</h3><p class="tiny muted" style="margin-top:5px">${esc(k)} · ${errors[k]?'JSON inválido':'Não enviado'}</p></div><button class="btn ghost" style="margin-left:auto" data-open-draft="${k}">Abrir ${icon('arrow')}</button></div>`).join(''):`<div class="empty">${icon('check')}<h3>Nenhum rascunho pendente</h3><p>Ao editar um parâmetro, a alteração aparecerá aqui para revisão.</p></div>`}</section><p class="export-note">A exportação contém uma leitura com senhas e chaves privadas ocultas. É um relatório de consulta, não um backup completo para restaurar o dispositivo.</p>`;}
function openDraft(key){const target=key.startsWith('channel.')?'channels':key==='config.lora'?'radio':['config.network','config.bluetooth','module.mqtt','module.serial'].includes(key)?'connections':key.startsWith('module.')?'modules':['ui','ringtone','canned_text'].includes(key)?'screen':'device';go(target,key);}
function bindActions(root=document){root.querySelectorAll('[data-action]').forEach(el=>el.onclick=()=>actions[el.dataset.action]?.());}
function bind(){
  if($('#connection-type'))$('#connection-type').onchange=e=>{connectionType=e.target.value;render();};
  if($('#tcp-host'))$('#tcp-host').oninput=e=>{connectionHost=e.target.value;};
  if($('#tcp-port'))$('#tcp-port').oninput=e=>{connectionPort=e.target.value;};
  if($('#port-select'))$('#port-select').onchange=e=>{selectedPort=e.target.value;};
  bindActions();
  if(page==='messages')chat.bind();else chat.watch();
  document.querySelectorAll('[data-page]').forEach(el=>el.onclick=()=>go(el.dataset.page));
  document.querySelectorAll('[data-section]').forEach(el=>el.onclick=()=>{selected=el.dataset.section;fieldSearch='';jsonMode=false;render();});
  document.querySelectorAll('[data-open-draft]').forEach(el=>el.onclick=()=>openDraft(el.dataset.openDraft));
  document.querySelectorAll('[data-field]').forEach(el=>el.addEventListener('input',()=>{
    const draft=ensureDraft();let value;
    if(el.dataset.repeated)draft.rawFields[el.dataset.field]=el.value;
    try {value=el.dataset.repeated?JSON.parse(el.value):el.type==='checkbox'?el.checked:el.dataset.kind==='integer'?(el.dataset.bits==='64'?el.value:el.value===''?'':Number(el.value)):el.dataset.kind==='number'?(el.value===''?'':Number(el.value)):el.value;
      setAt(draft.values,el.dataset.field,value);delete draft.jsonText;delete draft.fieldErrors[el.dataset.field];
    }catch{draft.fieldErrors[el.dataset.field]='Uma lista contém JSON inválido. Corrija o conteúdo antes de revisar.';}
    errors[selected]=Object.values(draft.fieldErrors)[0]||'';updateDraftUI();
  }));
  document.querySelectorAll('[data-clear]').forEach(el=>el.onclick=()=>{const draft=ensureDraft();setAt(draft.values,el.dataset.clear,['integer','number'].includes(el.dataset.clearKind)?0:'');delete draft.jsonText;render();});
  if($('#json-editor'))$('#json-editor').oninput=e=>{const draft=ensureDraft();draft.jsonText=e.target.value;try{const data=JSON.parse(e.target.value);if(!data||Array.isArray(data)||typeof data!=='object')throw new Error();draft.values=data;draft.fieldErrors={};draft.rawFields={};delete errors[selected];}catch{errors[selected]='JSON inválido. Informe um objeto e confira vírgulas e aspas.';}updateDraftUI();};
  if($('#field-search'))$('#field-search').oninput=e=>{fieldSearch=e.target.value;const pos=e.target.selectionStart;render();$('#field-search').focus();$('#field-search').setSelectionRange(pos,pos);};
  if($('#node-search'))$('#node-search').oninput=e=>{nodeSearch=e.target.value;const pos=e.target.selectionStart;render();$('#node-search').focus();$('#node-search').setSelectionRange(pos,pos);};
}
const actions={
  menu:()=>$('.sidebar').classList.toggle('open'), overview:()=>go('overview'),
  ports:()=>task(async()=>{ports=await api('ports');}),
  connect:()=>{
    let body;
    if(connectionType==='tcp'){
      const host=connectionHost.trim(), tcp_port=Number(connectionPort);
      if(!host)return notify('Informe o IP ou nome do rádio.',true);
      if(!Number.isInteger(tcp_port)||tcp_port<1||tcp_port>65535)return notify('A porta TCP deve estar entre 1 e 65535.',true);
      body={transport:'tcp',host,tcp_port};
    }else{
      const port=$('#port-select')?.value;
      if(!port)return notify('Nenhuma porta serial selecionada.',true);
      selectedPort=port;body={transport:'serial',port};
    }
    body.mode='desktop';
    task(async()=>{state=await api('connect',body);drafts={};errors={};chat.reset();},'Rádio conectado. Recepção de mensagens ativa.');
  },
  demo:()=>task(async()=>{state=await api('demo',{});drafts={};errors={};chat.reset();},'Demonstração iniciada. Nenhum acesso ao rádio.'),
  disconnect:()=>task(async()=>{state=await api('disconnect',{});drafts={};errors={};chat.reset();},'Sessão encerrada.'),
  refresh:()=>{if(dirtyKeys().length){return notify('Há rascunhos pendentes. Revise ou descarte antes de renovar toda a leitura.',true);}task(async()=>{state=await api('refresh',{});},'Leitura atualizada.');},
  'sync-state':()=>task(async()=>{state=await api('refresh',{});},'Lista atualizada.'),
  'read-section':()=>{if(dirty(selected))return notify('Revise ou descarte o rascunho desta seção antes de reler.',true);task(async()=>{state=await api(`read/${selected}`,{});delete drafts[selected];delete errors[selected];},'Seção consultada.');},
  json:()=>{if(errors[selected])return notify('Corrija o conteúdo inválido antes de trocar de editor.',true);jsonMode=!jsonMode;render();},
  discard:()=>{delete drafts[selected];delete errors[selected];render();},
  review:()=>task(async()=>{const draft=drafts[selected];preview=await api('preview',{section:selected,revision:draft.revision,values:draft.values});preview.section=selected;reviewDialog();}),
  export:()=>{const exportData={app:'Mesh Studio',exported_at:new Date().toISOString(),notice:'Leitura com segredos ocultos. Não é um backup restaurável.',demo:state.demo,device:state.device,sections:state.sections};const blob=new Blob([JSON.stringify(exportData,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const anchor=document.createElement('a');anchor.href=url;anchor.download=`mesh-studio-${state.device?.id?.replace('!','')||'leitura'}.json`;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);},
};
function reviewDialog(){
  const dialog=$('#review-dialog');const val=v=>v===undefined||v===null?'(não definido)':typeof v==='object'?JSON.stringify(v,null,2):String(v);
  dialog.innerHTML=`<div class="dialog-head"><div><h2 id="review-title">Revise cada alteração</h2><p>${esc(schema.find(s=>s.id===preview.section)?.name)} · ${esc(state.device.id)}</p></div><button class="btn ghost" id="close-review" aria-label="Fechar revisão">${icon('close')}</button></div><div class="dialog-body">${!preview.can_apply?`<div class="status-strip">${icon('lock')}A gravação real está bloqueada no servidor. Este rascunho pode ser revisado, mas não será enviado.</div>`:preview.demo?'<div class="status-strip demo">Aplicação simulada. Nenhum dispositivo real será alterado.</div>':''}${preview.warnings.map(w=>`<div class="status-strip demo">${icon('warning')}${esc(w)}</div>`).join('')}<div class="eyebrow">VALOR ATUAL → RASCUNHO</div>${preview.changes.map(c=>`<div class="diff-row"><code>${esc(c.path)}</code><div class="diff-before">${esc(val(c.before))}</div><div class="diff-after">${esc(val(c.after))}</div></div>`).join('')}${preview.can_apply?`<label class="confirm">Para ${preview.demo?'simular a aplicação':'enviar esta seção ao dispositivo'}, digite <b class="mono">${esc(preview.confirmation)}</b><input id="confirm-input" placeholder="${esc(preview.confirmation)}" autocomplete="off" spellcheck="false"></label>`:'<p class="export-note">Para permitir gravações reais em outra sessão, encerre o servidor e inicie com <code>.\start.ps1 -AllowWrites</code>. Esta página não consegue desbloquear gravações.</p>'}</div><div class="dialog-foot"><button class="btn ghost" id="cancel-review">Voltar ao rascunho</button><button class="btn primary" id="apply-review" disabled>${icon(preview.can_apply?'check':'lock')}${preview.demo?'Aplicar no simulador':'Aplicar ao dispositivo'}</button></div>`;
  $('#close-review').onclick=$('#cancel-review').onclick=()=>dialog.close();
  dialog.oncancel=e=>{if(applying)e.preventDefault();};
  if($('#confirm-input'))$('#confirm-input').oninput=e=>$('#apply-review').disabled=e.target.value!==preview.confirmation;
  $('#apply-review').onclick=async()=>{
    const input=$('#confirm-input');if(!preview.can_apply||input?.value!==preview.confirmation)return;
    const confirmation=input.value, token=preview.token, key=preview.section;
    applying=true;
    $('#apply-review').disabled=true;$('#apply-review').textContent='Aplicando e verificando…';input.disabled=true;
    $('#close-review').disabled=$('#cancel-review').disabled=true;
    try{state=await api('apply',{token,confirmation});delete drafts[key];delete errors[key];dialog.close();notify(state.demo?'Rascunho aplicado e conferido no simulador.':'Gravação conferida por uma nova leitura.');}
    catch(e){dialog.close();notify(e.message,true);try{state=await api('state');}catch{}}
    finally{preview=null;applying=false;render();}
  };
  if(!dialog.open)dialog.showModal();
}
async function syncSession(){
  const epoch=state.epoch;
  const session=await api('session');
  if(busy||epoch!==state.epoch)return;
  csrf=session.token;schema=session.schema;state=session.state;preview=null;
  if(!applying)$('#review-dialog').close();
  render();
}
const chat=createChat({syncSession,api,esc,icon,isBusy:()=>busy,getState:()=>state,task,notify,refreshState:async()=>{state=await api('state');}});
window.addEventListener('beforeunload',event=>{if(dirtyKeys().length||applying||chat.hasDrafts()){event.preventDefault();event.returnValue='';}});
try{const session=await api('session');csrf=session.token;schema=session.schema;state=session.state;ports=await api('ports');render();}catch(e){$('#app').innerHTML=`<div class="boot"><h1>Não foi possível iniciar</h1><p style="margin-top:15px">${esc(e.message)}</p><p class="muted" style="margin-top:12px">Verifique se o servidor local está em execução e recarregue a página.</p></div>`;}
