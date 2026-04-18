let data = null;
let _streamTokenCount = 0;
let _streamCaseCount  = 0;

// ── UI helpers
function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.getElementById('panel-' + name).classList.add('active');
}

function toggleCard(id) {
  document.getElementById('tc-' + id).classList.toggle('open');
}

function showToast(msg, color = 'var(--green)') {
  const toast = document.getElementById('toast');
  document.getElementById('toastMsg').textContent = msg;
  document.getElementById('toastDot').style.background = color;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 3000);
}

// ── Clear / Reset
function clearAll() {
  data = null;
  localStorage.removeItem('lastResult');
  document.getElementById('userStory').value  = '';
  document.getElementById('context').value    = '';
  document.getElementById('tc-list').innerHTML    = '';
  document.getElementById('edge-list').innerHTML  = '';
  document.getElementById('bug-list').innerHTML   = '';
  document.getElementById('cov-content').style.display = 'none';
  ['tc','edge','bugs'].forEach(k => {
    document.getElementById('cnt-' + k).textContent = '0';
    document.getElementById('empty-' + k).style.display = 'flex';
  });
  document.getElementById('empty-cov').style.display = 'flex';
  document.getElementById('exportBar').classList.remove('visible');
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
  document.getElementById('evaluateBtn').disabled = true;
  ['cov','rel','con'].forEach(k => {
    document.getElementById('bar-' + k).style.width = '0%';
    const s = document.getElementById('score-' + k);
    s.textContent = '—'; s.style.color = 'var(--muted)';
  });
  const note = document.getElementById('metrics-note');
  if (note) note.style.display = 'none';
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
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url  = URL.createObjectURL(blob);
  const a    = Object.assign(document.createElement('a'), { href: url, download: 'test-cases.json' });
  a.click(); URL.revokeObjectURL(url);
}

function downloadCSV() {
  if (!data) return;
  const header = ['ID', 'Categoría', 'Título', 'Pasos', 'Resultado esperado', 'Prioridad'];
  const rows   = (data.test_cases || []).map(tc => [
    tc.id || '', tc.category || '', tc.title || '',
    (tc.steps || []).join(' | '), tc.expected_result || '', tc.priority || '',
  ].map(v => `"${String(v).replace(/"/g, '""')}"`));
  const csv  = [header, ...rows].map(r => r.join(',')).join('\r\n');
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' });
  const url  = URL.createObjectURL(blob);
  const a    = Object.assign(document.createElement('a'), { href: url, download: 'test-cases.csv' });
  a.click(); URL.revokeObjectURL(url);
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
    lines.push('## ' + cat.replace(/_/g, ' ').toUpperCase());
    lines.push('');
    tcs.forEach(tc => {
      lines.push('### ' + (tc.id || '') + ' · ' + tc.title);
      lines.push('');
      lines.push('**Prioridad:** ' + (tc.priority || ''));
      lines.push('');
      if (tc.preconditions && tc.preconditions.length) {
        lines.push('**Precondiciones:**');
        tc.preconditions.forEach(p => lines.push('- ' + p));
        lines.push('');
      }
      lines.push('**Pasos:**');
      (tc.steps || []).forEach((s, i) => lines.push((i+1) + '. ' + s));
      lines.push('');
      lines.push('> **Resultado esperado:** ' + tc.expected_result);
      lines.push('');
    });
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement('a'), { href: url, download: 'test-cases.md' });
  a.click(); URL.revokeObjectURL(url);
}

// ── Streaming helpers
function showStreamPreview() {
  _streamTokenCount = 0;
  _streamCaseCount  = 0;
  document.getElementById('streamPreview').classList.add('visible');
  document.getElementById('streamText').textContent = 'Iniciando generación...';
  document.getElementById('empty-tc').style.display = 'none';
  document.getElementById('tc-list').style.display = 'none';
}

function hideStreamPreview() {
  document.getElementById('streamPreview').classList.remove('visible');
  document.getElementById('streamText').textContent = '';
}

function appendStreamToken(token) {
  _streamTokenCount++;
  // Cuenta cuántos IDs de caso aparecen (patrones como "TC-001")
  const matches = token.match(/"id"\s*:\s*"TC-/g);
  if (matches) _streamCaseCount += matches.length;

  const el = document.getElementById('streamText');
  const cases = _streamCaseCount > 0 ? ` · ${_streamCaseCount} casos detectados` : '';
  el.textContent = `Procesando respuesta del modelo... ${_streamTokenCount} tokens recibidos${cases}`;
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
  login: {
    label: 'Login con email y contraseña',
    story: 'Como usuario registrado quiero poder iniciar sesión con mi email y contraseña para acceder a mi cuenta personal.',
    context: 'El sistema debe bloquear la cuenta tras 3 intentos fallidos y enviar email de recuperación.'
  },
  registro: {
    label: 'Registro de nuevo usuario',
    story: 'Como visitante quiero poder registrarme en la plataforma proporcionando nombre, email y contraseña para crear mi cuenta.',
    context: 'El email debe ser único en el sistema. La contraseña debe tener mínimo 8 caracteres.'
  },
  checkout: {
    label: 'Proceso de pago (Checkout)',
    story: 'Como cliente quiero poder completar una compra seleccionando método de pago y dirección de envío para recibir mi pedido.',
    context: 'Integración con pasarela de pago. Se debe validar stock antes de confirmar.'
  },
  busqueda: {
    label: 'Búsqueda de productos',
    story: 'Como usuario quiero buscar productos por nombre, categoría o precio para encontrar lo que necesito rápidamente.',
    context: 'El buscador debe soportar filtros combinados y ordenamiento por relevancia, precio y valoración.'
  },
  upload: {
    label: 'Subir archivos',
    story: 'Como usuario quiero poder subir documentos al sistema para adjuntarlos a mis solicitudes.',
    context: 'Formatos permitidos: PDF, DOCX, PNG, JPG. Tamaño máximo: 10MB por archivo.'
  },
  recuperacion: {
    label: 'Recuperación de contraseña',
    story: 'Como usuario que olvidó su contraseña quiero recibir un enlace de recuperación en mi email para restablecer el acceso a mi cuenta.',
    context: 'El enlace debe expirar en 30 minutos. Solo puede usarse una vez.'
  },
  perfil: {
    label: 'Editar perfil de usuario',
    story: 'Como usuario autenticado quiero poder editar mis datos de perfil (nombre, foto, teléfono) para mantener mi información actualizada.',
    context: 'Los cambios deben reflejarse inmediatamente en la UI sin recargar la página.'
  },
  notificaciones: {
    label: 'Sistema de notificaciones',
    story: 'Como usuario quiero recibir notificaciones en tiempo real sobre el estado de mis pedidos para estar informado sin tener que consultar manualmente.',
    context: 'Las notificaciones deben aparecer en la barra superior y también enviarse por email según preferencias del usuario.'
  }
};

function loadTemplate(key) {
  if (!key || !TEMPLATES[key]) return;
  const t = TEMPLATES[key];
  document.getElementById('userStory').value = t.story;
  document.getElementById('context').value = t.context;
}

// ── Filter TC
let _activeCategory = '';
let _activePriority = '';

function filterTC(type, value) {
  if (type === 'category') _activeCategory = (_activeCategory === value ? '' : value);
  if (type === 'priority')  _activePriority = (_activePriority === value ? '' : value);

  document.querySelectorAll('#filterCats .chip').forEach(c => {
    c.classList.toggle('active', c.dataset.value === _activeCategory && _activeCategory !== '');
  });
  document.querySelectorAll('#filterPrios .chip').forEach(c => {
    c.classList.toggle('active', c.dataset.value === _activePriority && _activePriority !== '');
  });

  document.querySelectorAll('#tc-list .tc-card').forEach(card => {
    const matchCat  = !_activeCategory || card.dataset.category === _activeCategory;
    const matchPrio = !_activePriority  || card.dataset.priority  === _activePriority;
    card.style.display = (matchCat && matchPrio) ? '' : 'none';
  });
}

// ── Generate (streaming)
async function generate() {
  const story = document.getElementById('userStory').value.trim();
  if (!story) { showToast('Escribe una historia de usuario primero', 'var(--amber)'); return; }

  const btn     = document.getElementById('generateBtn');
  const spinner = document.getElementById('spinner');
  const btnText = document.getElementById('btnText');
  btn.disabled  = true;
  spinner.style.display = 'block';
  btnText.textContent   = 'Generando...';
  document.getElementById('evaluateBtn').disabled = true;

  const _t0 = Date.now();
  let _timerInterval;

  switchTab('tc');
  showStreamPreview();
  _timerInterval = setInterval(() => {
    const s = Math.round((Date.now() - _t0) / 1000);
    document.getElementById('btnText').textContent = 'Generando... ' + s + 's';
  }, 1000);

  try {
    const res = await fetch(API + '/generate/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_story: story,
        model:   document.getElementById('modelSelect').value,
        context: document.getElementById('context').value,
        temperature: parseFloat(document.getElementById('tempSlider').value),
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Error del servidor');
    }

    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    let   buffer  = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const msg = JSON.parse(line.slice(6));
          if (msg.token !== undefined) {
            appendStreamToken(msg.token);
          } else if (msg.result) {
            data = msg.result;
            localStorage.setItem('lastResult', JSON.stringify(data));
            hideStreamPreview();
            renderResult(data);
            const elapsed = Math.round((Date.now() - _t0) / 1000);
            showToast(`${(data.test_cases||[]).length} casos generados en ${elapsed}s`);
            document.getElementById('evaluateBtn').disabled = false;
          } else if (msg.error) {
            throw new Error(msg.error);
          }
        } catch (e) {
          if (e.message && !e.message.startsWith('JSON')) throw e;
        }
      }
    }

  } catch (e) {
    hideStreamPreview();
    showToast('Error: ' + e.message, 'var(--red)');
  } finally {
    clearInterval(_timerInterval);
    btn.disabled = false;
    spinner.style.display = 'none';
    btnText.textContent   = 'Generar casos de prueba';
  }
}

// ── Evaluate (DeepEval real)
async function evaluate() {
  if (!data) return;
  const story = document.getElementById('userStory').value.trim();
  if (!story) { showToast('Necesitas una historia de usuario para evaluar', 'var(--amber)'); return; }

  const btn = document.getElementById('evaluateBtn');
  btn.disabled = true;
  btn.querySelector('span').textContent = '⟳';
  showToast('Evaluando con DeepEval (~30-60s)...', 'var(--cyan)');

  try {
    const res = await fetch(API + '/evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        requirement: story,
        generated_output: data,
        model: document.getElementById('modelSelect').value,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Error de evaluación');
    }

    const scores = await res.json();
    setMetric('cov', scores.coverage);
    setMetric('rel', scores.relevancy);
    setMetric('con', scores.consistency);
    showToast(`Evaluación completa · overall ${scores.overall.toFixed(2)}`);

  } catch (e) {
    showToast('Error: ' + e.message, 'var(--red)');
  } finally {
    btn.disabled = false;
    btn.querySelector('span').textContent = '◈';
  }
}

// ── Init
loadModels();
setInterval(loadModels, 30000);
const saved = localStorage.getItem('lastResult');
if (saved) {
  try {
    data = JSON.parse(saved);
    renderResult(data);
    document.getElementById('evaluateBtn').disabled = false;
  } catch { localStorage.removeItem('lastResult'); }
}
