// components/WorkflowBar.js — Barra de progreso visible de las 4 fases del workflow.

const WorkflowBar = (() => {
  const STEPS = [
    { id: 'input',    label: 'Input' },
    { id: 'generate', label: 'Generando' },
    { id: 'evaluate', label: 'Evaluando' },
    { id: 'export',   label: 'Exportar' },
  ];

  function set(stepId) {
    const idx = STEPS.findIndex(s => s.id === stepId);
    STEPS.forEach((s, i) => {
      const el = document.getElementById('wf-' + s.id);
      if (!el) return;
      el.dataset.state = i < idx ? 'done' : i === idx ? 'active' : 'idle';
    });
  }

  // Muestra u oculta el contador de tiempo en un paso concreto.
  // text = null → limpia el timer.
  function timer(stepId, text) {
    const el = document.getElementById('wf-timer-' + stepId);
    if (!el) return;
    el.textContent = text ?? '';
  }

  function clearAllTimers() {
    STEPS.forEach(s => timer(s.id, null));
  }

  function reset() {
    set('input');
    clearAllTimers();
  }

  return { set, timer, clearAllTimers, reset };
})();
