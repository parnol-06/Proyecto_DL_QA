// components/WorkflowBar.js — Barra de progreso visible de las 4 fases del workflow.
// Reemplaza los 4 divs ocultos que setWorkflowStep() manipulaba sin efecto visual.

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

  function reset() { set('input'); }

  return { set, reset };
})();
