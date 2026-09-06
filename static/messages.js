export function createChat({api, esc, icon, getState, task, notify, refreshState, isBusy, syncSession}) {
  let data={messages:[],listening:false,active_phase:'off',max_bytes:233,can_send:false}, target='', timer, sending=false, viewBusy=false, generation=0, polling=false;
  const drafts=new Map();
  const failedMessages=new Map();
  const status={preparing:'Preparando',unconfirmed:'Sem confirmação de rede',ack:'ACK de rede · não confirma leitura',rejected:'Rede recusou o envio',unknown:'Resultado desconhecido · confira antes de reenviar',received:'Recebida',observed:'Observada no rádio',simulated:'Envio simulado'};
  const $=s=>document.querySelector(s);
  const peerName=id=>getState().nodes.find(n=>n.id===id)?.name||id;
  function options(){
    const s=getState(), result=[];
    for(let i=0;i<8;i++){const ch=s.sections[`channel.${i}`]?.values;if(ch&&ch.role!=='DISABLED')result.push({id:`channel:${i}`,label:`Canal ${i} · ${ch.settings?.name||'Padrão'}`});}
    for(const n of s.nodes.filter(n=>!n.local))result.push({id:`direct:${n.id}`,label:`Direta · ${n.name} (${n.id})`});
    for(const m of data.messages)if(!result.some(o=>o.id===m.conversation))result.push({id:m.conversation,label:m.conversation.startsWith('direct:')?`Direta · ${peerName(m.conversation.slice(7))}`:`Canal ${m.channel}`});
    return result;
  }
  const title=()=>options().find(o=>o.id===target)?.label||'Escolha uma conversa';
  function optionMarkup(){return options().map(o=>{
    const count=data.messages.filter(m=>m.conversation===o.id).length;
    return `<option value="${esc(o.id)}" ${o.id===target?'selected':''}>${esc(o.label)}${count?` · ${count} mensagem(ns)`:''}</option>`;
  }).join('');}
  function feed(){
    const messages=data.messages.filter(m=>m.conversation===target);
    return messages.map(m=>`<article class="chat-message ${m.direction==='out'?'outgoing':''}"><div class="chat-meta">${esc(m.direction==='out'?'Você':peerName(m.sender))} · ${esc(new Date(m.time).toLocaleTimeString('pt-BR'))}${m.via_mqtt?' · via MQTT':''}</div><p>${esc(m.text)}</p><div class="chat-meta">${esc(status[m.status]||m.status)}</div></article>`).join('')||'<div class="empty"><h3>Nenhuma mensagem capturada nesta conversa</h3><p>As mensagens recebidas aparecerão aqui enquanto o rádio estiver conectado.</p></div>';
  }
  function receiveStatus(){
    if(data.active_phase==='starting')return 'Conectando ao rádio…';
    if(data.active_phase==='stopping')return 'Desconectando… Aguardando a comunicação em andamento terminar.';
    if(data.active_phase==='active')return 'Conectado · recebendo mensagens';
    if(data.listen_error)return 'Não foi possível manter a conexão. Use Conectar ao rádio para tentar novamente.';
    return data.listening?'Recepção por 30 segundos em andamento. A conexão será encerrada ao terminar ou parar.':'Rádio desconectado · histórico preservado nesta sessão';
  }
  function disconnectedDesktop(){return !getState().demo&&getState().connection_mode==='desktop'&&data.active_phase!=='active';}
  function activePending(){return ['starting','stopping'].includes(data.active_phase);}
  function updateReceptionButtons(){
    if($('#chat-stop')){$('#chat-stop').disabled=!data.listening||data.active_phase==='stopping';$('#chat-stop').hidden=!data.listening;}
    if($('#chat-active')){$('#chat-active').disabled=viewBusy||data.listening||!getState().session_active;$('#chat-active').hidden=data.listening;}
    if($('#chat-receive'))$('#chat-receive').disabled=viewBusy||data.listening||!getState().session_active;
    if($('#chat-connection-error')){$('#chat-connection-error').hidden=!data.listen_error;$('#chat-connection-detail').textContent=data.listen_error||'';}
  }
  async function poll(){
    if(polling)return;
    polling=true;
    const epoch=getState().epoch, version=generation;
    try{
      const next=await api('messages');
      // Ignore responses started before our own connect/disconnect completed.
      if(epoch!==getState().epoch||version!==generation)return;
      if(next.epoch!==epoch){
        if(isBusy()||sending)return;
        data={messages:[],listening:false,active_phase:'off',max_bytes:233,can_send:false};
        await syncSession();
        return;
      }
      const changed=next.active_phase!==data.active_phase;
      data=next;
      if(changed){getState().active_phase=next.active_phase;if(!activePending())await refreshState();if(!sending)await task(async()=>{});}
      const recipient=$('#chat-target');
      if(recipient){const markup=optionMarkup();if(markup&&recipient.innerHTML!==markup)recipient.innerHTML=markup;}
      const list=$('#chat-feed');
      if(list){const atEnd=list.scrollHeight-list.scrollTop-list.clientHeight<50;list.innerHTML=feed();if(atEnd)list.scrollTop=list.scrollHeight;}
      if($('#chat-receive-status'))$('#chat-receive-status').textContent=receiveStatus();
      updateReceptionButtons();updateCount();
    }catch{/* A failed local poll must never trigger a device reconnection. */}
    finally{polling=false;}
  }
  function watch(){if(!timer){timer=setInterval(poll,1500);poll();}}
  function pausePolling(){clearInterval(timer);timer=null;}
  function render(state,busy){
    viewBusy=busy;
    data.active_phase=state.active_phase||'off';
    data.listening=['starting','active','stopping'].includes(data.active_phase)||data.listening&&data.listen_mode==='window';
    const opts=options();if(!opts.some(o=>o.id===target))target=opts[0]?.id||'';
    return `<section class="card chat-panel"><div class="chat-toolbar"><label>Conversa<select id="chat-target" ${busy?'disabled':''}>${opts.map(o=>`<option value="${esc(o.id)}" ${o.id===target?'selected':''}>${esc(o.label)}</option>`).join('')||'<option>Leia um dispositivo para começar</option>'}</select></label><div class="actions"><button class="btn primary" id="chat-active" ${busy||data.listening||!state.session_active?'disabled':''}>Conectar ao rádio</button><button class="btn ghost" id="chat-stop" ${data.listening?'':'disabled'}>Desconectar</button></div></div><p id="chat-receive-status" class="field-hint" role="status">${esc(receiveStatus())}</p><details id="chat-connection-error" class="chat-help" hidden><summary>Detalhes da conexão</summary><p id="chat-connection-detail" class="field-hint"></p></details><h2 id="chat-title">${esc(title())}</h2><div id="chat-feed" class="chat-feed" role="log" aria-label="Mensagens da conversa" aria-live="polite">${feed()}</div><label class="chat-composer">Mensagem<textarea id="chat-text" rows="2" placeholder="Escreva uma mensagem…" ${busy||!state.session_active?'disabled':''}>${esc(drafts.get(target)||'')}</textarea></label><div class="chat-footer"><span id="chat-bytes" class="field-hint"></span><button class="btn primary" id="chat-send" disabled>${icon('arrow')}Enviar</button></div><div id="chat-send-status" class="field-hint" role="status" aria-live="polite"></div><div id="chat-recovery"></div><p class="field-hint">Enter envia · Shift+Enter quebra a linha</p>${state.session_active&&!state.writes_enabled?'<p class="field-hint">Envios bloqueados no modo somente leitura. A recepção continua disponível.</p>':''}<details class="chat-help"><summary>Sobre recepção e entrega</summary><button class="btn ghost" id="chat-receive" ${busy||data.listening||!state.session_active?'disabled':''}>${icon('download')}${state.demo?'Simular recebimento':'Receber por 30 segundos'}</button><p class="field-hint">A escuta ativa continua ao navegar no app ou fechar a aba. Use Desconectar ou Encerrar sessão para liberar o rádio. Se a conexão cair, use Conectar ao rádio novamente; não há reconexão automática.</p><p class="field-hint">O histórico contém até 300 mensagens capturadas nesta sessão. Não importa o histórico completo do rádio e pode perder mensagens enquanto o app está desconectado. Encerrar a sessão ou reiniciar o servidor apaga este histórico.</p><p class="field-hint">ACK de rede não confirma leitura nem entrega a todos os membros de um canal. Uma falha de confirmação não provoca reenvio automático.</p></details></section>`;
  }
  function updateRecovery(){
    const el=$('#chat-recovery'), item=failedMessages.get(target);
    if(!el||el._item===item)return;
    el._item=item;
    el.innerHTML=item?`<details class="chat-help"><summary>Texto preservado do envio com erro</summary><p class="field-hint">${esc(item.error)}</p><p class="chat-recovery-text">${esc(item.text)}</p><button class="btn ghost" id="chat-restore">Voltar ao editor</button></details>`:'';
    if($('#chat-restore'))$('#chat-restore').onclick=()=>{
      if(drafts.get(target))return notify('O editor já contém outro rascunho. Limpe-o antes de recuperar este texto.',true);
      drafts.set(target,item.text);failedMessages.delete(target);
      $('#chat-text').value=item.text;$('#chat-text').focus();updateCount();
    };
  }
  function updateCount(){
    const text=$('#chat-text')?.value||'';
    const bytes=new TextEncoder().encode(text).length;
    const valid=Boolean(text.trim())&&!text.includes('\0')&&bytes<=data.max_bytes;
    if($('#chat-bytes')){
      $('#chat-bytes').textContent=`${bytes} / ${data.max_bytes} bytes`;
      $('#chat-bytes').classList.toggle('over-limit',bytes>data.max_bytes);
    }
    if($('#chat-send')){
      $('#chat-send').disabled=viewBusy||sending||activePending()||disconnectedDesktop()||!getState().writes_enabled||!target||!valid;
      $('#chat-send').innerHTML=icon('arrow')+(sending?'Enviando…':'Enviar');
    }
    if($('#chat-send-status'))$('#chat-send-status').textContent=sending?'Enviando. Você pode continuar escrevendo a próxima mensagem.':'';
    updateRecovery();
  }
  async function sendMessage(){
    if(sending||viewBusy||activePending()||disconnectedDesktop()||!getState().writes_enabled||!target)return;
    const input=$('#chat-text'), text=input?.value||'';
    if(!text.trim()||text.includes('\0')||new TextEncoder().encode(text).length>data.max_bytes)return;
    const conversation=target, version=generation, epoch=getState().epoch;
    const destination=conversation.startsWith('direct:')?conversation.slice(7):null;
    const primary=Object.entries(getState().sections).find(([key,section])=>key.startsWith('channel.')&&section.values?.role==='PRIMARY');
    const channel=destination?Number(primary?.[0].split('.')[1]??0):Number(conversation.slice(8));
    let submitted=false;
    sending=true;
    drafts.delete(conversation);failedMessages.delete(conversation);
    input.value='';input.focus();updateCount();
    try{
      // Validation and a one-use grant remain internal; the click/Enter sends.
      const grant=await api('messages/preview',{text,channel,destination});
      if(version!==generation||epoch!==getState().epoch)return;
      submitted=true;
      const result=await api('messages/send',{token:grant.token});
      if(version!==generation||epoch!==getState().epoch)return;
      data=result;
    }catch(e){
      if(version!==generation)return;
      const uncertain=submitted&&(!e.status||e.status>=500);
      const explanation=uncertain?'Resultado desconhecido. Confira a conversa antes de reenviar.':e.message;
      if(!uncertain&&!drafts.get(conversation)){
        drafts.set(conversation,text);
        if(target===conversation&&$('#chat-text'))$('#chat-text').value=text;
      }else{
        // Keep the original text available without replacing the next draft.
        failedMessages.set(conversation,{text,time:new Date().toISOString(),error:explanation});
      }
      notify(explanation,true);
    }finally{
      if(version===generation){
        sending=false;updateCount();
        try{await refreshState();await poll();}catch{}
        updateCount();
      }
    }
  }
  function bind(){
    if(!$('#chat-target'))return;
    $('#chat-target').onchange=e=>{target=e.target.value;task(async()=>{});};
    $('#chat-text').oninput=e=>{drafts.set(target,e.target.value);updateCount();};
    $('#chat-active').onclick=()=>task(async()=>{data=await api('messages/active',{});getState().active_phase=data.active_phase;await poll();});
    $('#chat-stop').onclick=async()=>{try{await api('messages/stop',{});await poll();}catch(e){notify(e.message,true);}};
    $('#chat-receive').onclick=()=>task(async()=>{try{data=await api('messages/receive',{});}finally{await refreshState();await poll();}},'Janela de recepção encerrada. Conexão encerrada.');
    $('#chat-send').onclick=sendMessage;
    $('#chat-text').onkeydown=e=>{
      if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing&&e.keyCode!==229){
        e.preventDefault();if(!e.repeat)sendMessage();
      }
    };
    updateReceptionButtons();updateCount();pausePolling();poll();timer=setInterval(poll,1500);
  }
  function reset(){generation++;sending=false;failedMessages.clear();pausePolling();data={messages:[],listening:false,active_phase:'off',max_bytes:233,can_send:false};drafts.clear();target='';}
  return {render,bind,watch,pausePolling,reset,hasDrafts:()=>sending||failedMessages.size>0||[...drafts.values()].some(t=>t.trim())};
}
