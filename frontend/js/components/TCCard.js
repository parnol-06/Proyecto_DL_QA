// components/TCCard.js — Fuente única de verdad para el HTML de un test case card.
// Elimina la duplicación entre renderTC() y appendTC() que existía en render.js.

function catBadge(cat) {
  return ({
    happy_path:       'badge-happy',
    edge_case:        'badge-edge',
    caso_limite:      'badge-edge',
    negativo:         'badge-negative',
    negative:         'badge-negative',
    security:         'badge-security',
    seguridad:        'badge-security',
    performance:      'badge-performance',
    rendimiento:      'badge-performance',
    usabilidad:       'badge-usabilidad',
    compatibilidad:   'badge-compatibilidad',
  })[cat] || 'badge-low';
}

function catLabel(cat) {
  return (cat || '').replace(/_/g, ' ');
}

function TCCard(tc, index) {
  const id = tc.id || 'TC-' + String(index + 1).padStart(3, '0');

  const safeCategory = (tc.category || '').replace(/'/g, "\\'");
  const safeId       = (tc.id || '').replace(/'/g, "\\'");

  const precHtml = (tc.preconditions || []).length
    ? `<div class="field-label">Precondiciones</div>
       <ul class="steps-list">
         ${tc.preconditions.map(p => `<li class="prec-item">${p}</li>`).join('')}
       </ul>`
    : '';

  return `
    <div class="tc-card" id="tc-${index}"
         data-category="${tc.category || ''}"
         data-priority="${tc.priority || ''}"
         data-tcid="${tc.id || ''}">
      <div class="tc-header" onclick="toggleCard(${index})">
        <span class="tc-id">${id}</span>
        <span class="tc-title">${tc.title}</span>
        <div class="tc-badges">
          <span class="badge ${catBadge(tc.category)}">${catLabel(tc.category)}</span>
          <span class="badge badge-${tc.priority}">${tc.priority}</span>
        </div>
        <button class="btn-regen" title="Regenerar este caso"
                onclick="event.stopPropagation();regenerateTC(${index},'${safeId}','${safeCategory}')">⟳</button>
        <span class="badge-chevron">▾</span>
      </div>
      <div class="tc-body">
        ${precHtml}
        <div class="field-label">Pasos</div>
        <ol class="steps-list">${(tc.steps || []).map(s => `<li>${s}</li>`).join('')}</ol>
        <div class="field-label">Resultado esperado</div>
        <div class="field-value">${tc.expected_result}</div>
        <div class="field-label">Tipo</div>
        <div class="field-value">${tc.test_type || 'functional'}</div>
      </div>
    </div>`;
}
