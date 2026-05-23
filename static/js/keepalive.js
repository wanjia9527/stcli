async function loadKeepalive() {
  var tbody = document.getElementById('ka-tbody');
  tbody.innerHTML = '<tr><td colspan="7"><div class="loading-pulse"></div></td></tr>';
  var data = await api().keepalive_list();
  renderKeepaliveTable(data.files || []);
}

function renderKeepaliveTable(files) {
  var tbody = document.getElementById('ka-tbody');
  if (files.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7"><div class="empty-state"><div class="empty-icon" id="ka-empty-icon"></div><p>暂无守护文件</p><p class="text-muted">添加文件后将自动续命</p></div></td></tr>';
    setTimeout(function(){ var el = document.getElementById('ka-empty-icon'); if(el) el.innerHTML = iconInbox(); }, 0);
    return;
  }
  var html = '';
  for (var i = 0; i < files.length; i++) {
    var f = files[i];
    var remaining = parseFloat(f.remaining_days);
    var statusBadge = '';
    if (f.status === 'ok') {
      statusBadge = remaining <= 2 ? '<span class="badge badge-yellow">即将过期</span>' : '<span class="badge badge-green">正常</span>';
    } else if (f.status === 'error') {
      statusBadge = '<span class="badge badge-red">失败</span>';
    } else {
      statusBadge = '<span class="badge badge-blue">已续命</span>';
    }

    html += '<tr>' +
      '<td>' + escHtml(f.filename) + '</td>' +
      '<td class="text-muted">' + f.size + '</td>' +
      '<td class="text-muted">' + f.expires_at + '</td>' +
      '<td>' + f.remaining_days + ' 天</td>' +
      '<td>' + f.target_days + ' 天</td>' +
      '<td>' + statusBadge + '</td>' +
      '<td><span class="action-btn" style="color:var(--red)" onclick="keepaliveRemove(\'' + f.file_id + '\')">移除</span></td>' +
      '</tr>';
  }
  tbody.innerHTML = html;
}

async function keepaliveStart() {
  document.getElementById('ka-start-btn').classList.add('loading');
  await api().keepalive_start();
  document.getElementById('ka-start-btn').classList.remove('loading');
  document.getElementById('ka-status-dot').className = 'status-dot running';
  document.getElementById('ka-status-text').textContent = '运行中';
  document.getElementById('ka-start-btn').disabled = true;
  document.getElementById('ka-stop-btn').disabled = false;
  document.getElementById('ka-check-btn').disabled = false;
  showToast('守护已启动', 'success');
}

async function keepaliveStop() {
  document.getElementById('ka-stop-btn').classList.add('loading');
  await api().keepalive_stop();
  document.getElementById('ka-stop-btn').classList.remove('loading');
  document.getElementById('ka-status-dot').className = 'status-dot stopped';
  document.getElementById('ka-status-text').textContent = '已停止';
  document.getElementById('ka-start-btn').disabled = false;
  document.getElementById('ka-stop-btn').disabled = true;
  document.getElementById('ka-check-btn').disabled = true;
}

async function keepaliveCheckNow() {
  document.getElementById('ka-check-btn').classList.add('loading');
  var result = await api().keepalive_check_now();
  document.getElementById('ka-check-btn').classList.remove('loading');
  if (result.ok) {
    showToast('正在检查...', 'info');
  } else {
    showToast(result.error || '检查失败', 'error');
  }
}

async function keepaliveRemove(fileId) {
  if (!confirm('确定从守护中移除？')) return;
  await api().keepalive_remove(fileId);
  loadKeepalive();
}

function showAddKeepalive() {
  showModal('添加文件到守护',
    '<input type="text" id="modal-ka-fileid" placeholder="文件 ID">' +
    '<input type="text" id="modal-ka-token" placeholder="Owner Token">' +
    '<input type="number" id="modal-ka-days" min="1" max="7" value="7" placeholder="续命目标天数">' +
    '<button class="btn btn-primary modal-action" data-action="confirm-add-ka">添加</button>'
  );
}

async function doAddKeepalive() {
  var fileId = document.getElementById('modal-ka-fileid').value.trim();
  var token = document.getElementById('modal-ka-token').value.trim();
  var days = parseInt(document.getElementById('modal-ka-days').value) || 7;
  if (!fileId || !token) { showToast('请填写文件 ID 和 Owner Token', 'error'); return; }
  var result = await api().keepalive_add(fileId, token, days);
  closeModal();
  showToast(result.ok ? '已添加' : result.error, result.ok ? 'success' : 'error');
  loadKeepalive();
}

async function doAddKeepaliveWithToken(fileId) {
  var token = document.getElementById('modal-owner-token').value.trim();
  if (!token) { showToast('请输入 Owner Token', 'error'); return; }
  var result = await api().keepalive_add(fileId, token, 7);
  closeModal();
  showToast(result.ok ? '已加入守护' : (result.error || '添加失败'), result.ok ? 'success' : 'error');
}

window.onKeepaliveLog = function (msg) {
  var logEl = document.getElementById('ka-log');
  logEl.innerHTML += '<div>' + msg + '</div>';
  logEl.scrollTop = logEl.scrollHeight;
};

window.onKeepaliveStatus = function (fileId, status) {
  loadKeepalive();
};
