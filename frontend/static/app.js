'use strict';

const USER_ID = 6;

const PHASE_LABEL = {
  night: '夜晚',
  day: '白天',
  discussion: '讨论环节',
  voting: '投票环节',
  count_votes: '计票环节',
};

const PHASE_ALIAS = {
  night: 'night',
  day: 'day',
  discussion: 'discussion',
  voting: 'voting',
  count_votes: 'count_votes',
  夜晚: 'night',
  白天: 'day',
  讨论: 'discussion',
  讨论环节: 'discussion',
  投票: 'voting',
  投票环节: 'voting',
  计票: 'count_votes',
  计票环节: 'count_votes',
};

const ROLE_LABEL = {
  werewolf: '狼人',
  villager: '平民',
  seer: '预言家',
  witch: '女巫',
};

const ACTION_META = {
  kill: { label: '刀人', hint: '选择一名玩家，结束他的今晚', tone: 'danger' },
  check: { label: '查验', hint: '看清一名玩家的真实身份', tone: 'mystic' },
  resurrection: { label: '救人', hint: '用解药留住濒死的人', tone: 'good' },
  conversation: { label: '密谈', hint: '只说给狼队友听', tone: 'whisper' },
  none: { label: '跳过', hint: '什么也不做，闭上眼睛', tone: 'quiet' },
};

const AIM_TITLE = {
  kill: '选择刀口',
  check: '选择查验对象',
  resurrection: '选择要救的人',
  conversation: '选择队友',
  none: '什么也不做',
};

const state = {
  gameId: null,
  userRole: '',
  userRoleLabel: '',
  day: null,
  phase: '',
  alive: null,
  seatCount: 6,
  mode: 'lobby',
  winner: '',
  actions: [],
  targets: {},
  votes: [],
  selectedAction: null,
  selectedTarget: null,
  draft: '',
  speakingId: null,
  promptKind: 'act',
  sending: false,
  starting: false,
  reviewOpen: false,
  eventSource: null,
  streams: new Map(),
  lastErrorToast: 0,
};

const dom = {
  statusLine: document.getElementById('statusLine'),
  dayNum: document.getElementById('dayNum'),
  phaseChip: document.getElementById('phaseChip'),
  aliveChip: document.getElementById('aliveChip'),
  roleBoard: document.getElementById('roleBoard'),
  roleName: document.getElementById('roleName'),
  startBtn: document.getElementById('startBtn'),
  resetBtn: document.getElementById('resetBtn'),
  endBtn: document.getElementById('endBtn'),
  reviewBtn: document.getElementById('reviewBtn'),
  seatStat: document.getElementById('seatStat'),
  seatList: document.getElementById('seatList'),
  log: document.getElementById('log'),
  actionKicker: document.getElementById('actionKicker'),
  actionTitle: document.getElementById('actionTitle'),
  actionBody: document.getElementById('actionBody'),
  backdrop: document.getElementById('backdrop'),
  drawer: document.getElementById('reviewDrawer'),
  reviewMeta: document.getElementById('reviewMeta'),
  reviewList: document.getElementById('reviewList'),
  reviewClose: document.getElementById('reviewClose'),
  reviewRefresh: document.getElementById('reviewRefresh'),
  phaseBanner: document.getElementById('phaseBanner'),
  toast: document.getElementById('toast'),
};

function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  if (attrs) {
    for (const [key, value] of Object.entries(attrs)) {
      if (value == null || value === false) continue;
      if (key === 'class') node.className = value;
      else if (key === 'text') node.textContent = value;
      else node.setAttribute(key, value === true ? '' : String(value));
    }
  }
  for (const child of children) {
    if (child == null || child === false) continue;
    node.append(child);
  }
  return node;
}

function phaseKey(phase) {
  if (phase == null) return '';
  let raw = phase;
  if (typeof phase === 'object') raw = phase.value || phase.name || '';
  raw = String(raw);
  return PHASE_ALIAS[raw] || raw;
}

function phaseLabel(phase) {
  const key = phaseKey(phase);
  return PHASE_LABEL[key] || key || '未知环节';
}

function uniqNums(list) {
  const out = [];
  if (!Array.isArray(list)) return out;
  for (const item of list) {
    const n = Number(item);
    if (!Number.isInteger(n)) continue;
    if (!out.includes(n)) out.push(n);
  }
  out.sort((a, b) => a - b);
  return out;
}

function noteSeatCount(ids) {
  for (const id of ids || []) {
    if (id > state.seatCount) state.seatCount = id;
  }
}

function detailOf(data) {
  if (!data) return '';
  if (typeof data.detail === 'string') return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail.map((item) => item.msg || JSON.stringify(item)).join('；');
  }
  return '';
}

let toastTimer = 0;
function toast(message) {
  dom.toast.textContent = message;
  dom.toast.classList.add('is-on');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => dom.toast.classList.remove('is-on'), 2800);
}

let flashTimer = 0;
function flashPhase(text) {
  dom.phaseBanner.textContent = text;
  dom.phaseBanner.classList.add('is-on');
  clearTimeout(flashTimer);
  flashTimer = setTimeout(() => dom.phaseBanner.classList.remove('is-on'), 1400);
}

function setAtmosphereFromPhase(phase) {
  const key = phaseKey(phase);
  if (!key) return;
  const next = key === 'night' ? 'night' : 'day';
  const prev = document.documentElement.dataset.atmosphere || 'lobby';
  state.phase = key;
  document.documentElement.dataset.phase = key;
  document.documentElement.dataset.atmosphere = next;
  if (prev !== next) flashPhase(next === 'night' ? '夜幕降临' : '天亮了');
}

function setRole(raw) {
  state.userRole = raw || '';
  state.userRoleLabel = ROLE_LABEL[raw] || raw || '';
}

function toneFor(text) {
  const value = String(text || '');
  if (/没有人死亡|平安/.test(value)) return 'good';
  if (/杀死|出局|死亡/.test(value)) return 'danger';
  if (/复活|拯救|救了/.test(value)) return 'good';
  if (/身份|查验|检查/.test(value)) return 'mystic';
  if (/投票/.test(value)) return 'vote';
  return 'info';
}

function updateChrome() {
  dom.dayNum.textContent = state.day == null ? '—' : String(state.day);
  dom.phaseChip.dataset.phase = state.phase || 'lobby';
  dom.phaseChip.textContent = state.phase ? phaseLabel(state.phase) : '等待开局';
  dom.roleName.textContent = state.userRoleLabel || '未发牌';
  dom.roleBoard.dataset.role = state.userRole || 'none';

  const aliveN = Array.isArray(state.alive) ? state.alive.length : null;
  dom.aliveChip.textContent = aliveN == null ? '存活 —' : `存活 ${aliveN}`;
  const outN = aliveN == null ? null : Math.max(state.seatCount - aliveN, 0);
  dom.seatStat.textContent = aliveN == null ? '等待入座' : `存活 ${aliveN} · 出局 ${outN}`;

  if (state.mode === 'over') {
    dom.statusLine.textContent = state.winner ? `游戏已结束 · ${state.winner}胜利` : '游戏已结束';
  } else if (!state.gameId) {
    dom.statusLine.textContent = '未开始游戏';
  } else {
    dom.statusLine.textContent = '游戏进行中';
  }

  document.title = !state.gameId
    ? '狼人杀'
    : `狼人杀 · 第${state.day || 1}天${state.phase ? phaseLabel(state.phase) : ''}`;

  dom.startBtn.disabled = state.starting;
  dom.resetBtn.disabled = !state.gameId || state.starting;
  dom.endBtn.disabled = !state.gameId || state.mode === 'over' || state.starting;
  dom.reviewBtn.disabled = !state.gameId;
}

function renderSeats() {
  dom.seatList.replaceChildren();
  const aliveKnown = Array.isArray(state.alive);
  for (let id = 1; id <= state.seatCount; id += 1) {
    const alive = aliveKnown ? state.alive.includes(id) : null;
    const classes = ['seat'];
    if (id === USER_ID) classes.push('is-self');
    if (alive === true) classes.push('is-alive');
    else if (alive === false) classes.push('is-dead');
    else classes.push('is-unknown');
    if (state.speakingId === id) classes.push('is-speaking');
    if (state.selectedTarget === id && (state.mode === 'act' || state.mode === 'vote')) classes.push('is-target');
    if ((state.mode === 'speak' || state.mode === 'act' || state.mode === 'vote') && id === USER_ID) {
      classes.push('is-turn');
    }
    const status = alive === true ? '存活' : alive === false ? '出局' : '未入席';
    const name = id === USER_ID ? '你' : `玩家${id}`;
    const seat = el('div', {
      class: classes.join(' '),
      role: 'listitem',
      'aria-label': `${name}，${id}号，${status}`,
    });
    seat.append(el('span', { class: 'medal', text: String(id) }));
    const body = el('div', { class: 'seat-body' });
    body.append(el('div', { class: 'seat-name', text: name }));
    body.append(el('div', { class: 'seat-meta', text: `${id}号 · ${status}` }));
    const side = el('div', { class: 'seat-side' });
    side.append(el('span', { class: 'you-badge', text: '你' }));
    side.append(el('span', { class: 'lamp', 'aria-hidden': 'true' }));
    side.append(el('span', { class: 'stamp', text: '出局' }));
    seat.append(body, side);
    dom.seatList.append(seat);
  }
}

function scrollLog() {
  const box = dom.log;
  const distance = box.scrollHeight - box.scrollTop - box.clientHeight;
  if (distance < 140) box.scrollTop = box.scrollHeight;
}

function removeEmpty() {
  const empty = dom.log.querySelector('.empty');
  if (empty) empty.remove();
}

function setEmpty(title, sub) {
  const box = el('div', { class: 'empty' });
  box.append(
    el('img', { src: '/static/werewolf.png', alt: '' }),
    el('p', { class: 'empty-title', text: title }),
    el('p', { text: sub }),
  );
  dom.log.replaceChildren(box);
}

function appendSystem(text, phase) {
  if (!text) return;
  removeEmpty();
  const row = el('div', { class: `entry entry-system tone-${toneFor(text)}` });
  const label = phaseLabel(phase || state.phase);
  if (label && label !== '未知环节') row.append(el('span', { class: 'pill', text: label }));
  row.append(el('span', { class: 'sys-text', text }));
  dom.log.append(row);
  scrollLog();
}

function appendFinish(text) {
  removeEmpty();
  dom.log.append(el('div', { class: 'entry entry-finish', text }));
  scrollLog();
}

function appendWhisper(data) {
  removeEmpty();
  const who = data.source ? `玩家${data.source}` : '队友';
  const head = el('header', { class: 'entry-head' });
  head.append(el('span', { class: 'who', text: who }), el('span', { class: 'tag', text: '密谈' }));
  const article = el('article', { class: 'entry entry-whisper' }, head, el('p', { class: 'body', text: data.content || '' }));
  dom.log.append(article);
  scrollLog();
}

function echoLocal(echo) {
  removeEmpty();
  const head = el('header', { class: 'entry-head' });
  head.append(el('span', { class: 'who-medal', text: String(USER_ID) }));
  head.append(el('span', { class: 'who', text: '你' }));
  head.append(el('span', { class: 'tag', text: echo.kind === 'whisper' ? `对玩家${echo.target}` : '发言' }));
  const article = el(
    'article',
    { class: echo.kind === 'whisper' ? 'entry entry-me entry-whisper' : 'entry entry-me' },
    head,
    el('p', { class: 'body', text: echo.content }),
  );
  dom.log.append(article);
  scrollLog();
  return article;
}

function createSpeakEntry(playerId, mid) {
  const id = Number(playerId);
  const mine = id === USER_ID;
  const head = el('header', { class: 'entry-head' });
  head.append(el('span', { class: 'who-medal', text: String(id) }));
  head.append(el('span', { class: 'who', text: mine ? '你' : `玩家${id}` }));
  head.append(el('span', { class: 'tag', text: '发言' }));
  const body = el('p', { class: 'body is-streaming' });
  body.dataset.mid = mid;
  const article = el('article', { class: mine ? 'entry entry-me' : 'entry entry-speak' }, head, body);
  removeEmpty();
  dom.log.append(article);
  return body;
}

function handleSpeak(data) {
  if (data.content === 'FINISH') {
    const node = data.mid ? state.streams.get(data.mid) : null;
    if (node) node.classList.remove('is-streaming');
    const changed = state.speakingId !== null;
    state.speakingId = null;
    return changed;
  }
  if (!data.content) return false;
  const mid = data.mid || `p${data.id}`;
  let node = state.streams.get(mid);
  let changed = false;
  if (!node) {
    node = createSpeakEntry(data.id, mid);
    state.streams.set(mid, node);
    const speaker = Number(data.id);
    if (state.speakingId !== speaker) {
      state.speakingId = speaker;
      changed = true;
    }
  }
  node.textContent += data.content;
  scrollLog();
  return changed;
}

function noteClock(data) {
  if (data.day != null) state.day = data.day;
  if (data.phase) setAtmosphereFromPhase(data.phase);
  if (!Array.isArray(data.alive)) return false;
  const next = uniqNums(data.alive);
  noteSeatCount(next);
  const prev = Array.isArray(state.alive) ? state.alive.join(',') : '';
  state.alive = next;
  return prev !== next.join(',');
}

function waitingCopy() {
  switch (state.phase) {
    case 'night': return '夜还没轮到你。其他角色正在睁眼。';
    case 'day': return '天亮了，先看战报里的昨夜结果。';
    case 'discussion': return '还没到你。听别人把话说完。';
    case 'voting': return '别人正在投票。';
    case 'count_votes': return '正在唱票。';
    default: return '牌桌安静，等下一件事发生。';
  }
}

function actHint(actions, type) {
  if (type === 'conversation') return '队友在等你。可以回一句密谈，也可以直接动手。';
  const has = (name) => actions.includes(name);
  if (has('check')) return '选一名玩家，看清他的身份。';
  if (has('resurrection') && has('kill')) return '你可以救人、下毒，或什么都不做。';
  if (has('resurrection')) return '你可以救人，或什么都不做。';
  if (has('kill') && has('none')) return '你可以下毒，或什么都不做。';
  if (has('conversation') && has('kill')) return '先和队友通气，或直接选出刀口。';
  if (has('kill')) return '选择今晚的目标。';
  if (has('none')) return '今晚没有别的手段了。';
  return '请选择你的行动';
}

function setHead(kicker, title) {
  dom.actionKicker.textContent = kicker;
  dom.actionTitle.textContent = title;
}

function chip(id, pressed) {
  const dead = Array.isArray(state.alive) && !state.alive.includes(id);
  const btn = el('button', {
    type: 'button',
    class: `target-chip${pressed ? ' is-selected' : ''}${dead ? ' is-dead' : ''}${id === USER_ID ? ' is-self' : ''}`,
    'data-target': String(id),
    'aria-pressed': pressed ? 'true' : 'false',
  });
  btn.append(el('span', { class: 'num', text: String(id) }));
  btn.append(el('span', { class: 'who', text: id === USER_ID ? '你' : (dead ? '出局' : '玩家') }));
  return btn;
}

function targetGrid(ids) {
  const grid = el('div', { class: 'target-grid' });
  if (!ids.length) {
    grid.append(el('p', { class: 'hint', text: '没有可选的玩家。' }));
    return grid;
  }
  ids.forEach((id) => grid.append(chip(id, id === state.selectedTarget)));
  return grid;
}

function actionGrid(actions) {
  const grid = el('div', { class: 'action-grid' });
  actions.forEach((name) => {
    const meta = ACTION_META[name] || { label: name, hint: '执行此行动', tone: 'quiet' };
    const btn = el('button', {
      type: 'button',
      class: `action-card tone-${meta.tone}`,
      'data-action': name,
    });
    btn.append(el('strong', { text: meta.label }), el('span', { text: meta.hint }));
    grid.append(btn);
  });
  if (actions.length % 2 === 1 && grid.lastElementChild) grid.lastElementChild.classList.add('span-2');
  return grid;
}

function draftBox(placeholder, rows) {
  const area = el('textarea', {
    class: 'draft',
    placeholder,
    maxlength: '200',
    rows: String(rows || 4),
    spellcheck: 'false',
  });
  return el(
    'div',
    { class: 'draft-wrap' },
    area,
    el('div', { class: 'counter', text: '0/200' }),
    el('p', { class: 'keyhint', text: 'Enter 发送 · Shift+Enter 换行' }),
  );
}

function submitRow() {
  return el('div', { class: 'submit-row' }, el('button', {
    type: 'button',
    class: 'btn btn-primary',
    'data-submit': '1',
    text: '确认',
  }));
}

function confirmLabel() {
  const id = state.selectedTarget;
  const who = id ? (id === USER_ID ? '你' : `${id}号`) : '';
  if (state.mode === 'speak') return '发言';
  if (state.mode === 'vote') return who ? `投给${who}` : '投票';
  if (state.selectedAction === 'kill') return who ? `刀${who}` : '确认刀人';
  if (state.selectedAction === 'check') return who ? `查验${who}` : '确认查验';
  if (state.selectedAction === 'resurrection') return who ? `救${who}` : '确认救人';
  if (state.selectedAction === 'conversation') return who ? `告诉${who}` : '送出密谈';
  if (state.selectedAction === 'none') return '什么也不做';
  return '确认';
}

function buildPayload() {
  if (!state.gameId) return { error: '请先开始游戏' };
  if (state.mode === 'speak') {
    const content = (state.draft || '').trim();
    if (!content) return { error: '先写下你的发言' };
    return { payload: { etype: 'SPEAK', content }, echo: { kind: 'speak', content } };
  }
  if (state.mode === 'vote') {
    if (!state.selectedTarget) return { error: '请选择投票对象' };
    const reason = (state.draft || '').trim() || '投票决定';
    return { payload: { etype: 'VOTE', source: USER_ID, target: state.selectedTarget, reason } };
  }
  if (state.mode === 'act') {
    const action = state.selectedAction;
    if (!action) return { error: '请选择行动' };
    if (action === 'none') return { payload: { etype: 'NONE' } };
    if (!state.selectedTarget) return { error: '请选择目标玩家' };
    const target = state.selectedTarget;
    if (action === 'conversation') {
      const content = (state.draft || '').trim();
      if (!content) return { error: '写下要对队友说的话' };
      return {
        payload: { etype: 'CONVERSATION', source: USER_ID, target, content },
        echo: { kind: 'whisper', content, target },
      };
    }
    if (action === 'kill') return { payload: { etype: 'KILL', source: USER_ID, target, reason: '狼人杀人' } };
    if (action === 'resurrection') return { payload: { etype: 'RESURRECTION', source: USER_ID, target, reason: '女巫救人' } };
    if (action === 'check') return { payload: { etype: 'CHECK', source: USER_ID, target, reason: '查验身份' } };
    return { error: '无法识别的行动' };
  }
  return { error: '现在不能操作' };
}

function syncDraftUi() {
  const counter = dom.actionBody.querySelector('.counter');
  const submit = dom.actionBody.querySelector('[data-submit]');
  if (counter) counter.textContent = `${(state.draft || '').length}/200`;
  if (submit) {
    submit.disabled = state.sending || Boolean(buildPayload().error);
    submit.textContent = confirmLabel();
  }
}

function finishDraft(focus) {
  const draft = dom.actionBody.querySelector('.draft');
  if (draft) draft.value = state.draft || '';
  syncDraftUi();
  if (focus && draft && !state.reviewOpen) draft.focus();
}

function renderAction() {
  const body = dom.actionBody;
  body.replaceChildren();
  if (state.mode === 'lobby') {
    setHead('牌桌', '尚未开局');
    body.append(el('p', { class: 'hint', text: '你固定坐在 6 号。天黑后只做这一夜允许的事，天亮发言，再投票。' }));
    body.append(el('button', { type: 'button', class: 'btn btn-primary btn-block', 'data-start': '1', text: '开始游戏' }));
    return;
  }
  if (state.mode === 'waiting') {
    setHead(state.phase ? phaseLabel(state.phase) : '牌桌', '请稍候');
    body.append(el(
      'div',
      { class: 'wait-row' },
      el('span', { class: 'wait-orb', 'aria-hidden': 'true' }),
      el('p', { class: 'hint', text: waitingCopy() }),
    ));
    return;
  }
  if (state.mode === 'over') {
    setHead('终局', '对局结束');
    body.append(el('p', { class: 'hint', text: state.winner ? `胜利方：${state.winner}` : '这局已经停下。' }));
    body.append(el(
      'div',
      { class: 'submit-row' },
      el('button', { type: 'button', class: 'btn btn-ghost', 'data-review': '1', text: '复盘' }),
      el('button', { type: 'button', class: 'btn btn-primary', 'data-reset': '1', text: '再来一局' }),
    ));
    return;
  }
  if (state.mode === 'speak') {
    setHead('讨论', '轮到你发言');
    body.append(el('p', { class: 'hint', text: '写下你的判断。发出后会立刻出现在战报里。' }));
    body.append(draftBox('把你的判断说给牌桌……'));
    body.append(submitRow());
    finishDraft(true);
    return;
  }
  if (state.mode === 'vote') {
    setHead('投票', '投票放逐');
    body.append(el('p', { class: 'hint', text: '选择一名玩家。不写理由时，记为「投票决定」。' }));
    body.append(targetGrid(state.votes));
    body.append(draftBox('投票理由（可选）', 3));
    body.append(submitRow());
    finishDraft(false);
    return;
  }
  if (state.mode !== 'act') return;

  const action = state.selectedAction;
  if (!action) {
    setHead('夜晚', '夜晚行动');
    body.append(el('p', { class: 'hint', text: actHint(state.actions, state.promptKind) }));
    if (!state.actions.length) body.append(el('p', { class: 'hint', text: '这一夜没有可执行的行动。' }));
    else body.append(actionGrid(state.actions));
    return;
  }

  const meta = ACTION_META[action] || { label: action, hint: '' };
  setHead('夜晚', AIM_TITLE[action] || meta.label);
  if (state.actions.length > 1) {
    body.append(el('button', { type: 'button', class: 'btn btn-ghost btn-back', 'data-back': '1', text: '重选行动' }));
  }
  body.append(el('p', { class: 'hint', text: meta.hint || actHint(state.actions, 'act') }));
  if (action !== 'none') body.append(targetGrid(state.targets[action] || []));
  if (action === 'conversation') body.append(draftBox('只说给队友听……'));
  body.append(submitRow());
  finishDraft(false);
}

function enterSpeak() {
  state.mode = 'speak';
  state.draft = '';
  state.selectedAction = null;
  state.selectedTarget = null;
  renderAction();
  renderSeats();
  updateChrome();
}

function enterVote(data) {
  state.mode = 'vote';
  state.votes = uniqNums(data.voting);
  noteSeatCount(state.votes);
  state.selectedAction = null;
  state.selectedTarget = null;
  state.draft = '';
  renderAction();
  renderSeats();
  updateChrome();
}

function enterAct(data, type) {
  const actions = Array.isArray(data.action) ? data.action.slice() : [];
  const targets = {};
  actions.forEach((name) => {
    targets[name] = uniqNums(data[name]);
    noteSeatCount(targets[name]);
  });
  state.mode = 'act';
  state.promptKind = type || 'act';
  state.actions = actions;
  state.targets = targets;
  state.selectedAction = actions.length === 1 ? actions[0] : null;
  state.selectedTarget = null;
  state.draft = '';
  renderAction();
  if (type === 'conversation' && state.selectedAction) {
    /* single-action nights open straight onto the target step */
  }
  renderSeats();
  updateChrome();
}

function handleServerEvent(data) {
  if (!data || typeof data !== 'object') return;
  if (data.type === 'speak') {
    noteClock(data);
    if (handleSpeak(data)) renderSeats();
    updateChrome();
    return;
  }

  noteClock(data);
  let panel = false;
  if (data.type === 'display') {
    if (data.content) appendSystem(data.content, data.phase);
  } else if (data.type === 'user_speak') {
    enterSpeak();
    panel = true;
  } else if (data.type === 'conversation') {
    appendWhisper(data);
    enterAct(data, 'conversation');
    panel = true;
  } else if (data.type === 'act') {
    if (data.content) appendSystem(data.content, data.phase);
    enterAct(data, 'act');
    panel = true;
  } else if (data.type === 'voting') {
    if (data.content) appendSystem(data.content, data.phase);
    enterVote(data);
    panel = true;
  } else if (data.type === 'finish') {
    const winner = data.winner || '未知';
    state.winner = winner;
    appendFinish(`游戏结束。胜利方：${winner}`);
    finishLocal(`游戏已结束 · ${winner}胜利`);
    panel = true;
  }
  if (!panel) renderSeats();
  updateChrome();
}

function stopStream() {
  const source = state.eventSource;
  state.eventSource = null;
  if (source) source.close();
}

function connect() {
  stopStream();
  const source = new EventSource(`/game/playing/${encodeURIComponent(state.gameId)}`);
  state.eventSource = source;
  source.onmessage = (event) => {
    if (state.eventSource !== source) return;
    try {
      handleServerEvent(JSON.parse(event.data));
    } catch (err) {
      console.error('处理 SSE 消息失败', err);
    }
  };
  source.onerror = () => {
    if (state.eventSource !== source || state.mode === 'over') return;
    const now = Date.now();
    if (now - state.lastErrorToast < 8000) return;
    state.lastErrorToast = now;
    toast('牌桌连接中断，浏览器会自动重试');
  };
}

function bootTable(data) {
  stopStream();
  if (data.game_id) state.gameId = data.game_id;
  setRole(data.user_role);
  state.day = 1;
  state.alive = [1, 2, 3, 4, 5, 6];
  state.seatCount = 6;
  state.mode = 'waiting';
  state.winner = '';
  state.actions = [];
  state.targets = {};
  state.votes = [];
  state.selectedAction = null;
  state.selectedTarget = null;
  state.draft = '';
  state.speakingId = null;
  state.promptKind = 'act';
  state.sending = false;
  state.streams.clear();
  setAtmosphereFromPhase('night');
  setEmpty('正在发牌', '夜晚的第一条消息马上会写进战报。');
  renderSeats();
  renderAction();
  updateChrome();
}

async function startGame() {
  if (state.starting) return;
  state.starting = true;
  updateChrome();
  try {
    const res = await fetch('/game/start', { cache: 'no-store' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(detailOf(data) || '未知错误');
    bootTable(data);
    connect();
  } catch (err) {
    toast(`游戏启动失败：${err.message || '未知错误'}`);
  } finally {
    state.starting = false;
    updateChrome();
  }
}

async function resetGame() {
  if (!state.gameId || state.starting) {
    if (!state.gameId) toast('请先开始游戏');
    return;
  }
  state.starting = true;
  updateChrome();
  try {
    stopStream();
    const res = await fetch(`/game/reset/${encodeURIComponent(state.gameId)}`, { cache: 'no-store' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(detailOf(data) || '未知错误');
    bootTable({ game_id: state.gameId, user_role: data.user_role });
    connect();
  } catch (err) {
    toast(`重置失败：${err.message || '未知错误'}`);
  } finally {
    state.starting = false;
    updateChrome();
  }
}

function finishLocal() {
  stopStream();
  state.mode = 'over';
  state.selectedAction = null;
  state.selectedTarget = null;
  state.speakingId = null;
  state.draft = '';
  renderAction();
  renderSeats();
  updateChrome();
}

async function endGame() {
  if (!state.gameId || state.mode === 'over') {
    if (!state.gameId) toast('请先开始游戏');
    return;
  }
  try {
    const res = await fetch(`/game/end/${encodeURIComponent(state.gameId)}`, { cache: 'no-store' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(detailOf(data) || '未知错误');
    appendSystem('你结束了这局游戏。');
    finishLocal();
  } catch (err) {
    toast(`结束失败：${err.message || '未知错误'}`);
  }
}

let reviewSeq = 0;
function openDrawer() {
  state.reviewOpen = true;
  dom.backdrop.classList.add('is-open');
  dom.drawer.classList.add('is-open');
  dom.drawer.setAttribute('aria-hidden', 'false');
  dom.drawer.inert = false;
  dom.reviewClose.focus();
}

function closeDrawer() {
  state.reviewOpen = false;
  dom.backdrop.classList.remove('is-open');
  dom.drawer.classList.remove('is-open');
  dom.drawer.setAttribute('aria-hidden', 'true');
  if (document.activeElement && dom.drawer.contains(document.activeElement)) dom.reviewBtn.focus();
  dom.drawer.inert = true;
}

function renderReview(events) {
  dom.reviewMeta.textContent = `共 ${events.length} 条`;
  dom.reviewMeta.title = state.gameId || '';
  if (!events.length) {
    dom.reviewList.replaceChildren(el('p', {
      class: 'review-empty',
      text: '还没有可复盘的记录。行动、发言和投票会按时间排在这里。',
    }));
    return;
  }
  const list = document.createDocumentFragment();
  let last = '';
  for (const event of events) {
    const day = event.day == null ? '?' : event.day;
    const key = `${day}|${phaseKey(event.phase)}`;
    if (key !== last) {
      last = key;
      list.append(el('h3', { class: 'tl-day', text: `第${day}天 · ${phaseLabel(event.phase)}` }));
    }
    const text = event.content || event.etype || '（无内容）';
    list.append(el('article', { class: `tl-item tone-${toneFor(text)}` }, el('p', { text })));
  }
  dom.reviewList.replaceChildren(list);
}

async function openReview() {
  if (!state.gameId) {
    toast('请先开始游戏');
    return;
  }
  const seq = ++reviewSeq;
  openDrawer();
  dom.reviewMeta.textContent = '正在读取';
  dom.reviewList.replaceChildren(el('p', { class: 'review-empty', text: '正在翻开记录…' }));
  try {
    const res = await fetch(`/game/review/${encodeURIComponent(state.gameId)}`, { cache: 'no-store' });
    const data = await res.json().catch(() => ({}));
    if (seq !== reviewSeq) return;
    if (!res.ok) throw new Error(detailOf(data) || '获取复盘失败');
    if (!Array.isArray(data.events)) throw new Error('复盘数据无法识别');
    renderReview(data.events);
  } catch (err) {
    if (seq !== reviewSeq) return;
    dom.reviewMeta.textContent = '读取失败';
    dom.reviewList.replaceChildren(el('p', { class: 'review-empty', text: err.message || '获取复盘失败' }));
  }
}

async function submitCurrent() {
  if (state.sending) return;
  const built = buildPayload();
  if (built.error) {
    toast(built.error);
    return;
  }
  const modeAtSend = state.mode;
  state.sending = true;
  syncDraftUi();
  const bubble = built.echo ? echoLocal(built.echo) : null;
  try {
    const res = await fetch(`/game/send/${encodeURIComponent(state.gameId)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(built.payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(detailOf(data) || `HTTP ${res.status}`);
    // SSE can deliver the next prompt before this response arrives.
    // Don't clobber a panel the server already opened.
    if (state.mode === modeAtSend) {
      state.draft = '';
      state.mode = 'waiting';
      state.selectedAction = null;
      state.selectedTarget = null;
      renderAction();
      renderSeats();
      updateChrome();
    }
  } catch (err) {
    if (state.mode === modeAtSend) {
      if (bubble) bubble.remove();
      toast(`发送失败：${err.message || '未知错误'}`);
      syncDraftUi();
    }
  } finally {
    state.sending = false;
    syncDraftUi();
  }
}

function selectTarget(id) {
  state.selectedTarget = id;
  dom.actionBody.querySelectorAll('[data-target]').forEach((btn) => {
    const on = Number(btn.dataset.target) === id;
    btn.classList.toggle('is-selected', on);
    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
  });
  syncDraftUi();
  renderSeats();
}

function bind() {
  dom.startBtn.addEventListener('click', startGame);
  dom.resetBtn.addEventListener('click', resetGame);
  dom.endBtn.addEventListener('click', endGame);
  dom.reviewBtn.addEventListener('click', openReview);
  dom.reviewClose.addEventListener('click', closeDrawer);
  dom.reviewRefresh.addEventListener('click', openReview);
  dom.backdrop.addEventListener('click', closeDrawer);

  dom.actionBody.addEventListener('click', (event) => {
    const actionBtn = event.target.closest('[data-action]');
    if (actionBtn) {
      state.selectedAction = actionBtn.dataset.action;
      state.selectedTarget = null;
      renderAction();
      renderSeats();
      return;
    }
    const targetBtn = event.target.closest('[data-target]');
    if (targetBtn) {
      selectTarget(Number(targetBtn.dataset.target));
      return;
    }
    if (event.target.closest('[data-back]')) {
      state.selectedAction = null;
      state.selectedTarget = null;
      state.draft = '';
      renderAction();
      renderSeats();
      return;
    }
    if (event.target.closest('[data-submit]')) submitCurrent();
    else if (event.target.closest('[data-start]')) startGame();
    else if (event.target.closest('[data-review]')) openReview();
    else if (event.target.closest('[data-reset]')) resetGame();
  });

  dom.actionBody.addEventListener('input', (event) => {
    if (!event.target.classList.contains('draft')) return;
    state.draft = event.target.value;
    syncDraftUi();
  });

  dom.actionBody.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey && event.target.classList.contains('draft')) {
      event.preventDefault();
      submitCurrent();
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && state.reviewOpen) closeDrawer();
  });
}

function init() {
  dom.drawer.inert = true;
  bind();
  renderSeats();
  renderAction();
  updateChrome();
  setEmpty('六人牌桌还没亮灯', '你坐 6 号。开始后，夜晚、发言和投票都会写在这卷战报里。');
}

init();
