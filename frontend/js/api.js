const API = 'http://localhost:8000';

async function loadModels() {
  try {
    const res = await fetch(API + '/models');
    const json = await res.json();
    const sel = document.getElementById('modelSelect');
    sel.innerHTML = '';
    json.models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m; opt.textContent = m;
      sel.appendChild(opt);
    });
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
  try {
    const res = await fetch(API + '/model-status?model=' + encodeURIComponent(modelName));
    const json = await res.json();
    if (json.loaded) {
      dot.style.background = 'var(--green)';
      lbl.textContent = 'cargado';
    } else {
      dot.style.background = 'var(--amber)';
      lbl.textContent = 'no cargado';
    }
  } catch {
    dot.style.background = 'var(--muted)';
    lbl.textContent = '';
  }
}
