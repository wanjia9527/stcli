async function loadSettings() {
  try {
    const auth = await api().get_auth_mode();
    const settings = await api().get_settings();

    if (auth.mode === 'token') {
      document.getElementById('auth-anonymous').classList.remove('active');
      document.getElementById('auth-token').classList.add('active');
      document.getElementById('token-input-area').classList.remove('hidden');
      if (auth.username) {
        document.getElementById('token-verify-result').innerHTML =
          '<span style="color:var(--green);display:flex;align-items:center;gap:6px">' + iconCheck() + ' 已验证: ' + auth.username + (auth.is_premium ? ' · Premium' : '') + '</span>';
      }
    }

    document.getElementById('set-expiry-days').value = settings.default_expiry_days;
    document.getElementById('set-ka-days').value = settings.default_keepalive_days;
    document.getElementById('set-ka-threshold').value = settings.keepalive_threshold;
    document.getElementById('set-ka-interval').value = settings.keepalive_check_interval || 60;
    document.getElementById('set-ka-autostart').checked = settings.keepalive_autostart || false;

    switchDownload(settings.download_mode);
    if (settings.idm_path) {
      document.getElementById('idm-path-input').value = settings.idm_path;
    }

    switchFileMode(settings.file_mode || 'merge');
    refreshQuota();
  } catch (e) {
    console.error('loadSettings error:', e);
  }
}

function switchAuth(mode) {
  document.getElementById('auth-anonymous').classList.toggle('active', mode === 'anonymous');
  document.getElementById('auth-token').classList.toggle('active', mode === 'token');
  document.getElementById('token-input-area').classList.toggle('hidden', mode === 'anonymous');

  if (mode === 'anonymous') {
    api().clear_token();
    document.getElementById('token-verify-result').innerHTML = '';
    updateStatusBar();
  }
}

function toggleTokenVisibility() {
  var input = document.getElementById('bearer-token-input');
  input.type = input.type === 'password' ? 'text' : 'password';
}

async function verifyToken() {
  var token = document.getElementById('bearer-token-input').value.trim();
  if (!token) return;
  var result = await api().set_token(token);
  var el = document.getElementById('token-verify-result');
  if (result.ok) {
    el.innerHTML = '<span style="color:var(--green);display:flex;align-items:center;gap:6px">' + iconCheck() + ' 已验证: ' + result.username + (result.is_premium ? ' · Premium' : '') + '</span>';
  } else {
    el.innerHTML = '<span style="color:var(--red);display:flex;align-items:center;gap:6px">' + iconX() + ' ' + result.error + '</span>';
  }
  updateStatusBar();
}

async function refreshQuota() {
  var bw = await api().get_quota();
  document.getElementById('q-limit').textContent = bw.limit_gb.toFixed(0);
  document.getElementById('q-used').textContent = bw.used_gb.toFixed(1);
  document.getElementById('q-remaining').textContent = bw.remaining_gb.toFixed(1);
  var pct = bw.limit_gb > 0 ? (bw.used_gb / bw.limit_gb * 100) : 0;
  document.getElementById('quota-progress-fill').style.width = pct + '%';
}

function switchDownload(mode) {
  document.getElementById('dl-browser').classList.toggle('active', mode === 'browser');
  document.getElementById('dl-idm').classList.toggle('active', mode === 'idm');
  document.getElementById('idm-path-area').classList.toggle('hidden', mode !== 'idm');
}

async function detectIdm() {
  var result = await api().detect_idm_path();
  if (result.path) {
    document.getElementById('idm-path-input').value = result.path;
  } else {
    showToast('未检测到 IDM', 'error');
  }
}

async function browseIdm() {
  var result = await api().browse_file('选择 IDMan.exe');
  if (result.path) {
    document.getElementById('idm-path-input').value = result.path;
  }
}

function switchFileMode(mode) {
  document.getElementById('filemode-merge').classList.toggle('active', mode === 'merge');
  document.getElementById('filemode-local').classList.toggle('active', mode === 'local');
  document.getElementById('filemode-cloud').classList.toggle('active', mode === 'cloud');
}

async function saveSettings() {
  var fileMode = 'merge';
  if (document.getElementById('filemode-local').classList.contains('active')) fileMode = 'local';
  else if (document.getElementById('filemode-cloud').classList.contains('active')) fileMode = 'cloud';

  var settings = {
    download_mode: document.getElementById('dl-idm').classList.contains('active') ? 'idm' : 'browser',
    idm_path: document.getElementById('idm-path-input').value,
    default_expiry_days: parseInt(document.getElementById('set-expiry-days').value),
    default_keepalive_days: parseInt(document.getElementById('set-ka-days').value),
    keepalive_threshold: parseInt(document.getElementById('set-ka-threshold').value),
    keepalive_check_interval: parseInt(document.getElementById('set-ka-interval').value) || 60,
    keepalive_autostart: document.getElementById('set-ka-autostart').checked,
    file_mode: fileMode,
  };
  await api().save_settings(settings);
  showToast('设置已保存', 'success');
}

function resetSettings() {
  document.getElementById('set-expiry-days').value = 3;
  document.getElementById('set-ka-days').value = 7;
  document.getElementById('set-ka-threshold').value = 2;
  document.getElementById('set-ka-interval').value = 60;
  document.getElementById('set-ka-autostart').checked = false;
  switchDownload('browser');
  switchFileMode('merge');
  document.getElementById('idm-path-input').value = '';
}
