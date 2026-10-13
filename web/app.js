/* ==========================================================================
   Super Investing · Research Agent Client Logic
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
  const tickerInput = document.getElementById('ticker-input');
  const modelSelect = document.getElementById('model-select');
  const docsInput = document.getElementById('docs-input');
  const runBtn = document.getElementById('run-btn');
  const btnText = document.getElementById('btn-text');
  const btnSpinner = document.getElementById('btn-spinner');
  
  const apiStatusBadge = document.getElementById('api-status-badge');
  const alertsContainer = document.getElementById('alerts-container');
  const docCountBadge = document.getElementById('doc-count-badge');
  
  const briefContainer = document.getElementById('brief-container');
  const rawMarkdown = document.getElementById('raw-markdown');
  const auditDossier = document.getElementById('audit-dossier');
  
  const copyBtn = document.getElementById('copy-btn');
  const downloadBtn = document.getElementById('download-btn');
  const toast = document.getElementById('toast');

  let currentMarkdown = '';

  // 1. Initial Status & Document Check
  checkStatus();
  loadDocuments();

  // Tab Switching
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      
      btn.classList.add('active');
      const tabTarget = document.getElementById(`tab-${btn.dataset.tab}`);
      if (tabTarget) tabTarget.classList.add('active');
    });
  });

  // Pipeline tracker DOM elements
  const pipelineTracker = document.getElementById('pipeline-tracker');
  const pipelineStatusText = document.getElementById('pipeline-status-text');
  const pipelineStepBadge = document.getElementById('pipeline-step-badge');
  const pipelineProgressFill = document.getElementById('pipeline-progress-fill');

  function setPipelineStep(stepNum, statusText, progressPercent) {
    if (pipelineTracker) pipelineTracker.classList.remove('hidden');
    if (pipelineStatusText && statusText) pipelineStatusText.textContent = statusText;
    if (pipelineStepBadge && stepNum) pipelineStepBadge.textContent = `${stepNum} / 5`;
    if (pipelineProgressFill && progressPercent !== undefined) {
      pipelineProgressFill.style.width = `${progressPercent}%`;
    }
    for (let i = 1; i <= 5; i++) {
      const stepEl = document.getElementById(`step-${i}`);
      if (!stepEl) continue;
      stepEl.classList.remove('active', 'completed');
      if (i < stepNum) {
        stepEl.classList.add('completed');
      } else if (i === stepNum) {
        stepEl.classList.add('active');
      }
    }
  }

  // 2. Run Button Handler (Real-Time SSE Streaming)
  runBtn.addEventListener('click', async () => {
    const ticker = tickerInput.value.trim().toUpperCase() || 'SRVCABLE';
    const model = modelSelect.value;
    const docsDir = docsInput.value.trim() || './research_pack';

    setLoading(true);
    setPipelineStep(1, 'Initializing real-time ingestion & verification...', 5);

    // Reset alerts and output areas
    alertsContainer.innerHTML = '';
    currentMarkdown = '';
    rawMarkdown.value = '';
    briefContainer.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon"><span class="spinner" style="border-color:#000;border-top-color:transparent;"></span></div>
        <h4>Synthesizing brief in real time...</h4>
        <p>Live audit data and stream tokens will populate here as each step finishes.</p>
      </div>
    `;

    let streamFinished = false;

    try {
      const res = await fetch('/api/run-stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker, model, docs_dir: docsDir })
      });

      if (!res.ok) {
        throw new Error(`Server returned HTTP ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (!streamFinished) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split('\n\n');
        buffer = blocks.pop(); // keep remainder

        for (const block of blocks) {
          if (!block.trim()) continue;
          let eventType = 'message';
          let dataStr = '';

          for (const line of block.split('\n')) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith('data: ')) {
              dataStr = line.slice(6);
            }
          }

          if (!dataStr) continue;
          try {
            const data = JSON.parse(dataStr);
            handleRealtimeEvent(eventType, data);
            if (streamFinished) {
              try { await reader.cancel(); } catch {}
              break;
            }
          } catch (parseErr) {
            console.error('Error parsing event payload:', parseErr);
          }
        }
      }

    } catch (err) {
      alertsContainer.innerHTML += `
        <div class="alert-item alert-danger">
          <span class="alert-icon">✕</span>
          <span>Error: ${escapeHtml(err.message)}</span>
        </div>
      `;
    } finally {
      setLoading(false);
    }

    function handleRealtimeEvent(type, data) {
      if (type === 'step_update') {
        setPipelineStep(data.step, data.status, data.progress);
      } else if (type === 'files_found') {
        docCountBadge.textContent = `${data.total} docs`;
      } else if (type === 'doc_read') {
        // Doc read event
      } else if (type === 'profile_resolved') {
        alertsContainer.innerHTML += `
          <div class="alert-item alert-info">
            <span class="alert-icon">✓</span>
            <span>Target profile verified: <strong>${escapeHtml(data.profile.canonical_name)}</strong> (NSE:${escapeHtml(data.profile.ticker)})</span>
          </div>
        `;
      } else if (type === 'doc_inspected') {
        if (data.alerts && data.alerts.length > 0) {
          data.alerts.forEach(a => {
            alertsContainer.innerHTML += `
              <div class="alert-item alert-warning">
                <span class="alert-icon">🛡</span>
                <span><strong>[TRAP DEFUSED] ${escapeHtml(a.file)}:</strong> ${escapeHtml(a.flag)}</span>
              </div>
            `;
          });
        }
      } else if (type === 'audit_complete') {
        if (data.conflicts && data.conflicts.length > 0) {
          data.conflicts.forEach(c => {
            alertsContainer.innerHTML += `
              <div class="alert-item alert-warning">
                <span class="alert-icon">⚠️</span>
                <span><strong>[METRIC AUDIT CONFLICT]</strong> ${escapeHtml(c)}</span>
              </div>
            `;
          });
        } else {
          alertsContainer.innerHTML += `
            <div class="alert-item alert-info">
              <span class="alert-icon">✓</span>
              <span>Metric audit complete: All quantitative values reconciled.</span>
            </div>
          `;
        }
      } else if (type === 'dossier_ready') {
        auditDossier.textContent = data.dossier || 'Audit dossier assembled.';
      } else if (type === 'chunk') {
        currentMarkdown += data.delta;
        rawMarkdown.value = currentMarkdown;
        rawMarkdown.scrollTop = rawMarkdown.scrollHeight;
        renderMarkdown(currentMarkdown + '<span class="streaming-cursor"></span>');
      } else if (type === 'complete') {
        streamFinished = true;
        setLoading(false);
        for (let i = 1; i <= 5; i++) {
          const stepEl = document.getElementById(`step-${i}`);
          if (stepEl) stepEl.classList.add('completed');
        }
        if (pipelineStatusText) pipelineStatusText.textContent = 'Analysis complete · All checks verified';
        if (pipelineStepBadge) pipelineStepBadge.textContent = 'Done';
        if (pipelineProgressFill) pipelineProgressFill.style.width = '100%';

        currentMarkdown = data.brief;
        rawMarkdown.value = currentMarkdown;
        renderMarkdown(currentMarkdown);
        showToast('Research brief generated & streamed successfully!');
      } else if (type === 'error') {
        streamFinished = true;
        setLoading(false);
        alertsContainer.innerHTML += `
          <div class="alert-item alert-danger">
            <span class="alert-icon">✕</span>
            <span>Error: ${escapeHtml(data.error)}</span>
          </div>
        `;
      }
    }
  });

  // 3. Copy Button
  copyBtn.addEventListener('click', () => {
    if (!currentMarkdown) {
      showToast('No brief to copy yet.');
      return;
    }
    navigator.clipboard.writeText(currentMarkdown).then(() => {
      showToast('Copied brief markdown to clipboard!');
    });
  });

  // 4. Download Button
  downloadBtn.addEventListener('click', () => {
    if (!currentMarkdown) {
      showToast('No brief to download yet.');
      return;
    }
    const blob = new Blob([currentMarkdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `brief_${(tickerInput.value || 'SRVCABLE').toLowerCase()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  });

  // API Status
  async function checkStatus() {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      if (data.has_api_key) {
        apiStatusBadge.textContent = 'API KEY ACTIVE';
        apiStatusBadge.className = 'meta-badge badge-success';
      } else {
        apiStatusBadge.textContent = 'NO API KEY (.env)';
        apiStatusBadge.className = 'meta-badge badge-warn';
      }
    } catch {
      apiStatusBadge.textContent = 'OFFLINE';
    }
  }

  // Document Count & Existing Brief Check
  async function loadDocuments() {
    try {
      const res = await fetch('/api/docs?docs_dir=' + encodeURIComponent(docsInput.value));
      const data = await res.json();
      if (data.docs) {
        docCountBadge.textContent = `${data.docs.length} docs`;
      }
      if (data.existing_brief) {
        currentMarkdown = data.existing_brief;
        rawMarkdown.value = currentMarkdown;
        renderMarkdown(currentMarkdown);
      }
    } catch {
      docCountBadge.textContent = '8 docs';
    }
  }

  function renderAlerts(alerts, conflicts) {
    const items = [];
    if (!alerts.length && !conflicts.length) {
      items.push(`
        <div class="alert-item alert-info">
          <span class="alert-icon">✓</span>
          <span>Stage 1 passed: All documents verified with zero collisions.</span>
        </div>
      `);
    }

    alerts.forEach(a => {
      items.push(`
        <div class="alert-item alert-warning">
          <span class="alert-icon">🛡</span>
          <span><strong>${escapeHtml(a.file)}:</strong> ${escapeHtml(a.flag)}</span>
        </div>
      `);
    });

    conflicts.forEach(c => {
      items.push(`
        <div class="alert-item alert-warning">
          <span class="alert-icon">⚠️</span>
          <span>${escapeHtml(c)}</span>
        </div>
      `);
    });

    alertsContainer.innerHTML = items.join('');
  }

  function renderMarkdown(md) {
    if (!md) {
      briefContainer.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">□</div>
          <h4>No brief generated yet</h4>
          <p>Click "Run Research Agent" to inspect the research pack.</p>
        </div>
      `;
      return;
    }

    // Clean, lightweight Markdown parser
    let html = md
      // Escape
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      // Headers
      .replace(/^### (.*$)/gim, '<h3>$1</h3>')
      .replace(/^## (.*$)/gim, '<h2>$1</h2>')
      .replace(/^# (.*$)/gim, '<h1>$1</h1>')
      // Bold & Italic
      .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/gim, '<em>$1</em>')
      // Inline code
      .replace(/`([^`]+)`/gim, '<code>$1</code>')
      // Sources [Source X] highlighting
      .replace(/\[Source\s*(\d+)\]/gi, '<code>Source $1</code>')
      // Unordered lists
      .replace(/^\s*-\s+(.*$)/gim, '<li>$1</li>')
      // Dividers
      .replace(/^---$/gim, '<hr style="border:0;border-top:1px solid #e4e4e7;margin:16px 0;">');

    // Wrap li in ul
    html = html.replace(/(<li>.*<\/li>)/gims, '<ul>$1</ul>');
    // Paragraphs
    html = html.split('\n\n').map(p => {
      p = p.trim();
      if (!p) return '';
      if (p.startsWith('<h') || p.startsWith('<ul') || p.startsWith('<hr')) return p;
      return `<p>${p}</p>`;
    }).join('');

    briefContainer.innerHTML = html;
  }

  function setLoading(loading) {
    if (loading) {
      runBtn.disabled = true;
      btnSpinner.classList.remove('hidden');
      btnText.textContent = 'ANALYZING...';
    } else {
      runBtn.disabled = false;
      btnSpinner.classList.add('hidden');
      btnText.textContent = 'RUN RESEARCH AGENT';
    }
  }

  function showToast(msg) {
    toast.textContent = msg;
    toast.classList.remove('hidden');
    setTimeout(() => toast.classList.add('hidden'), 2500);
  }

  function escapeHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }
});
