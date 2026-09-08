/* ═══════════════════════════════════════════════════════════════════════════
   LLMinator ONNX UI — app.js
   ═══════════════════════════════════════════════════════════════════════════ */

// ── State ─────────────────────────────────────────────────────────────────────
let selectedFile   = null;   // File object from input
let selectedPath   = null;   // Manual path string
let currentJobId   = null;
let eventSource    = null;

// ── Background canvas (animated grid + particles) ─────────────────────────────
(function initBg() {
  const canvas = document.getElementById('bg-canvas');
  const ctx    = canvas.getContext('2d');
  let W, H;

  const particles = Array.from({length: 60}, () => ({
    x: Math.random(), y: Math.random(),
    vx: (Math.random()-0.5)*0.0003,
    vy: (Math.random()-0.5)*0.0003,
    r: Math.random()*1.4+0.4,
    a: Math.random()*0.6+0.2,
  }));

  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }
  window.addEventListener('resize', resize);
  resize();

  function draw() {
    ctx.clearRect(0, 0, W, H);

    // Grid
    ctx.strokeStyle = 'rgba(59,130,246,0.04)';
    ctx.lineWidth = 1;
    const step = 60;
    for (let x = 0; x < W; x += step) {
      ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,H); ctx.stroke();
    }
    for (let y = 0; y < H; y += step) {
      ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(W,y); ctx.stroke();
    }

    // Particles
    particles.forEach(p => {
      p.x += p.vx; p.y += p.vy;
      if (p.x<0) p.x=1; if (p.x>1) p.x=0;
      if (p.y<0) p.y=1; if (p.y>1) p.y=0;
      ctx.beginPath();
      ctx.arc(p.x*W, p.y*H, p.r, 0, Math.PI*2);
      ctx.fillStyle = `rgba(99,167,255,${p.a})`;
      ctx.fill();
    });

    // Connections
    ctx.lineWidth = 0.5;
    for (let i=0; i<particles.length; i++) {
      for (let j=i+1; j<particles.length; j++) {
        const dx = (particles[i].x-particles[j].x)*W;
        const dy = (particles[i].y-particles[j].y)*H;
        const d  = Math.sqrt(dx*dx+dy*dy);
        if (d < 100) {
          ctx.beginPath();
          ctx.strokeStyle = `rgba(59,130,246,${0.12*(1-d/100)})`;
          ctx.moveTo(particles[i].x*W, particles[i].y*H);
          ctx.lineTo(particles[j].x*W, particles[j].y*H);
          ctx.stroke();
        }
      }
    }

    requestAnimationFrame(draw);
  }
  draw();
})();


// ── Server health ping ────────────────────────────────────────────────────────
async function pingServer() {
  const dot   = document.getElementById('server-dot');
  const label = document.getElementById('server-label');
  try {
    const r = await fetch('/api/reports', {signal: AbortSignal.timeout(2000)});
    if (r.ok) {
      dot.classList.add('ok'); dot.classList.remove('err');
      label.textContent = 'Server online';
    } else throw new Error();
  } catch {
    dot.classList.add('err'); dot.classList.remove('ok');
    label.textContent = 'Server offline';
  }
}
pingServer();
setInterval(pingServer, 8000);


// ── View routing ──────────────────────────────────────────────────────────────
function showView(name) {
  document.querySelectorAll('main > section').forEach(s => s.classList.add('hidden'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(`view-${name}`).classList.remove('hidden');
  document.getElementById(`nav-${name}`).classList.add('active');
  if (name === 'history') loadHistory();
}


// ── Drop-zone wiring ──────────────────────────────────────────────────────────
const dropZone  = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');

dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (f) applyFile(f);
});
dropZone.addEventListener('click', e => {
  if (e.target.classList.contains('link-btn') || e.target.closest('.path-row')) return;
  fileInput.click();
});
fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) applyFile(fileInput.files[0]);
});

function applyFile(f) {
  if (!f.name.endsWith('.onnx')) {
    showToast('Only .onnx files are accepted.', 'error');
    return;
  }
  selectedFile = f;
  selectedPath = null;
  document.getElementById('path-input').value = '';
  document.getElementById('selected-name').textContent = f.name;
  document.getElementById('selected-size').textContent = fmtBytes(f.size);
  document.getElementById('selected-file').classList.remove('hidden');
  document.getElementById('btn-scan').disabled = false;
}

function clearFile() {
  selectedFile = null;
  selectedPath = null;
  fileInput.value = '';
  document.getElementById('selected-file').classList.add('hidden');
  document.getElementById('btn-scan').disabled = true;
  document.getElementById('path-input').value = '';
}

function usePath() {
  const v = document.getElementById('path-input').value.trim();
  if (!v) return;
  if (!v.endsWith('.onnx')) { showToast('Path must end with .onnx', 'error'); return; }
  selectedPath = v;
  selectedFile = null;
  fileInput.value = '';
  document.getElementById('selected-name').textContent = v.split('/').pop();
  document.getElementById('selected-size').textContent = 'local path';
  document.getElementById('selected-file').classList.remove('hidden');
  document.getElementById('btn-scan').disabled = false;
}


// ── Scan ──────────────────────────────────────────────────────────────────────
async function startScan() {
  if (!selectedFile && !selectedPath) return;

  const btn  = document.getElementById('btn-scan');
  const deep = document.getElementById('deep-toggle').checked;

  btn.disabled = true;
  btn.classList.add('scanning');
  btn.querySelector('.btn-icon').textContent = '⟳';
  btn.childNodes[1].textContent = ' Scanning…';

  const fd = new FormData();
  fd.append('deep', String(deep));
  if (selectedFile) fd.append('file', selectedFile);
  else              fd.append('path', selectedPath);

  // Show terminal
  const termCard  = document.getElementById('terminal-card');
  const termBody  = document.getElementById('terminal-body');
  const termStat  = document.getElementById('terminal-status');
  termCard.classList.remove('hidden');
  termBody.textContent = '';
  termStat.textContent = 'running';
  termStat.className   = 'terminal-status';
  document.getElementById('results-area').innerHTML = '';

  try {
    const resp = await fetch('/api/scan', { method: 'POST', body: fd });
    const data = await resp.json();
    if (!resp.ok) { showToast(data.error || 'Scan failed', 'error'); resetBtn(btn); return; }

    currentJobId = data.job_id;
    streamJob(currentJobId, termBody, termStat, btn);

  } catch (e) {
    showToast('Could not reach server: ' + e.message, 'error');
    resetBtn(btn);
  }
}

function streamJob(jobId, termBody, termStat, btn) {
  if (eventSource) eventSource.close();
  eventSource = new EventSource(`/api/jobs/${jobId}/stream`);

  eventSource.onmessage = e => {
    const msg = JSON.parse(e.data);
    if (msg.line !== undefined) {
      appendLine(termBody, msg.line);
    }
    if (msg.done) {
      eventSource.close();
      termStat.textContent = msg.status === 'done' ? 'done' : 'error';
      termStat.classList.add(msg.status === 'done' ? 'done' : 'error');
      resetBtn(btn);
      // Fetch full report and render
      fetch(`/api/jobs/${jobId}`)
        .then(r => r.json())
        .then(job => {
          if (job.report && Object.keys(job.report).length > 0) {
            renderReport(job.report, document.getElementById('results-area'));
          }
        });
    }
  };

  eventSource.onerror = () => {
    eventSource.close();
    termStat.textContent = 'error';
    termStat.classList.add('error');
    resetBtn(btn);
  };
}

function appendLine(container, line) {
  const span = document.createElement('span');
  const low  = line.toLowerCase();
  if (low.includes('fail') || low.includes('error') || low.includes('✗'))
    span.className = 't-err';
  else if (low.includes('pass') || low.includes('ok') || low.includes('✓'))
    span.className = 't-ok';
  else if (low.includes('warn') || low.includes('⚠'))
    span.className = 't-warn';
  span.textContent = line + '\n';
  container.appendChild(span);
  container.scrollTop = container.scrollHeight;
}

function resetBtn(btn) {
  btn.disabled = false;
  btn.classList.remove('scanning');
  btn.querySelector('.btn-icon').textContent = '⬡';
  btn.childNodes[1].textContent = ' Run ONNX Audit';
}


// ── Report renderer ───────────────────────────────────────────────────────────
function renderReport(r, container) {
  container.innerHTML = '';
  const div = document.createElement('div');
  div.className = 'card';
  div.innerHTML = buildReportHTML(r);
  container.appendChild(div);
  div.scrollIntoView({behavior: 'smooth', block: 'start'});
}

function buildReportHTML(r) {
  const sum = r.summary || {};
  const tgt = r.target  || {};
  const checks = r.results || [];
  const allPass = (sum.failed || 0) === 0 && (sum.errors || 0) === 0;
  const overallStatus = allPass ? 'pass' : 'fail';

  // Severity breakdown pill
  const sev = sum.severity_breakdown || {};
  const sevPills = Object.entries(sev)
    .filter(([,v]) => v > 0)
    .map(([k,v]) => `<span class="severity ${k}">${v} ${k}</span>`)
    .join(' ') || '<span class="severity info">clean</span>';

  let html = `
    <div class="result-header">
      <div class="result-badge-wrap">
        <span class="result-badge ${overallStatus}">${overallStatus === 'pass' ? '✓ Pass' : '✗ Issues Found'}</span>
      </div>
      <div>
        <div class="result-title">${escHtml(tgt.name || 'ONNX Audit')}</div>
        <div class="result-sub">${escHtml(r.scan_id || '')} &nbsp;·&nbsp; ${escHtml(r.suite || '')} &nbsp;·&nbsp; ${sevPills}</div>
      </div>
    </div>

    <div class="counters">
      <div class="counter-box total">
        <div class="counter-num">${sum.total_checks || 0}</div>
        <div class="counter-lbl">Total</div>
      </div>
      <div class="counter-box passed">
        <div class="counter-num">${sum.passed || 0}</div>
        <div class="counter-lbl">Passed</div>
      </div>
      <div class="counter-box failed">
        <div class="counter-num">${sum.failed || 0}</div>
        <div class="counter-lbl">Failed</div>
      </div>
      <div class="counter-box errors">
        <div class="counter-num">${sum.errors || 0}</div>
        <div class="counter-lbl">Errors</div>
      </div>
    </div>
  `;

  // Per-check breakdown
  checks.forEach((c, i) => {
    const ev  = c.evidence || {};
    html += `<div class="section-title">Check ${i+1} — ${escHtml(c.check || '')}</div>`;

    // Evidence grid
    const evFields = [
      ['Engine', c.engine],
      ['Status', c.status],
      ['Severity', `<span class="severity ${c.severity}">${c.severity}</span>`],
      ['Duration', c.duration_ms ? `${c.duration_ms.toFixed(1)} ms` : '—'],
      ['Details', c.details],
      ['SHA-256', ev.sha256 ? ev.sha256.slice(0,20)+'…' : null],
      ['Producer', ev.producer],
      ['IR Version', ev.ir_version],
      ['Node count', ev.node_count],
      ['Size', ev.size_bytes ? fmtBytes(ev.size_bytes) : null],
      ['Dynamic dims', ev.dynamic_input_dimensions != null ? String(ev.dynamic_input_dimensions) : null],
    ].filter(([,v]) => v != null && v !== '');

    html += '<div class="evidence-grid">';
    evFields.forEach(([k, v]) => {
      html += `<div class="ev-item"><div class="ev-key">${escHtml(k)}</div><div class="ev-value">${String(v).startsWith('<') ? v : escHtml(String(v))}</div></div>`;
    });
    html += '</div>';

    // Opsets
    if (ev.opsets && ev.opsets.length) {
      html += `<div class="section-title">Opsets</div><p style="margin-bottom:1.2rem">`;
      ev.opsets.forEach(op => {
        html += `<span class="pill">${escHtml(op.domain || 'default')} v${op.version}</span>`;
      });
      html += '</p>';
    }

    // Inputs / Outputs
    if ((ev.inputs && ev.inputs.length) || (ev.outputs && ev.outputs.length)) {
      html += `<div class="section-title">Model I/O</div>`;
      html += '<table class="io-table"><thead><tr><th>Role</th><th>Name</th><th>Shape</th><th>Dtype</th></tr></thead><tbody>';
      (ev.inputs || []).forEach(io => {
        html += `<tr><td style="color:var(--accent2)">Input</td><td>${escHtml(io.name)}</td><td>${escHtml(JSON.stringify(io.shape))}</td><td>${io.element_type}</td></tr>`;
      });
      (ev.outputs || []).forEach(io => {
        html += `<tr><td style="color:var(--purple)">Output</td><td>${escHtml(io.name)}</td><td>${escHtml(JSON.stringify(io.shape))}</td><td>${io.element_type}</td></tr>`;
      });
      html += '</tbody></table>';
    }

    // Remediation
    if (c.remediation && c.remediation.length) {
      html += `<div class="section-title">Remediation</div><ul class="remediation-list">`;
      c.remediation.forEach(r2 => {
        html += `<li>${escHtml(r2)}</li>`;
      });
      html += '</ul>';
    }
  });

  // Timestamps footer
  if (r.started_at) {
    html += `<div style="margin-top:1.5rem;padding-top:1rem;border-top:1px solid var(--border);font-size:0.76rem;color:var(--text3);font-family:var(--mono)">
      Started: ${fmtDate(r.started_at)} &nbsp;·&nbsp; Finished: ${fmtDate(r.finished_at)}
      &nbsp;·&nbsp; Tool: ${escHtml((r.tool||{}).name||'')} ${escHtml((r.tool||{}).version||'')}
    </div>`;
  }

  return html;
}


// ── History ───────────────────────────────────────────────────────────────────
async function loadHistory() {
  const list = document.getElementById('history-list');
  list.innerHTML = '<p class="empty-msg">Loading…</p>';
  try {
    const r = await fetch('/api/reports');
    const data = await r.json();
    if (!data.length) { list.innerHTML = '<p class="empty-msg">No ONNX scan reports found yet.</p>'; return; }
    list.innerHTML = '';
    data.forEach(({filename, data: rep}) => {
      const tgt  = rep.target || {};
      const sum  = rep.summary || {};
      const allPass = (sum.failed||0)===0 && (sum.errors||0)===0;
      const item = document.createElement('div');
      item.className = 'history-item';
      item.innerHTML = `
        <div class="hist-icon">${allPass ? '✅' : '⚠️'}</div>
        <div class="hist-info">
          <div class="hist-name">${escHtml(tgt.name || filename)}</div>
          <div class="hist-meta">${escHtml(filename)} &nbsp;·&nbsp; ${escHtml(rep.suite || '')}</div>
        </div>
        <div class="hist-right">
          <div style="margin-bottom:4px"><span class="result-badge ${allPass?'pass':'fail'}" style="font-size:0.7rem">${allPass?'Pass':'Issues'}</span></div>
          <div style="font-size:0.72rem;color:var(--text3)">${sum.total_checks||0} check(s)</div>
        </div>
      `;
      item.onclick = () => openReportModal(rep);
      list.appendChild(item);
    });
  } catch(e) {
    list.innerHTML = `<p class="empty-msg">Failed to load: ${e.message}</p>`;
  }
}


// ── Modal ─────────────────────────────────────────────────────────────────────
function openReportModal(rep) {
  document.getElementById('modal-content').innerHTML = buildReportHTML(rep);
  document.getElementById('modal-backdrop').classList.remove('hidden');
  document.getElementById('modal').classList.remove('hidden');
}
function closeModal() {
  document.getElementById('modal-backdrop').classList.add('hidden');
  document.getElementById('modal').classList.add('hidden');
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });


// ── Utilities ─────────────────────────────────────────────────────────────────
function fmtBytes(n) {
  if (n < 1024) return n + ' B';
  if (n < 1048576) return (n/1024).toFixed(1) + ' KB';
  return (n/1048576).toFixed(2) + ' MB';
}

function fmtDate(iso) {
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function escHtml(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Toast notification ────────────────────────────────────────────────────────
function showToast(msg, type='info') {
  const t = document.createElement('div');
  t.style.cssText = `
    position:fixed;bottom:2rem;right:2rem;z-index:999;
    background:${type==='error'?'rgba(248,113,113,0.15)':'rgba(59,130,246,0.15)'};
    border:1px solid ${type==='error'?'rgba(248,113,113,0.3)':'rgba(59,130,246,0.3)'};
    color:${type==='error'?'#fca5a5':'#93c5fd'};
    padding:.75rem 1.2rem;border-radius:10px;font-size:.87rem;
    backdrop-filter:blur(12px);animation:fadeUp .25s ease;
    max-width:340px;line-height:1.5;
  `;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}
