export function createChat({api, esc, icon, getState, task, notify, refreshState}) {
  let data={messages:[],listening:false,max_bytes:233,can_send:false}, target='', timer, sending=false;
  const drafts=new Map();
  const channelSelections=new Map();
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
    return data.messages.filter(m=>m.conversation===target).map(m=>`<article class="chat-message ${m.direction==='out'?'outgoing':''}"><div class="chat-meta">${esc(m.direction==='out'?'Você':peerName(m.sender))} · ${esc(new Date(m.time).toLocaleTimeString('pt-BR'))}${m.via_mqtt?' · via MQTT':''}</div><p>${esc(m.text)}</p><div class="chat-meta">${esc(status[m.status]||m.status)}</div></article>`).join('')||'<div class="empty"><h3>Nenhuma mensagem capturada nesta conversa</h3><p>Use Receber por 30 segundos ou teste no simulador.</p></div>';
  }
  function receiveStatus(){return data.listening?'Recepção ativa: a Home pode pausar. A porta será liberada ao parar ou após 30 segundos de escuta.':'Recepção pausada. A porta fica livre entre operações.';}
  async function poll(){
    try{
      const next=await api('messages');
      if(next.epoch!==getState().epoch){pausePolling();notify('A sessão mudou. Recarregue a página antes de continuar.',true);return;}
      data=next;
      const recipient=$('#chat-target');
      if(recipient){const markup=optionMarkup();if(markup&&recipient.innerHTML!==markup)recipient.innerHTML=markup;}
      const list=$('#chat-feed');
      if(list){const atEnd=list.scrollHeight-list.scrollTop-list.clientHeight<50;list.innerHTML=feed();if(atEnd)list.scrollTop=list.scrollHeight;}
      if($('#chat-receive-status'))$('#chat-receive-status').textContent=receiveStatus();
      if($('#chat-stop'))$('#chat-stop').disabled=!data.listening;
    }catch{/* A failed local poll must never trigger a device reconnection. */}
  }
  function pausePolling(){clearInterval(timer);timer=null;}
  function render(state,busy){
    const opts=options();if(!opts.some(o=>o.id===target))target=opts[0]?.id||'';
    return `<section class="card chat-panel"><div class="chat-toolbar"><label>Conversa<select id="chat-target" ${busy?'disabled':''}>${opts.map(o=>`<option value="${esc(o.id)}" ${o.id===target?'selected':''}>${esc(o.label)}</option>`).join('')||'<option>Leia um dispositivo para começar</option>'}</select></label><div class="actions"><button class="btn ghost" id="chat-receive" ${busy||!state.session_active?'disabled':''}>${icon('download')}${state.demo?'Simular recebimento':'Receber por 30 segundos'}</button><button class="btn ghost" id="chat-stop" ${data.listening?'':'disabled'}>Parar recepção</button></div></div><p id="chat-receive-status" class="field-hint">${esc(receiveStatus())}</p><p class="field-hint">O histórico contém até 300 mensagens capturadas nesta sessão. Não importa o histórico completo do rádio e pode perder mensagens enquanto a porta está livre. Encerrar a sessão ou reiniciar o servidor apaga este histórico.</p><h2 id="chat-title">${esc(title())}</h2><div id="chat-feed" class="chat-feed" role="log" aria-label="Mensagens da conversa" aria-live="polite">${feed()}</div><label class="chat-composer">Mensagem para ${esc(title())}<textarea id="chat-text" rows="3" placeholder="Escreva uma mensagem…" ${busy||!state.session_active?'disabled':''}>${esc(drafts.get(target)||'')}</textarea></label><div class="chat-footer"><span id="chat-bytes" class="field-hint"></span><button class="btn primary" id="chat-review" ${busy||!state.writes_enabled||!target?'disabled':''}>${icon('eye')}Revisar mensagem</button></div>${state.session_active&&!state.writes_enabled?'<p class="field-hint">Envios bloqueados no modo somente leitura. A recepção continua disponível.</p>':''}<p class="field-hint">Para mensagens diretas, selecione o canal compartilhado abaixo. A criptografia e a entrega dependem do firmware e das chaves disponíveis; ACK de rede não é confirmação de leitura.</p><label id="chat-channel-label">Canal de envio<select id="chat-channel" ${busy?'disabled':''}>${opts.filter(o=>o.id.startsWith('channel:')).map(o=>`<option value="${o.id.slice(8)}">${esc(o.label)}</option>`).join('')}</select></label></section>`;
  }
  function updateCount(){
    const bytes=new TextEncoder().encode($('#chat-text')?.value||'').length;
    if($('#chat-bytes'))$('#chat-bytes').textContent=`${bytes} / ${data.max_bytes} bytes UTF-8`;
  }
  function bind(){
    if(!$('#chat-target'))return;
    $('#chat-channel-label').hidden=!target.startsWith('direct:');
    if(channelSelections.has(target))$('#chat-channel').value=channelSelections.get(target);
    $('#chat-channel').onchange=e=>channelSelections.set(target,e.target.value);
    $('#chat-target').onchange=e=>{target=e.target.value;task(async()=>{});};
    $('#chat-text').oninput=e=>{drafts.set(target,e.target.value);updateCount();};
    $('#chat-stop').onclick=async()=>{try{await api('messages/stop',{});notify('Parada solicitada. A porta será liberada ao concluir a comunicação atual.');}catch(e){notify(e.message,true);}};
    $('#chat-receive').onclick=()=>task(async()=>{try{data=await api('messages/receive',{});}finally{await refreshState();await poll();}},'Janela de recepção encerrada. Porta liberada.');
    $('#chat-review').onclick=()=>{
      const destination=target.startsWith('direct:')?target.slice(7):null;
      const channel=destination?Number($('#chat-channel').value):Number(target.slice(8));
      const text=$('#chat-text').value;
      task(async()=>{
        const review=await api('messages/preview',{text,channel,destination});
        const conversation=target;
        const dialog=$('#review-dialog');
        dialog.innerHTML=`<div class="dialog-head"><h2>Confirmar ${review.demo?'envio simulado':'envio da mensagem'}</h2></div><div class="dialog-body"><p>${esc(title())} · canal ${channel}</p><p class="chat-review-text">${esc(review.text)}</p><p class="field-hint">${review.bytes} bytes. O envio não altera configurações. Não há reenvio automático pelo app.</p></div><div class="dialog-foot"><button class="btn ghost" id="chat-cancel">Voltar</button><button class="btn primary" id="chat-send">${review.demo?'Enviar no simulador':'Enviar mensagem'}</button></div>`;
        dialog.oncancel=e=>{if(sending)e.preventDefault();};
        $('#chat-cancel').onclick=()=>dialog.close();
        $('#chat-send').onclick=async()=>{
          if(sending)return;sending=true;$('#chat-send').disabled=true;$('#chat-cancel').disabled=true;
          $('#chat-send').textContent='Enviando e aguardando confirmação…';
          try{data=await api('messages/send',{token:review.token});drafts.delete(conversation);notify('Consulte o resultado na conversa.');}
          catch(e){notify(e.message,true);}
          finally{sending=false;dialog.close();try{await refreshState();await poll();}catch{}task(async()=>{});}
        };
        dialog.showModal();
      });
    };
    updateCount();pausePolling();poll();timer=setInterval(poll,1500);
  }
  function reset(){pausePolling();data={messages:[],listening:false,max_bytes:233,can_send:false};drafts.clear();channelSelections.clear();target='';}
  return {render,bind,pausePolling,reset,hasDrafts:()=>sending||[...drafts.values()].some(t=>t.trim())};
}
