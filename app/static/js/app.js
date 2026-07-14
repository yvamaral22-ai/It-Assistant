const api = async (url, options = {}) => {
  const response = await fetch(url, {headers: {'Content-Type': 'application/json'}, ...options});
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || 'Não foi possível concluir a operação.');
  return data;
};

const startForm = document.querySelector('#start-form');
if (startForm) startForm.addEventListener('submit', async event => {
  event.preventDefault(); const error = document.querySelector('#form-error'); error.textContent = '';
  const payload = Object.fromEntries(new FormData(startForm));
  try {
    const result = await api('/api/sessions', {method: 'POST', body: JSON.stringify(payload)});
    sessionStorage.setItem('it-session-id', result.session.id);
    location.href = `/diagnostic/${encodeURIComponent(payload.category)}`;
  } catch (exc) { error.textContent = exc.message; }
});

const root = document.querySelector('#diagnostic');
if (root) {
  const sessionId = sessionStorage.getItem('it-session-id'); let count = 0; let canGoBack = false;
  const card = document.querySelector('#node-card'), error = document.querySelector('#diagnostic-error');
  const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const render = (node, nodeId) => {
    count++; document.querySelector('#progress-label').textContent = `Etapa ${count} do diagnóstico`;
    document.querySelector('#progress-bar').style.width = `${Math.min(90, 12 + count * 14)}%`;
    if (node.type === 'question') {
      card.innerHTML = `<span class="eyebrow">PERGUNTA</span><h1>${escapeHtml(node.text)}</h1><div>${node.options.map(o => `<button class="option" data-value="${escapeHtml(o.value)}">${escapeHtml(o.label)}</button>`).join('')}</div>`;
      card.querySelectorAll('.option').forEach(button => button.onclick = async () => {
        try { const result = await api(`/api/sessions/${sessionId}/answer`, {method:'POST',body:JSON.stringify({node_id:nodeId,value:button.dataset.value})}); canGoBack = true; render(result.node,result.node_id); } catch(exc){error.textContent=exc.message;}
      });
    } else if (node.type === 'solution') {
      card.innerHTML = `<span class="eyebrow">ORIENTAÇÃO</span><h1>${escapeHtml(node.title)}</h1><p>${escapeHtml(node.text)}</p><ol class="steps">${(node.steps||[]).map(s=>`<li>${escapeHtml(s)}</li>`).join('')}</ol>${node.ask_if_resolved ? '<h2>A orientação resolveu o problema?</h2><button class="option finish" data-status="resolved">Sim, resolveu</button><button class="option finish" data-status="unresolved">Não resolveu</button><button class="option finish" data-status="not_tested">Ainda não testei</button>' : '<button class="primary" id="continue">Continuar</button>'}`;
      card.querySelectorAll('.finish').forEach(button => button.onclick = () => solutionResult(button.dataset.status));
      const next = card.querySelector('#continue'); if(next) next.onclick = async()=>{const r=await api(`/api/sessions/${sessionId}/continue`,{method:'POST'});render(r.node,r.node_id)};
    } else { solutionResult('unresolved'); }
    document.querySelector('#back-button').hidden = !canGoBack;
  };
  const solutionResult = async status => {
    try { const result = await api(`/api/sessions/${sessionId}/solution-result`, {method:'POST',body:JSON.stringify({result:status})});
      if(status==='not_tested'){card.insertAdjacentHTML('beforeend','<p class="warning">Sem problema. A sessão continuará nesta orientação até você testar.</p>');return;}
      if(result.status === 'in_progress'){canGoBack=result.can_go_back;render(result.node,result.node_id);return;}
      card.innerHTML=`<span class="eyebrow">${status==='resolved'?'CONCLUÍDO':'ENCAMINHAMENTO'}</span><h1>${status==='resolved'?'Que bom que funcionou!':'Resumo pronto para o suporte'}</h1><pre id="final-summary">${escapeHtml(result.summary)}</pre><button class="primary" data-copy-target="final-summary">Copiar resumo</button>`; bindCopy();
    } catch(exc){error.textContent=exc.message;}
  };
  document.querySelector('#back-button').onclick=async()=>{try{const previous=await api(`/api/sessions/${sessionId}/back`,{method:'POST'});canGoBack=previous.can_go_back;error.textContent='';render(previous.node,previous.node_id);}catch(exc){error.textContent=exc.message;}};
  document.querySelector('#leave-link').onclick=event=>{if(!confirm('Deseja abandonar este diagnóstico?'))event.preventDefault();else api(`/api/sessions/${sessionId}/finish`,{method:'POST',body:JSON.stringify({status:'abandoned'})});};
  if(!sessionId){card.innerHTML='<p class="error">Sessão não encontrada. Volte ao início.</p>';} else api(`/api/sessions/${sessionId}`).then(r=>{canGoBack=r.can_go_back;render(r.node,r.session.current_node_id)}).catch(exc=>error.textContent=exc.message);
}

function bindCopy(){document.querySelectorAll('[data-copy-target]').forEach(button=>button.onclick=async()=>{await navigator.clipboard.writeText(document.getElementById(button.dataset.copyTarget).textContent);button.textContent='Resumo copiado!';});} bindCopy();
