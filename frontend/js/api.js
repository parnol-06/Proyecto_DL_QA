const API = 'http://localhost:8000';

// Generador async para leer un stream SSE línea a línea.
// Evita duplicar el while-loop en generate(), generateAgents() y evaluate().
async function* readSSE(response) {
  const reader  = response.body.getReader();
  const decoder = new TextDecoder();
  let   buffer  = '';
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try { yield JSON.parse(line.slice(6)); } catch { /* línea inválida, continuar */ }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

async function loadModels() {
  try {
    const res  = await fetch(API + '/models');
    const json = await res.json();

    const sel     = document.getElementById('modelSelect');
    const evalSel = document.getElementById('evalModelSelect');

    // Preservar selecciones actuales antes de reconstruir las listas
    const prevModel = sel.value;
    const prevEval  = evalSel ? evalSel.value : '';

    sel.innerHTML = '';
    if (evalSel) {
      evalSel.innerHTML = '<option value="">— mismo que generación —</option>';
    }

    if (!json.ollama_available || json.models.length === 0) {
      const opt = document.createElement('option');
      opt.value = '';
      opt.textContent = json.ollama_available ? 'Sin modelos descargados' : 'Ollama no disponible';
      opt.disabled = true;
      sel.appendChild(opt);
      document.getElementById('statusDot').style.background = 'var(--amber)';
      const badge = document.getElementById('modelBadge');
      if (badge) badge.textContent = '—';
      return;
    }

    json.models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m; opt.textContent = m;
      sel.appendChild(opt);

      if (evalSel) {
        const opt2 = document.createElement('option');
        opt2.value = m; opt2.textContent = m;
        evalSel.appendChild(opt2);
      }
    });

    // Restaurar selección anterior si el modelo sigue disponible
    if (prevModel && [...sel.options].some(o => o.value === prevModel)) {
      sel.value = prevModel;
    }
    if (evalSel && prevEval && [...evalSel.options].some(o => o.value === prevEval)) {
      evalSel.value = prevEval;
    }

    document.getElementById('modelBadge').textContent = sel.value;
    loadModelStatus(sel.value);
    fetch(API + '/health')
      .then(r => r.json())
      .then(h => {
        document.getElementById('statusDot').style.background =
          h.ollama ? 'var(--green)' : 'var(--amber)';
      })
      .catch(() => {});
  } catch {
    document.getElementById('statusDot').style.background = 'var(--red)';
  }
}

async function loadModelStatus(modelName) {
  const dot = document.getElementById('modelLoadDot');
  const lbl = document.getElementById('modelLoadLabel');
  if (!dot || !lbl) return;

  // Limpiar botón de descarga previo si existe
  const prev = document.getElementById('pullModelBtn');
  if (prev) prev.remove();

  try {
    const res = await fetch(API + '/model-status?model=' + encodeURIComponent(modelName));
    const json = await res.json();
    if (json.loaded) {
      dot.style.background = 'var(--green)';
      lbl.textContent = 'disponible';
    } else {
      dot.style.background = 'var(--amber)';
      lbl.textContent = 'no descargado';
      const btn = document.createElement('button');
      btn.id = 'pullModelBtn';
      btn.textContent = '⬇ Descargar';
      btn.style.cssText = 'font-size:10px;padding:2px 8px;background:var(--accent);color:#fff;border:none;border-radius:4px;cursor:pointer;margin-left:6px';
      btn.onclick = () => pullModel(modelName);
      lbl.parentElement.appendChild(btn);
    }
  } catch {
    dot.style.background = 'var(--muted)';
    lbl.textContent = '';
  }
}

async function pullModel(modelName) {
  const btn = document.getElementById('pullModelBtn');
  if (btn) { btn.textContent = 'Descargando...'; btn.disabled = true; }
  if (typeof showToast === 'function') showToast(`Descargando ${modelName}... (puede tardar varios minutos)`, 'var(--cyan)');
  try {
    const res = await fetch(API + '/pull-model', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: modelName }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'Error al descargar');
    if (typeof showToast === 'function') showToast(`${modelName} descargado correctamente`, 'var(--green)');
    loadModelStatus(modelName);
  } catch (e) {
    if (typeof showToast === 'function') showToast('Error descargando modelo: ' + e.message, 'var(--red)');
    if (btn) { btn.textContent = '⬇ Descargar'; btn.disabled = false; }
  }
}
