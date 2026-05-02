// store.js — Estado global centralizado (pub-sub simple, sin framework)
const Store = (() => {
  const _state = {
    result:           null,
    agentMode:        false,
    streaming:        false,
    metrics:          null,
    metricsEstimated: false,
    filters:          { category: '', priority: '' },
    workflowStep:     'input',   // input | generate | evaluate | export
  };

  const _subs = {};

  function get(key) {
    return _state[key];
  }

  function set(key, value) {
    _state[key] = value;
    (_subs[key] || []).forEach(fn => fn(value));
  }

  function on(key, fn) {
    if (!_subs[key]) _subs[key] = [];
    _subs[key].push(fn);
    return () => { _subs[key] = _subs[key].filter(f => f !== fn); };
  }

  function reset() {
    set('result', null);
    set('metrics', null);
    set('metricsEstimated', false);
    set('streaming', false);
    set('workflowStep', 'input');
    set('filters', { category: '', priority: '' });
  }

  return { get, set, on, reset };
})();
