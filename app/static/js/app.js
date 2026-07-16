const api = async (url, options = {}) => {
  const response = await fetch(url, {headers: {'Content-Type': 'application/json'}, ...options});
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || 'Não foi possível concluir a operação.');
  return data;
};

const startForm = document.querySelector('#start-form');
const existingSessionId = sessionStorage.getItem('it-session-id');
const resumeBox = document.querySelector('#resume-session');
if (resumeBox && existingSessionId) api(`/api/sessions/${existingSessionId}`).then(result => {
  if (result.session.status === 'in_progress') {
    resumeBox.hidden = false;
    resumeBox.innerHTML = `<div><strong>Você tem um diagnóstico em andamento.</strong><span>Categoria: ${result.session.category}</span></div><a class="primary" href="/diagnostic/${encodeURIComponent(result.session.category)}">Retomar diagnóstico</a>`;
  } else sessionStorage.removeItem('it-session-id');
}).catch(() => sessionStorage.removeItem('it-session-id'));

const categorySearch = document.querySelector('#category-search');
if (categorySearch) categorySearch.addEventListener('input', () => {
  const term = categorySearch.value.trim().toLocaleLowerCase('pt-BR'); let visible = 0;
  document.querySelectorAll('.category').forEach(card => {
    const matches = card.textContent.toLocaleLowerCase('pt-BR').includes(term);
    card.hidden = !matches; if (matches) visible++;
  });
  document.querySelector('#category-empty').hidden = visible > 0;
});
if (startForm) startForm.addEventListener('submit', async event => {
  event.preventDefault(); const error = document.querySelector('#form-error'); error.textContent = '';
  const payload = Object.fromEntries([...new FormData(startForm)].filter(([, value]) => value !== ''));
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
      card.innerHTML = `<span class="eyebrow">ORIENTAÇÃO</span><h1>${escapeHtml(node.title)}</h1><p>${escapeHtml(node.text)}</p>${node.media?`<img class="solution-media" src="/static/${escapeHtml(node.media)}" alt="${escapeHtml(node.media_alt||'Ilustração da orientação')}">`:''}<ol class="steps">${(node.steps||[]).map(s=>`<li>${escapeHtml(s)}</li>`).join('')}</ol>${node.ask_if_resolved ? '<h2>A orientação resolveu o problema?</h2><button class="option finish" data-status="resolved">Sim, resolveu</button><button class="option finish" data-status="unresolved">Não resolveu</button><button class="option finish" data-status="not_tested">Ainda não testei</button>' : '<button class="primary" id="continue">Continuar</button>'}`;
      card.querySelectorAll('.finish').forEach(button => button.onclick = () => solutionResult(button.dataset.status));
      const next = card.querySelector('#continue'); if(next) next.onclick = async()=>{const r=await api(`/api/sessions/${sessionId}/continue`,{method:'POST'});render(r.node,r.node_id)};
    } else { solutionResult('unresolved'); }
    document.querySelector('#back-button').hidden = !canGoBack;
    card.focus();
  };
  const solutionResult = async status => {
    try { const result = await api(`/api/sessions/${sessionId}/solution-result`, {method:'POST',body:JSON.stringify({result:status})});
      if(status==='not_tested'){card.insertAdjacentHTML('beforeend','<p class="warning">Sem problema. A sessão continuará nesta orientação até você testar.</p>');return;}
      if(result.status === 'in_progress'){canGoBack=result.can_go_back;render(result.node,result.node_id);return;}
      card.innerHTML=`<span class="eyebrow">${status==='resolved'?'CONCLUÍDO':'ENCAMINHAMENTO'}</span><h1>${status==='resolved'?'Que bom que funcionou!':'Resumo pronto para o suporte'}</h1><pre id="final-summary">${escapeHtml(result.summary)}</pre><div class="summary-actions"><button class="secondary" data-copy-target="final-summary">Copiar resumo</button><button class="secondary" id="print-summary">Imprimir</button><button class="primary" id="close-service">Encerrar atendimento</button></div><section class="feedback-box"><h2>Como foi o atendimento?</h2><div class="rating" role="group" aria-label="Avaliação de uma a cinco estrelas">${[1,2,3,4,5].map(value=>`<button data-rating="${value}" aria-label="${value} estrela${value>1?'s':''}">★</button>`).join('')}</div><textarea id="feedback-comment" maxlength="1000" rows="2" placeholder="Comentário opcional"></textarea><p id="feedback-message" role="status"></p></section>`; bindCopy(); bindFeedback(); document.querySelector('#print-summary').onclick=()=>window.print(); document.querySelector('#close-service').onclick=()=>{sessionStorage.removeItem('it-session-id');location.href='/';}; sessionStorage.removeItem('it-session-id');
    } catch(exc){error.textContent=exc.message;}
  };
  const bindFeedback = () => document.querySelectorAll('[data-rating]').forEach(button => button.onclick = async () => {
    try {
      const rating = Number(button.dataset.rating); const feedback = document.querySelector('#feedback-comment').value || null;
      const result = await api(`/api/sessions/${sessionId}/feedback`, {method:'POST', body:JSON.stringify({rating,feedback})});
      document.querySelectorAll('[data-rating]').forEach(item=>item.classList.toggle('selected',Number(item.dataset.rating)<=rating));
      document.querySelector('#feedback-message').textContent=result.message;
    } catch(exc){error.textContent=exc.message;}
  });
  document.querySelector('#back-button').onclick=async()=>{try{const previous=await api(`/api/sessions/${sessionId}/back`,{method:'POST'});canGoBack=previous.can_go_back;error.textContent='';render(previous.node,previous.node_id);}catch(exc){error.textContent=exc.message;}};
  document.querySelector('#leave-link').onclick=async event=>{
    event.preventDefault();
    if(!confirm('Deseja abandonar este diagnóstico?'))return;
    try {
      await api(`/api/sessions/${sessionId}/finish`,{method:'POST',body:JSON.stringify({status:'abandoned'})});
    } catch(exc) {
      console.warn('Não foi possível registrar o abandono do diagnóstico.', exc);
    } finally {
      sessionStorage.removeItem('it-session-id');
      window.location.replace('/');
    }
  };
  if(!sessionId){card.innerHTML='<p class="error">Sessão não encontrada. Volte ao início.</p>';} else api(`/api/sessions/${sessionId}`).then(r=>{canGoBack=r.can_go_back;render(r.node,r.session.current_node_id)}).catch(exc=>error.textContent=exc.message);
}

function bindCopy(){document.querySelectorAll('[data-copy-target]').forEach(button=>button.onclick=async()=>{await navigator.clipboard.writeText(document.getElementById(button.dataset.copyTarget).textContent);button.textContent='Resumo copiado!';});} bindCopy();

const initBrandScrollTrigger = () => {
  const topbar = document.querySelector('.topbar');
  const brand = topbar?.querySelector('.brand');
  const motionAllowed = window.matchMedia('(min-width: 700px) and (prefers-reduced-motion: no-preference)');
  if (!topbar || !brand || !motionAllowed.matches) return;

  topbar.dataset.scroll3d = 'active';

  const render = () => {
    const triggerDistance = Math.max(360, Math.min(window.innerHeight * 0.75, 620));
    const progress = Math.min(1, Math.max(0, window.scrollY / triggerDistance));

    const horizontalTravel = Math.min(118, window.innerWidth * 0.075);
    brand.style.setProperty('--text-shift-x', `${(progress * horizontalTravel).toFixed(2)}px`);
    brand.style.setProperty('--text-rotate-y', `${(-progress * 18).toFixed(2)}deg`);
    brand.style.setProperty('--text-rotate-z', `${(progress * 1.2).toFixed(2)}deg`);
  };

  window.addEventListener('scroll', render, {passive: true});
  window.addEventListener('resize', render, {passive: true});
  render();
};

initBrandScrollTrigger();

const initProcessTabs = () => {
  const tabs = [...document.querySelectorAll('[data-process-tab]')];
  const panels = [...document.querySelectorAll('[data-process-panel]')];
  if (!tabs.length || !panels.length) return;

  const activate = tab => {
    const selectedId = tab.dataset.processTab;
    tabs.forEach(item => {
      const selected = item === tab;
      item.setAttribute('aria-selected', String(selected));
      item.tabIndex = selected ? 0 : -1;
    });
    panels.forEach(panel => {
      panel.hidden = panel.dataset.processPanel !== selectedId;
    });
  };

  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => activate(tab));
    tab.addEventListener('keydown', event => {
      if (!['ArrowDown', 'ArrowUp', 'ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const forward = ['ArrowDown', 'ArrowRight'].includes(event.key);
      let targetIndex = forward ? index + 1 : index - 1;
      if (event.key === 'Home') targetIndex = 0;
      if (event.key === 'End') targetIndex = tabs.length - 1;
      const target = tabs[(targetIndex + tabs.length) % tabs.length];
      activate(target);
      target.focus();
    });
  });
};

document.querySelectorAll('form[data-confirm]').forEach(form => {
  form.addEventListener('submit', event => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});

initProcessTabs();
