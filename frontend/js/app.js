// app.js — Orquesta Store, WorkflowBar, StreamMonitor, AgentPipeline y MetricCard.
// Responsabilidades: init, event wiring, export, streaming, filtros, templates.

let data = null;
let _streamTokenCount = 0;
let _streamCaseCount  = 0;
let _streamBuf        = '';

// ── Workflow step — delega a WorkflowBar
function setWorkflowStep(step) {
  WorkflowBar.set(step);
}

// ── UI helpers
function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  const tab   = document.getElementById('tab-' + name);
  const panel = document.getElementById('panel-' + name);
  if (tab)   tab.classList.add('active');
  if (panel) panel.classList.add('active');
}

function toggleCard(id) {
  document.getElementById('tc-' + id).classList.toggle('open');
}

function showToast(msg, color = 'var(--green)') {
  const toast = document.getElementById('toast');
  document.getElementById('toastMsg').textContent = msg;
  document.getElementById('toastDot').style.background = color;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 3500);
}

// ── Clear / Reset completo
function clearAll() {
  data = null;
  Store.reset();
  localStorage.removeItem('lastResult');

  // Inputs
  document.getElementById('userStory').value = '';
  document.getElementById('context').value   = '';

  // Listas
  ['tc-list', 'edge-list', 'bug-list'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.innerHTML = ''; el.style.display = 'none'; }
  });

  // Empties
  ['empty-tc', 'empty-edge', 'empty-bugs', 'empty-cov'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = 'flex';
  });

  // Counters
  ['tc', 'edge', 'bugs'].forEach(k => {
    const el = document.getElementById('cnt-' + k);
    if (el) el.textContent = '0';
  });

  // Coverage
  const covContent = document.getElementById('cov-content');
  if (covContent) covContent.style.display = 'none';

  // Export bar
  document.getElementById('exportBar').classList.remove('visible');

  // TC controls y filtros
  const ctrl = document.getElementById('tc-controls');
  if (ctrl) ctrl.style.display = 'none';
  const sw = document.getElementById('tcSearchWrap');
  if (sw) sw.style.display = 'none';
  const si = document.getElementById('tcSearch');
  if (si) si.value = '';
  _activeCategory = ''; _activePriority = '';
  document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
  const fw = document.getElementById('filterWrap');
  if (fw) fw.style.display = 'none';

  // Evaluate button
  document.getElementById('evaluateBtn').disabled = true;
  _hideEvalTimeHint();

  // Métricas mini bars (right panel)
  ['cov', 'rel', 'con', 'spe', 'nfb'].forEach(k => {
    const bar     = document.getElementById('bar-' + k);
    const scoreEl = document.getElementById('score-' + k);
    if (bar)     bar.style.width    = '0%';
    if (scoreEl) { scoreEl.textContent = '—'; scoreEl.style.color = 'var(--muted)'; }
  });
  const miniEmpty   = document.getElementById('metrics-mini-empty');
  const miniContent = document.getElementById('metrics-mini-content');
  if (miniEmpty)   miniEmpty.style.display   = 'flex';
  if (miniContent) miniContent.style.display = 'none';

  // Métricas dashboard (panel-metrics)
  const dashContent = document.getElementById('metrics-dashboard-content');
  if (dashContent) { dashContent.innerHTML = ''; dashContent.style.display = 'none'; }
  const emptyMetrics = document.getElementById('empty-metrics');
  if (emptyMetrics) emptyMetrics.style.display = 'flex';

  // Pipeline de agentes (right panel)
  if (typeof AgentPipeline !== 'undefined') AgentPipeline.reset();

  // Stream monitor
  if (typeof StreamMonitor !== 'undefined') StreamMonitor.hide();

  // Agentes tab
  const agentList = document.getElementById('agent-trace-list');
  if (agentList) { agentList.innerHTML = ''; agentList.style.display = 'none'; }
  const emptyAgents = document.getElementById('empty-agents');
  if (emptyAgents) emptyAgents.style.display = 'flex';

  // Fallback banner
  const fb = document.getElementById('fallbackBannerMain');
  if (fb) fb.remove();

  // KPIs del header
  ['kpi-tc-val', 'kpi-bugs-val', 'kpi-coverage-val'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = '—';
  });
  const kpiScore = document.getElementById('kpi-score-val');
  if (kpiScore) { kpiScore.textContent = '—'; kpiScore.style.color = ''; }

  setWorkflowStep('input');
  showToast('Resultados borrados', 'var(--muted2)');
}

// ── Export
function copyJSON() {
  if (!data) return;
  navigator.clipboard.writeText(JSON.stringify(data, null, 2))
    .then(() => showToast('JSON copiado al portapapeles'))
    .catch(() => showToast('No se pudo copiar', 'var(--red)'));
}

function downloadJSON() {
  if (!data) return;
  _download(JSON.stringify(data, null, 2), 'test-cases.json', 'application/json');
}

function downloadCSV() {
  if (!data) return;
  const header = ['ID', 'Categoría', 'Título', 'Pasos', 'Resultado esperado', 'Prioridad'];
  const rows   = (data.test_cases || []).map(tc => [
    tc.id || '', tc.category || '', tc.title || '',
    (tc.steps || []).join(' | '), tc.expected_result || '', tc.priority || '',
  ].map(v => `"${String(v).replace(/"/g, '""')}"`));
  const csv = [header, ...rows].map(r => r.join(',')).join('\r\n');
  _download('﻿' + csv, 'test-cases.csv', 'text/csv;charset=utf-8');
}

function downloadMarkdown() {
  if (!data) return;
  const lines = ['# Test Cases', ''];
  const byCategory = {};
  (data.test_cases || []).forEach(tc => {
    const cat = tc.category || 'general';
    if (!byCategory[cat]) byCategory[cat] = [];
    byCategory[cat].push(tc);
  });
  for (const [cat, tcs] of Object.entries(byCategory)) {
    lines.push('## ' + cat.replace(/_/g, ' ').toUpperCase(), '');
    tcs.forEach(tc => {
      lines.push('### ' + (tc.id || '') + ' · ' + tc.title, '');
      lines.push('**Prioridad:** ' + (tc.priority || ''), '');
      if (tc.preconditions && tc.preconditions.length) {
        lines.push('**Precondiciones:**');
        tc.preconditions.forEach(p => lines.push('- ' + p));
        lines.push('');
      }
      lines.push('**Pasos:**');
      (tc.steps || []).forEach((s, i) => lines.push((i + 1) + '. ' + s));
      lines.push('', '> **Resultado esperado:** ' + tc.expected_result, '');
    });
  }
  _download(lines.join('\n'), 'test-cases.md', 'text/markdown;charset=utf-8');
}

function downloadXLSX() {
  if (!data || typeof XLSX === 'undefined') {
    showToast('XLSX no disponible', 'var(--red)'); return;
  }
  const wb = XLSX.utils.book_new();
  const tcRows = (data.test_cases || []).map(tc => ({
    ID: tc.id || '', Título: tc.title || '', Categoría: tc.category || '',
    Prioridad: tc.priority || '', 'Tipo': tc.test_type || '',
    Precondiciones: (tc.preconditions || []).join(' | '),
    Pasos: (tc.steps || []).join(' | '), 'Resultado esperado': tc.expected_result || '',
  }));
  XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(tcRows.length ? tcRows : [{}]), 'Test Cases');
  const edgeRows = (data.edge_scenarios || []).map(e => ({
    ID: e.id || '', Escenario: e.scenario || '',
    'Nivel de riesgo': e.risk_level || '', Descripción: e.description || '',
  }));
  XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(edgeRows.length ? edgeRows : [{}]), 'Edge Scenarios');
  const bugRows = (data.potential_bugs || []).map(b => ({
    ID: b.id || '', Título: b.title || '', Área: b.area || '',
    Probabilidad: b.likelihood || '', Descripción: b.description || '',
    'Test sugerido': b.suggested_test || '',
  }));
  XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(bugRows.length ? bugRows : [{}]), 'Potential Bugs');
  const cov = data.coverage_summary || {};
  const covRows = [
    { Métrica: 'Total casos',            Valor: cov.total_test_cases ?? '' },
    { Métrica: 'Categorías cubiertas',   Valor: (cov.categories_covered || []).join(', ') },
    { Métrica: 'Cobertura estimada (%)', Valor: cov.estimated_coverage_percent ?? '' },
    { Métrica: 'Áreas faltantes',        Valor: (cov.missing_areas || []).join(', ') },
  ];
  XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(covRows), 'Coverage');
  XLSX.writeFile(wb, 'test-cases.xlsx');
  showToast('XLSX exportado correctamente');
}

function _download(content, filename, type) {
  const blob = new Blob([content], { type });
  const url  = URL.createObjectURL(blob);
  const a    = Object.assign(document.createElement('a'), { href: url, download: filename });
  a.click();
  URL.revokeObjectURL(url);
}

// ── Streaming helpers (modo estándar, sin agentes)
function showStreamPreview() {
  _streamTokenCount = 0;
  _streamCaseCount  = 0;
  _streamBuf        = '';
  // Ocultar stream-monitor si estuviera visible
  StreamMonitor.hide();
  document.getElementById('streamPreview').classList.add('visible');
  document.getElementById('streamText').textContent = 'Iniciando generación...';
  document.getElementById('empty-tc').style.display = 'none';
  document.getElementById('tc-list').style.display  = 'none';
}

function hideStreamPreview() {
  document.getElementById('streamPreview').classList.remove('visible');
  document.getElementById('streamText').textContent = '';
}

function appendStreamToken(token) {
  _streamTokenCount++;
  _streamBuf += token;
  const newCases = (token.match(/"title"\s*:/g) || []).length;
  _streamCaseCount += newCases;
  const el = document.getElementById('streamText');
  if (!el) return;
  if (_streamCaseCount > 0) {
    el.textContent = `Generando... ${_streamCaseCount} caso${_streamCaseCount > 1 ? 's' : ''} detectado${_streamCaseCount > 1 ? 's' : ''}`;
  } else {
    el.textContent = `Procesando... ${_streamTokenCount} tokens`;
  }
}

// ── Search TC
function searchTC(query) {
  const q = query.toLowerCase().trim();
  document.querySelectorAll('#tc-list .tc-card').forEach(card => {
    const text = card.innerText.toLowerCase();
    card.style.display = (!q || text.includes(q)) ? '' : 'none';
  });
}

// ── Templates
const TEMPLATES = {
  login:         { label: 'Login con email y contraseña', story: 'Como usuario registrado quiero poder iniciar sesión con mi email y contraseña para acceder a mi cuenta personal.', context: 'El sistema debe bloquear la cuenta tras 3 intentos fallidos y enviar email de recuperación.' },
  registro:      { label: 'Registro de nuevo usuario', story: 'Como visitante quiero poder registrarme en la plataforma proporcionando nombre, email y contraseña para crear mi cuenta.', context: 'El email debe ser único en el sistema. La contraseña debe tener mínimo 8 caracteres.' },
  checkout:      { label: 'Proceso de pago (Checkout)', story: 'Como cliente quiero poder completar una compra seleccionando método de pago y dirección de envío para recibir mi pedido.', context: 'Integración con pasarela de pago. Se debe validar stock antes de confirmar.' },
  busqueda:      { label: 'Búsqueda de productos', story: 'Como usuario quiero buscar productos por nombre, categoría o precio para encontrar lo que necesito rápidamente.', context: 'El buscador debe soportar filtros combinados y ordenamiento por relevancia, precio y valoración.' },
  upload:        { label: 'Subir archivos', story: 'Como usuario quiero poder subir documentos al sistema para adjuntarlos a mis solicitudes.', context: 'Formatos permitidos: PDF, DOCX, PNG, JPG. Tamaño máximo: 10MB por archivo.' },
  recuperacion:  { label: 'Recuperación de contraseña', story: 'Como usuario que olvidó su contraseña quiero recibir un enlace de recuperación en mi email para restablecer el acceso a mi cuenta.', context: 'El enlace debe expirar en 30 minutos. Solo puede usarse una vez.' },
  perfil:        { label: 'Editar perfil de usuario', story: 'Como usuario autenticado quiero poder editar mis datos de perfil (nombre, foto, teléfono) para mantener mi información actualizada.', context: 'Los cambios deben reflejarse inmediatamente en la UI sin recargar la página.' },
  notificaciones:{ label: 'Sistema de notificaciones', story: 'Como usuario quiero recibir notificaciones en tiempo real sobre el estado de mis pedidos para estar informado sin tener que consultar manualmente.', context: 'Las notificaciones deben aparecer en la barra superior y también enviarse por email según preferencias.' },
};

function loadTemplate(key) {
  if (!key || !TEMPLATES[key]) return;
  const t = TEMPLATES[key];
  document.getElementById('userStory').value = t.story;
  document.getElementById('context').value   = t.context;
}

// ── Filter TC
let _activeCategory = '';
let _activePriority = '';

function filterTC(type, value) {
  if (type === 'category') _activeCategory = (_activeCategory === value ? '' : value);
  if (type === 'priority')  _activePriority = (_activePriority === value ? '' : value);

  document.querySelectorAll('#filterCats .chip').forEach(c =>
    c.classList.toggle('active', c.dataset.value === _activeCategory && _activeCategory !== ''));
  document.querySelectorAll('#filterPrios .chip').forEach(c =>
    c.classList.toggle('active', c.dataset.value === _activePriority && _activePriority !== ''));

  document.querySelectorAll('#tc-list .tc-card').forEach(card => {
    const matchCat  = !_activeCategory || card.dataset.category === _activeCategory;
    const matchPrio = !_activePriority  || card.dataset.priority === _activePriority;
    card.style.display = (matchCat && matchPrio) ? '' : 'none';
  });
}

function getSelectedCategories() {
  return [...document.querySelectorAll('#catChecks input[type=checkbox]:checked')]
    .map(cb => cb.value);
}

function getQtyCounts() {
  return {
    tc_count:   Math.max(1, parseInt(document.getElementById('tcCount')?.value)  || 10),
    edge_count: Math.max(0, parseInt(document.getElementById('edgeCount')?.value) || 4),
    bug_count:  Math.max(0, parseInt(document.getElementById('bugCount')?.value)  || 3),
  };
}

function updateCatDistHint() {
  const hint = document.getElementById('catDistHint');
  if (!hint) return;
  const cats  = getSelectedCategories();
  const count = Math.max(1, parseInt(document.getElementById('tcCount')?.value) || 10);
  if (!cats.length) { hint.textContent = ''; return; }
  const base = Math.floor(count / cats.length);
  const rem  = count % cats.length;
  const parts = cats.map((c, i) => `${c.replace(/_/g,' ')}: ${base + (i < rem ? 1 : 0)}`);
  hint.textContent = 'Distribución: ' + parts.join(' · ');
}

// ── Modo: estándar vs agentes
let _agentMode = false;

function setAgentMode(on) {
  _agentMode = on;
  Store.set('agentMode', on);
  document.getElementById('modeStd').classList.toggle('mode-active', !on);
  document.getElementById('modeAgents').classList.toggle('mode-active', on);
  const agentInfo = document.getElementById('agentModeInfo');
  if (agentInfo) agentInfo.style.display = on ? 'block' : 'none';
  if (!on && typeof AgentPipeline !== 'undefined') AgentPipeline.hide();
}

// ── Estimado de tiempo de evaluación DeepEval
function _showEvalTimeHint(elapsedSecs, tcCount) {
  const hint = document.getElementById('eval-time-hint');
  if (!hint) return;
  // Cada métrica GEval procesa el JSON completo (similar carga al LLM que generó)
  // Estimación: 0.8× el tiempo de generación por métrica × 5 métricas
  const secsPerMetric = Math.max(12, Math.round(elapsedSecs * 0.8));
  const low  = Math.max(1, Math.floor((secsPerMetric * 5) / 60));
  const high = Math.ceil((secsPerMetric * 5 * 1.5) / 60);
  const range = low === high ? `~${low} min` : `~${low}–${high} min`;
  hint.textContent = `⏱ Evaluación estimada: ${range} (5 métricas, ${tcCount} casos)`;
  hint.style.display = 'block';
}

function _hideEvalTimeHint() {
  const hint = document.getElementById('eval-time-hint');
  if (hint) hint.style.display = 'none';
}

// ── RAG status
async function checkRagStatus() {
  try {
    const res = await fetch(API + '/rag/status');
    const { built, chunk_count } = await res.json();
    const label = document.getElementById('ragStatusLabel');
    const cb    = document.getElementById('ragToggle');
    if (label) {
      label.textContent = built ? `Base QA (${chunk_count} chunks)` : 'Índice no construido';
      label.style.color = built ? 'var(--green)' : 'var(--muted)';
    }
    if (cb) cb.disabled = !built;
  } catch { /* silencioso */ }
}

// ── Generate — modo estándar (usa readSSE)
async function generate() {
  const story = document.getElementById('userStory').value.trim();
  if (!story) { showToast('Escribe una historia de usuario primero', 'var(--amber)'); return; }
  if (_agentMode) { return generateAgents(); }

  const btn     = document.getElementById('generateBtn');
  const spinner = document.getElementById('spinner');
  const btnText = document.getElementById('btnText');
  btn.disabled = true;
  spinner.style.display = 'block';
  btnText.textContent   = 'Generando...';
  document.getElementById('evaluateBtn').disabled = true;

  const _t0 = Date.now();
  let _timerInterval;
  switchTab('tc');
  showStreamPreview();
  setWorkflowStep('generate');

  _timerInterval = setInterval(() => {
    const s = Math.round((Date.now() - _t0) / 1000);
    document.getElementById('btnText').textContent = 'Generando... ' + s + 's';
  }, 1000);

  const useRag = document.getElementById('ragToggle')?.checked ?? false;

  try {
    const res = await fetch(API + '/generate/stream', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_story:  story,
        model:       document.getElementById('modelSelect').value,
        context:     document.getElementById('context').value,
        temperature: parseFloat(document.getElementById('tempSlider').value),
        use_rag:     useRag,
        categories:  getSelectedCategories(),
        ...getQtyCounts(),
      }),
    });

    if (!res.ok) throw new Error((await res.json()).detail || 'Error del servidor');

    for await (const msg of readSSE(res)) {
      if (msg.token !== undefined) {
        appendStreamToken(msg.token);
      } else if (msg.case) {
        if (!data) data = { test_cases: [], edge_scenarios: [], potential_bugs: [], coverage_summary: {} };
        data.test_cases.push(msg.case);
        appendTC(msg.case);
        if (data.test_cases.length === 1) switchTab('tc');
      } else if (msg.result) {
        data = msg.result;
        localStorage.setItem('lastResult', JSON.stringify(data));
        hideStreamPreview();
        const tcStreamed = (data.test_cases || []).length > 0 &&
                           document.querySelectorAll('#tc-list .tc-card').length > 0;
        renderResult(data, tcStreamed);
        setWorkflowStep('evaluate');
        const elapsed = Math.round((Date.now() - _t0) / 1000);
        const tcCount = (data.test_cases || []).length;
        const ragTag  = useRag ? ' · RAG' : '';
        showToast(`${tcCount} casos generados en ${elapsed}s${ragTag}`);
        _showEvalTimeHint(elapsed, tcCount);
        document.getElementById('evaluateBtn').disabled = false;
      } else if (msg.error) {
        throw new Error(msg.error);
      }
    }

  } catch (e) {
    hideStreamPreview();
    if (!document.querySelectorAll('#tc-list .tc-card').length) {
      const emptyTc = document.getElementById('empty-tc');
      if (emptyTc) emptyTc.style.display = 'flex';
    }
    showToast('Error: ' + e.message, 'var(--red)');
    setWorkflowStep('input');
  } finally {
    clearInterval(_timerInterval);
    btn.disabled = false;
    spinner.style.display = 'none';
    btnText.textContent   = 'Generar casos de prueba';
  }
}

// ── Generate con agentes CrewAI (usa readSSE + StreamMonitor)
async function generateAgents() {
  const story = document.getElementById('userStory').value.trim();

  const btn     = document.getElementById('generateBtn');
  const spinner = document.getElementById('spinner');
  const btnText = document.getElementById('btnText');
  btn.disabled = true;
  spinner.style.display = 'block';
  document.getElementById('evaluateBtn').disabled = true;

  const _t0 = Date.now();
  let _timerInterval;

  setWorkflowStep('generate');
  switchTab('tc');

  // StreamMonitor toma el control del panel-tc
  StreamMonitor.show();
  AgentPipeline.show();
  AgentPipeline.reset();

  _timerInterval = setInterval(() => {
    const s = Math.round((Date.now() - _t0) / 1000);
    btnText.textContent = `Agentes trabajando... ${s}s`;
  }, 1000);

  const useRag      = document.getElementById('ragToggle')?.checked ?? false;
  const agentTraces = [];
  _streamCaseCount  = 0;

  try {
    const res = await fetch(API + '/generate/agents/stream', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_story:  story,
        model:       document.getElementById('modelSelect').value,
        context:     document.getElementById('context').value,
        temperature: parseFloat(document.getElementById('tempSlider').value),
        use_rag:     useRag,
        categories:  getSelectedCategories(),
        ...getQtyCounts(),
      }),
    });

    if (!res.ok) throw new Error((await res.json()).detail || 'Error en agentes');

    for await (const msg of readSSE(res)) {

      if (msg.event === 'agent_start') {
        AgentPipeline.agentStart(msg.agent, msg.step);
        StreamMonitor.setAgent(msg.agent, msg.step, msg.total);
        btnText.textContent = `${msg.agent} (${msg.step}/${msg.total})...`;

      } else if (msg.event === 'token') {
        AgentPipeline.agentProgress(msg.agent || 'Generador', _streamCaseCount);

      } else if (msg.event === 'case') {
        if (!data) data = { test_cases: [], edge_scenarios: [], potential_bugs: [], coverage_summary: {}, raw_story: story };
        data.test_cases = data.test_cases || [];
        data.test_cases.push(msg.case);
        _streamCaseCount++;
        appendTC(msg.case);
        StreamMonitor.addCase(msg.case.id || `TC-${_streamCaseCount}`, msg.case.category || '');
        AgentPipeline.agentProgress('Generador', _streamCaseCount);

      } else if (msg.event === 'agent_done') {
        agentTraces.push({ agent: msg.agent, elapsed_s: msg.elapsed_s, summary: msg.summary });
        AgentPipeline.agentDone(msg.agent, msg.step, msg.summary, msg.elapsed_s);
        StreamMonitor.agentDone(msg.agent, msg.elapsed_s, msg.summary);

        if (msg.agent === 'Generador') {
          data = { ...(data || {}), ...msg.data, raw_story: story };
          localStorage.setItem('lastResult', JSON.stringify(data));
          showToast(
            `${(msg.data?.test_cases || []).length} casos listos · Revisor analizando...`,
            'var(--cyan)'
          );
        }

        if (msg.agent === 'Revisor') {
          if (msg.decisions?.length) {
            AgentPipeline.showDecisions('Revisor', msg.decisions);
            msg.decisions.forEach(d =>
              StreamMonitor.addDecision(d.tc_id || d.id, d.verdict, d.reason)
            );
          }
          renderAgentTrace(agentTraces, false, null);
        }

      } else if (msg.event === 'done') {
        data = msg.data;
        localStorage.setItem('lastResult', JSON.stringify(data));
        StreamMonitor.hide();

        const tcStreamed = document.querySelectorAll('#tc-list .tc-card').length > 0;
        renderResult(data, tcStreamed);
        setWorkflowStep('evaluate');

        if (data.agent_trace?.length) {
          renderAgentTrace(data.agent_trace, data.used_fallback, data.optimizer_output);
          data.agent_trace.forEach(trace => {
            if (trace.decisions?.length) AgentPipeline.showDecisions(trace.agent, trace.decisions);
          });
        }

        if (data.used_fallback) {
          const bar = document.getElementById('exportBar');
          if (bar && !document.getElementById('fallbackBannerMain')) {
            bar.insertAdjacentHTML('afterbegin',
              `<div id="fallbackBannerMain" class="fallback-banner">
                 ⚠ Modo Fallback — CrewAI no disponible, se usó generación directa
               </div>`);
          }
        }

        const elapsed     = Math.round((Date.now() - _t0) / 1000);
        const tcCount     = (data.test_cases || []).length;
        const fallbackTag = data.used_fallback ? ' (fallback)' : '';
        showToast(`${tcCount} casos · ${elapsed}s${fallbackTag}`);
        _showEvalTimeHint(elapsed, tcCount);
        document.getElementById('evaluateBtn').disabled = false;

      } else if (msg.event === 'error') {
        throw new Error(msg.message || 'Error en pipeline de agentes');
      }
    }

  } catch (e) {
    StreamMonitor.error('Generador', e.message);
    StreamMonitor.hide();
    AgentPipeline.agentError('Generador', e.message);
    showToast('Error en agentes: ' + e.message, 'var(--red)');
    setWorkflowStep('input');
  } finally {
    clearInterval(_timerInterval);
    btn.disabled = false;
    spinner.style.display = 'none';
    btnText.textContent   = 'Generar casos de prueba';
  }
}

// ── Render traza de agentes (tab Agentes — resumen post-run)
function renderAgentTrace(traces, usedFallback, optimizerOutput = null) {
  const empty     = document.getElementById('empty-agents');
  const container = document.getElementById('agent-trace-list');
  if (!container) return;

  if (empty) empty.style.display = 'none';
  container.style.display = 'block';

  const fallbackBanner = usedFallback
    ? '<div class="fallback-banner" style="margin-bottom:12px">⚠ CrewAI falló — se usó generación directa como fallback</div>'
    : '';

  const gapsHtml = optimizerOutput?.priority_gaps?.length
    ? `<div class="trace-section">
        <div class="trace-section-label">Brechas Críticas Identificadas</div>
        ${optimizerOutput.priority_gaps.map(g => `
          <div class="trace-gap">
            <span class="trace-gap-rank" style="background:${g.impact === 'alto' ? 'var(--red)' : 'var(--amber)'}">${g.rank}</span>
            <div>
              <div class="trace-gap-reason">${g.reason}</div>
              <div class="trace-gap-meta">Categoría: ${g.category} · Impacto: ${g.impact}</div>
            </div>
          </div>`).join('')}
      </div>`
    : '';

  const summaryHtml = optimizerOutput?.optimization_summary
    ? `<div class="trace-summary">${optimizerOutput.optimization_summary}</div>`
    : '';

  container.innerHTML = fallbackBanner + traces.map(t => `
    <div class="trace-card">
      <div class="trace-card-header">
        <span class="trace-card-agent">${t.agent}</span>
        <span class="trace-card-elapsed">${t.elapsed_s}s</span>
      </div>
      <p class="trace-card-summary">${t.summary}</p>
    </div>`).join('') + gapsHtml + summaryHtml;
}

// ── Evaluate (DeepEval streaming — usa readSSE)
async function evaluate() {
  if (!data) { showToast('Genera casos de prueba primero', 'var(--amber)'); return; }
  const story = document.getElementById('userStory').value.trim();
  if (!story) { showToast('Necesitas una historia de usuario para evaluar', 'var(--amber)'); return; }

  const btn = document.getElementById('evaluateBtn');
  btn.disabled = true;
  btn.querySelector('span').textContent = '⟳';
  _hideEvalTimeHint();

  // Resetear métricas
  ['cov', 'rel', 'con', 'spe', 'nfb'].forEach(k => setMetric(k, 0));
  const dashContent = document.getElementById('metrics-dashboard-content');
  if (dashContent) { dashContent.innerHTML = ''; dashContent.style.display = 'none'; }
  const emptyMetrics = document.getElementById('empty-metrics');
  if (emptyMetrics) emptyMetrics.style.display = 'flex';
  const miniContent = document.getElementById('metrics-mini-content');
  const miniEmpty   = document.getElementById('metrics-mini-empty');
  if (miniContent) miniContent.style.display = 'none';
  if (miniEmpty)   miniEmpty.style.display   = 'flex';

  showToast('Evaluando con DeepEval...', 'var(--cyan)');

  const KEY_MAP = {
    coverage: 'cov', relevancy: 'rel', consistency: 'con',
    specificity: 'spe', nonfunctional_balance: 'nfb',
  };

  const _metricsCollected = {};
  const _reasonsCollected = {};
  let   _firstMetric      = true;

  // Modelo de evaluación: el usuario puede elegir uno diferente al de generación
  // para evitar sesgo de auto-evaluación. Si está vacío, el backend usa su default.
  const evalModelEl = document.getElementById('evalModelSelect');
  const evalModel   = evalModelEl?.value || document.getElementById('modelSelect').value;

  try {
    const res = await fetch(API + '/evaluate/stream', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        requirement:      story,
        generated_output: data,
        model:            document.getElementById('modelSelect').value,
        eval_model:       evalModel,
      }),
    });

    if (!res.ok) throw new Error((await res.json()).detail || 'Error de evaluación');

    for await (const msg of readSSE(res)) {
      if (msg.error) throw new Error(msg.error);

      if (msg.metric) {
        const shortKey = KEY_MAP[msg.metric];
        if (shortKey) setMetric(shortKey, msg.score);
        _metricsCollected[msg.metric] = msg.score;
        if (msg.reason) _reasonsCollected[msg.metric] = msg.reason;
        renderMetricsDashboard(_metricsCollected, _reasonsCollected);

        // Mostrar sección mini en primer resultado
        if (_firstMetric) {
          _firstMetric = false;
          if (miniEmpty)   miniEmpty.style.display   = 'none';
          if (miniContent) miniContent.style.display = 'block';
        }

        const icon  = msg.passed ? '✓' : '✗';
        const color = msg.passed ? 'var(--green)' : 'var(--amber)';
        showToast(`${msg.name} ${icon} ${msg.score.toFixed(2)} (${msg.step}/${msg.total})`, color);
      }

      if (msg.done) {
        Store.set('metrics', { ..._metricsCollected });
        renderMetricsDashboard(_metricsCollected, _reasonsCollected);
        updateKPIs(data, msg.overall);
        setWorkflowStep('export');
        showToast(`Evaluación completa · overall ${msg.overall.toFixed(2)}`);
        switchTab('metrics');
      }
    }

  } catch (e) {
    showToast('Error: ' + e.message, 'var(--red)');
  } finally {
    btn.disabled = false;
    btn.querySelector('span').textContent = '◈';
  }
}

// ── Regenerar TC individual
async function regenerateTC(cardIndex, tcId, category) {
  const story = document.getElementById('userStory').value.trim();
  if (!story) { showToast('Necesitas una historia de usuario', 'var(--amber)'); return; }

  const card = document.getElementById('tc-' + cardIndex);
  const btn  = card?.querySelector('.btn-regen');
  if (btn) { btn.textContent = '⟳'; btn.disabled = true; btn.style.opacity = '0.5'; }

  try {
    const res = await fetch(API + '/regenerate-tc', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tc_id:       tcId,
        user_story:  story,
        model:       document.getElementById('modelSelect').value,
        temperature: parseFloat(document.getElementById('tempSlider').value),
        category,
        context:     document.getElementById('context').value,
      }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'Error');
    const { test_case } = await res.json();

    if (data?.test_cases?.[cardIndex]) {
      data.test_cases[cardIndex] = test_case;
      localStorage.setItem('lastResult', JSON.stringify(data));
    }

    const wrap = document.createElement('div');
    wrap.innerHTML = TCCard(test_case, cardIndex).trim();
    const newCard = wrap.firstElementChild;
    if (newCard && card) card.replaceWith(newCard);
    showToast(`${tcId} regenerado`);
  } catch (e) {
    showToast('Error al regenerar: ' + e.message, 'var(--red)');
    if (btn) { btn.textContent = '⟳'; btn.disabled = false; btn.style.opacity = ''; }
  }
}

// ── Batch mode
async function generateBatch() {
  const raw     = document.getElementById('userStory').value.trim();
  const stories = raw.split(/\n---+\n/).map(s => s.trim()).filter(s => s.length >= 20);
  if (stories.length < 2) { showToast('Separa historias con "---" en línea propia', 'var(--amber)'); return; }

  const btn     = document.getElementById('generateBtn');
  const spinner = document.getElementById('spinner');
  const btnText = document.getElementById('btnText');
  btn.disabled = true;
  spinner.style.display = 'block';
  showToast(`Procesando ${stories.length} historias en lote...`, 'var(--cyan)');

  const merged = { test_cases: [], edge_scenarios: [], potential_bugs: [], coverage_summary: {} };

  for (let i = 0; i < stories.length; i++) {
    btnText.textContent = `Historia ${i + 1}/${stories.length}...`;
    try {
      const res = await fetch(API + '/generate', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_story:  stories[i],
          model:       document.getElementById('modelSelect').value,
          context:     document.getElementById('context').value,
          temperature: parseFloat(document.getElementById('tempSlider').value),
          use_rag:     document.getElementById('ragToggle')?.checked ?? false,
        }),
      });
      if (!res.ok) continue;
      const r = await res.json();
      (r.test_cases || []).forEach((tc, j) => {
        tc.id = `B${i + 1}-TC-${String(j + 1).padStart(3, '0')}`;
        merged.test_cases.push(tc);
      });
      (r.edge_scenarios || []).forEach((e, j) => {
        e.id = `B${i + 1}-ES-${String(j + 1).padStart(3, '0')}`;
        merged.edge_scenarios.push(e);
      });
      (r.potential_bugs || []).forEach((b, j) => {
        b.id = `B${i + 1}-BUG-${String(j + 1).padStart(3, '0')}`;
        merged.potential_bugs.push(b);
      });
    } catch { /* continúa con la siguiente */ }
  }

  const cats = [...new Set(merged.test_cases.map(tc => tc.category).filter(Boolean))];
  merged.coverage_summary = {
    total_test_cases: merged.test_cases.length,
    categories_covered: cats,
    estimated_coverage_percent: Math.min(95, 50 + merged.test_cases.length * 2),
    missing_areas: [],
  };

  data = merged;
  localStorage.setItem('lastResult', JSON.stringify(data));
  renderResult(data);
  setWorkflowStep('evaluate');
  document.getElementById('evaluateBtn').disabled = false;
  btn.disabled = false;
  spinner.style.display = 'none';
  btnText.textContent = 'Generar casos de prueba';
  showToast(`Lote: ${merged.test_cases.length} TC de ${stories.length} historias`);
}

// ── Fusionar casos del Optimizador de Cobertura
function mergeOptimizerCases(addedCases) {
  if (!addedCases || !addedCases.length || !data) return;
  addedCases.forEach((tc, i) => {
    tc.id = tc.id || `OPT-${String(i + 1).padStart(3, '0')}`;
    data.test_cases.push(tc);
  });
  localStorage.setItem('lastResult', JSON.stringify(data));
  const cntEl = document.getElementById('cnt-tc');
  if (cntEl) cntEl.textContent = data.test_cases.length;
  showToast(`+${addedCases.length} casos añadidos por el Optimizador`, 'var(--accent2)');
}

// ── Init
loadModels();
checkRagStatus();
setWorkflowStep('input');
setInterval(loadModels, 300000);
setInterval(checkRagStatus, 300000);

// Actualizar hint de distribución cuando cambia cantidad o categorías
document.getElementById('tcCount')?.addEventListener('input', updateCatDistHint);
document.getElementById('catChecks')?.addEventListener('change', updateCatDistHint);
updateCatDistHint();

const saved = localStorage.getItem('lastResult');
if (saved) {
  try {
    data = JSON.parse(saved);
    renderResult(data);
    setWorkflowStep('evaluate');
    document.getElementById('evaluateBtn').disabled = false;
  } catch { localStorage.removeItem('lastResult'); }
}
