var fileViewMode = 'table';
var selectedFiles = new Set();
var allFiles = [];
var _currentModalIsCollection = false;

async function loadFiles() {
  var container = document.getElementById('file-list');
  container.innerHTML = '<div class="loading-pulse"></div>';
  var keyword = document.getElementById('file-search').value;
  var data = await api().list_files(keyword);
  allFiles = data.files || [];
  selectedFiles.clear();
  renderFiles();
  updateBatchBar();
}

function renderFiles() {
  var container = document.getElementById('file-list');
  if (fileViewMode === 'table') {
    renderFileTable(container);
  } else {
    renderFileCards(container);
  }
}

function renderFileTable(container) {
  if (allFiles.length === 0) {
    container.innerHTML = '<div class="empty-state"><div class="empty-icon" id="files-empty-icon"></div><p>暂无文件</p><p class="text-muted">上传文件后将在此显示</p></div>';
    document.getElementById('files-empty-icon').innerHTML = iconInbox();
    return;
  }
  var html = '<table class="data-table"><thead><tr>' +
    '<th style="width:24px"><input type="checkbox" id="select-all-cb"></th>' +
    '<th>文件名</th><th>大小</th><th>过期</th><th>来源</th><th style="text-align:right">操作</th>' +
    '</tr></thead><tbody>';
  for (var i = 0; i < allFiles.length; i++) {
    var f = allFiles[i];
    var checked = selectedFiles.has(f.id) ? 'checked' : '';
    var sourceBadge = f.source === 'local' ? '<span class="badge badge-blue">本地</span>' : f.source === 'cloud' ? '<span class="badge badge-green">云端</span>' : '';
    html += '<tr data-file-id="' + f.id + '">' +
      '<td><input type="checkbox" class="file-checkbox" data-file-id="' + f.id + '" ' + checked + '></td>' +
      '<td>' + escHtml(f.filename) + '</td>' +
      '<td class="text-muted">' + f.human_size + '</td>' +
      '<td class="text-muted">' + f.expires_at + '</td>' +
      '<td>' + sourceBadge + '</td>' +
      '<td style="text-align:right;white-space:nowrap">' +
      '<span class="action-btn file-action" data-action="download" data-file-id="' + f.id + '" title="下载">' + iconDownload() + '</span>' +
      '<span class="action-btn file-action" data-action="copy-dl-link" data-file-id="' + f.id + '" title="复制直链">' + iconLink() + '</span>' +
      '<span class="action-btn file-action" data-action="copy-link" data-file-id="' + f.id + '" title="复制页面链接">' + iconCopy() + '</span>' +
      '<span class="action-btn file-action" data-action="qr-code" data-file-id="' + f.id + '" title="二维码">' + iconFile() + '</span>' +
      '<span class="action-btn file-action" data-action="open-browser" data-file-id="' + f.id + '" title="在浏览器打开">' + iconUpload() + '</span>' +
      '<span class="action-btn file-action" data-action="add-keepalive" data-file-id="' + f.id + '" title="加入守护">' + iconClock() + '</span>' +
      '<span class="action-btn file-action" data-action="set-expiry" data-file-id="' + f.id + '" title="修改过期">' + iconSettings() + '</span>' +
      '<span class="action-btn file-action" data-action="set-password" data-file-id="' + f.id + '" title="设置密码">' + iconLock() + '</span>' +
      '<span class="action-btn file-action" data-action="set-downloads" data-file-id="' + f.id + '" title="设置下载次数">' + iconBarChart() + '</span>' +
      '<span class="action-btn file-action file-action-danger" data-action="delete-file" data-file-id="' + f.id + '" title="删除">' + iconTrash() + '</span>' +
      '</td></tr>';
  }
  html += '</tbody></table>';
  container.innerHTML = html;
}

function renderFileCards(container) {
  if (allFiles.length === 0) {
    container.innerHTML = '<div class="empty-state"><div class="empty-icon" id="files-empty-icon-card"></div><p>暂无文件</p><p class="text-muted">上传文件后将在此显示</p></div>';
    document.getElementById('files-empty-icon-card').innerHTML = iconInbox();
    return;
  }
  var html = '<div class="card-grid">';
  for (var i = 0; i < allFiles.length; i++) {
    var f = allFiles[i];
    var iconHtml = getFileIconSvg(f.filename);
    var checked = selectedFiles.has(f.id);
    var sourceBadge = f.source === 'local' ? ' <span class="badge badge-blue">本地</span>' : f.source === 'cloud' ? ' <span class="badge badge-green">云端</span>' : '';
    html += '<div class="card" data-file-id="' + f.id + '" style="cursor:pointer">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">' +
      '<div style="background:var(--accent-muted);width:28px;height:28px;border-radius:6px;display:flex;align-items:center;justify-content:center;color:var(--accent)">' + iconHtml + '</div>' +
      '<input type="checkbox" class="file-checkbox" data-file-id="' + f.id + '" ' + (checked ? 'checked' : '') + '>' +
      '</div>' +
      '<div class="card-title" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + escHtml(f.filename) + '</div>' +
      '<div class="card-meta">' + f.human_size + ' · ' + f.expires_at + ' 过期' + sourceBadge + '</div>' +
      '<div class="card-actions">' +
      '<button class="btn btn-sm file-action" data-action="download" data-file-id="' + f.id + '">' + iconDownload() + ' 下载</button>' +
      '<button class="btn btn-sm file-action" data-action="copy-dl-link" data-file-id="' + f.id + '">' + iconLink() + ' 直链</button>' +
      '<button class="btn btn-sm file-action" data-action="more" data-file-id="' + f.id + '">' + iconMore() + ' 更多</button>' +
      '</div></div>';
  }
  html += '</div>';
  container.innerHTML = html;
}

function getFileIconSvg(filename) {
  var ext = filename.split('.').pop().toLowerCase();
  if (['mp4', 'avi', 'mkv', 'mov'].indexOf(ext) >= 0) return iconFilm();
  if (['zip', '7z', 'rar', 'tar'].indexOf(ext) >= 0) return iconPackage();
  if (['jpg', 'jpeg', 'png', 'gif', 'webp'].indexOf(ext) >= 0) return iconImage();
  if (['mp3', 'wav', 'flac'].indexOf(ext) >= 0) return iconMusic();
  return iconFile();
}

function toggleFileView() {
  fileViewMode = fileViewMode === 'table' ? 'card' : 'table';
  document.getElementById('file-view-toggle').textContent = fileViewMode === 'table' ? '切换卡片' : '切换表格';
  renderFiles();
}

function toggleFileSelect(id, checked) {
  if (checked) selectedFiles.add(id); else selectedFiles.delete(id);
  renderFiles();
  updateBatchBar();
}

function toggleSelectAll(checked) {
  if (checked) allFiles.forEach(function(f) { selectedFiles.add(f.id); });
  else selectedFiles.clear();
  renderFiles();
  updateBatchBar();
}

function updateBatchBar() {
  var bar = document.getElementById('file-batch-bar');
  var count = selectedFiles.size;
  if (count > 0) {
    bar.classList.remove('hidden');
    document.getElementById('file-selected-count').textContent = '已选 ' + count + ' 个';
  } else {
    bar.classList.add('hidden');
  }
}

var _searchTimer;
function searchFiles() {
  clearTimeout(_searchTimer);
  _searchTimer = setTimeout(loadFiles, 300);
}

function refreshFiles() { withBtnLoading('files-refresh-btn', loadFiles); }

function getFileUrl(id, isCollection) {
  return isCollection ? 'https://storage.to/c/' + id : 'https://storage.to/' + id;
}

async function downloadFile(id, isCollection) {
  if (isCollection) {
    window.open(getFileUrl(id, true), '_blank');
    return;
  }
  var result = await api().get_download_url(id);
  if (result.ok && result.url) {
    window.open(result.url, '_blank');
  } else {
    window.open(getFileUrl(id, false), '_blank');
  }
}

async function copyDownloadLink(id, isCollection) {
  if (isCollection) {
    showToast('合集不支持直链', 'info');
    return;
  }
  var result = await api().get_download_url(id);
  if (result.ok && result.url) {
    navigator.clipboard.writeText(result.url);
    showToast('直链已复制', 'success');
  } else {
    showToast('获取直链失败', 'error');
  }
}

function copyFileLink(id, isCollection) {
  navigator.clipboard.writeText(getFileUrl(id, isCollection));
  showToast('链接已复制', 'success');
}

async function showQrCode(id, isCollection) {
  var url = getFileUrl(id, isCollection);
  var result = await api().get_qrcode(url);
  if (!result.ok) {
    showToast(result.error || '生成二维码失败', 'error');
    return;
  }
  showModal('分享二维码',
    '<div style="text-align:center">' +
    '<img src="' + result.image + '" style="width:200px;height:200px;border-radius:8px;margin-bottom:12px">' +
    '<div style="color:var(--fg-muted);font-size:11px;word-break:break-all;margin-bottom:12px">' + url + '</div>' +
    '<button class="btn modal-action" data-action="copy-link" data-id="' + id + '" style="width:100%">复制链接</button>' +
    '</div>'
  );
}

function openInBrowser(id, isCollection) {
  window.open(getFileUrl(id, isCollection), '_blank');
}

async function batchDownload() {
  var ids = Array.from(selectedFiles);
  for (var i = 0; i < ids.length; i++) {
    await downloadFile(ids[i]);
  }
}

async function batchCopyDlLinks() {
  var ids = Array.from(selectedFiles);
  var links = [];
  for (var i = 0; i < ids.length; i++) {
    var isColl = false;
    for (var j = 0; j < allFiles.length; j++) {
      if (allFiles[j].id === ids[i]) { isColl = allFiles[j].is_collection; break; }
    }
    if (isColl) {
      links.push(getFileUrl(ids[i], true));
    } else {
      var result = await api().get_download_url(ids[i]);
      if (result.ok && result.url) links.push(result.url);
    }
  }
  if (links.length > 0) {
    navigator.clipboard.writeText(links.join('\n'));
    showToast('已复制 ' + links.length + ' 条链接', 'success');
  } else {
    showToast('获取链接失败', 'error');
  }
}

async function batchCopyLinks() {
  var ids = Array.from(selectedFiles);
  var links = [];
  for (var i = 0; i < ids.length; i++) {
    var isColl = false;
    for (var j = 0; j < allFiles.length; j++) {
      if (allFiles[j].id === ids[i]) { isColl = allFiles[j].is_collection; break; }
    }
    links.push(getFileUrl(ids[i], isColl));
  }
  navigator.clipboard.writeText(links.join('\n'));
  showToast('已复制 ' + links.length + ' 条链接', 'success');
}

async function batchAddToKeepalive() {
  var ids = Array.from(selectedFiles);
  var count = 0;
  for (var i = 0; i < ids.length; i++) {
    try {
      var result = await api().keepalive_add(ids[i], '', 7);
      if (result.ok) count++;
    } catch(e) {}
  }
  showToast('已将 ' + count + ' 个文件加入守护', 'success');
}

async function addToKeepalive(id) {
  var result = await api().keepalive_add(id, '', 7);
  showToast(result.ok ? '已加入守护' : (result.error || '添加失败'), result.ok ? 'success' : 'error');
}

function batchSetExpiry() {
  showModal('批量修改过期时间',
    '<label>天数 (1-7)</label>' +
    '<input type="number" id="modal-batch-expiry" min="1" max="7" value="7">' +
    '<button class="btn btn-primary modal-action" data-action="confirm-batch-expiry">确认</button>'
  );
}

async function doBatchSetExpiry() {
  var days = parseInt(document.getElementById('modal-batch-expiry').value);
  var ids = Array.from(selectedFiles);
  var count = 0;
  for (var i = 0; i < ids.length; i++) {
    var result = await api().set_file_expiry(ids[i], days);
    if (result.ok) count++;
  }
  closeModal();
  showToast('已修改 ' + count + '/' + ids.length + ' 个文件', 'success');
  loadFiles();
}

function batchSetPassword() {
  showModal('批量设置密码',
    '<input type="text" id="modal-batch-password" placeholder="密码（留空则清除）">' +
    '<button class="btn btn-primary modal-action" data-action="confirm-batch-password">确认</button>'
  );
}

async function doBatchSetPassword() {
  var pw = document.getElementById('modal-batch-password').value;
  var ids = Array.from(selectedFiles);
  var count = 0;
  for (var i = 0; i < ids.length; i++) {
    var result = await api().set_file_password(ids[i], pw);
    if (result.ok) count++;
  }
  closeModal();
  showToast('已设置 ' + count + '/' + ids.length + ' 个文件', 'success');
}

async function batchDeleteFiles() {
  if (!confirm('确定删除 ' + selectedFiles.size + ' 个文件？')) return;
  var ids = Array.from(selectedFiles);
  var result = await api().delete_files(ids);
  showToast('已删除 ' + result.deleted + ' 个文件', 'success');
  loadFiles();
}

function showFileMenu(id) {
  // Store is_collection for modal actions
  _currentModalIsCollection = false;
  for (var i = 0; i < allFiles.length; i++) {
    if (allFiles[i].id === id) { _currentModalIsCollection = allFiles[i].is_collection; break; }
  }
  showModal('文件操作',
    '<button class="btn modal-action" style="width:100%;margin-bottom:8px" data-action="copy-dl-link" data-id="' + id + '">' + iconLink() + ' 复制直链</button>' +
    '<button class="btn modal-action" style="width:100%;margin-bottom:8px" data-action="copy-link" data-id="' + id + '">' + iconCopy() + ' 复制页面链接</button>' +
    '<button class="btn modal-action" style="width:100%;margin-bottom:8px" data-action="qr-code" data-id="' + id + '">' + iconFile() + ' 二维码</button>' +
    '<button class="btn modal-action" style="width:100%;margin-bottom:8px" data-action="open-browser" data-id="' + id + '">' + iconUpload() + ' 在浏览器打开</button>' +
    '<button class="btn modal-action" style="width:100%;margin-bottom:8px" data-action="add-keepalive" data-id="' + id + '">' + iconClock() + ' 加入守护</button>' +
    '<button class="btn modal-action" style="width:100%;margin-bottom:8px" data-action="set-expiry" data-id="' + id + '">' + iconSettings() + ' 修改过期时间</button>' +
    '<button class="btn modal-action" style="width:100%;margin-bottom:8px" data-action="set-password" data-id="' + id + '">' + iconLock() + ' 设置密码</button>' +
    '<button class="btn modal-action" style="width:100%;margin-bottom:8px" data-action="set-downloads" data-id="' + id + '">' + iconBarChart() + ' 设置下载次数</button>' +
    '<button class="btn btn-danger modal-action" style="width:100%" data-action="delete-file" data-id="' + id + '">' + iconTrash() + ' 删除</button>'
  );
}

function handleModalAction(action, id) {
  closeModal();
  switch (action) {
    case 'copy-link': copyFileLink(id); break;
    case 'set-expiry': showSetExpiry(id); break;
    case 'set-password': showSetPassword(id); break;
    case 'set-downloads': showSetDownloads(id); break;
    case 'delete-file': deleteSingleFile(id); break;
  }
}

function showSetExpiry(id) {
  showModal('修改过期时间',
    '<label>天数 (1-7)</label>' +
    '<input type="number" id="modal-expiry-days" min="1" max="7" value="7">' +
    '<button class="btn btn-primary modal-action" data-action="confirm-expiry" data-id="' + id + '">确认</button>'
  );
}

async function doSetExpiry(id) {
  var days = parseInt(document.getElementById('modal-expiry-days').value);
  var result = await api().set_file_expiry(id, days);
  closeModal();
  showToast(result.ok ? '过期时间已更新' : result.error, result.ok ? 'success' : 'error');
  loadFiles();
}

function showSetPassword(id) {
  showModal('设置密码',
    '<input type="text" id="modal-password" placeholder="留空则清除密码">' +
    '<button class="btn btn-primary modal-action" data-action="confirm-password" data-id="' + id + '">确认</button>'
  );
}

async function doSetPassword(id) {
  var pw = document.getElementById('modal-password').value;
  var result = await api().set_file_password(id, pw);
  closeModal();
  showToast(result.ok ? '密码已更新' : result.error, result.ok ? 'success' : 'error');
}

function showSetDownloads(id) {
  showModal('设置最大下载次数',
    '<input type="number" id="modal-max-dl" min="1" max="1000" value="10">' +
    '<button class="btn btn-primary modal-action" data-action="confirm-downloads" data-id="' + id + '">确认</button>'
  );
}

async function doSetDownloads(id) {
  var count = parseInt(document.getElementById('modal-max-dl').value);
  var result = await api().set_max_downloads(id, count);
  closeModal();
  showToast(result.ok ? '已更新' : result.error, result.ok ? 'success' : 'error');
}

async function deleteSingleFile(id) {
  if (!confirm('确定删除此文件？')) return;
  await api().delete_files([id]);
  showToast('已删除', 'success');
  loadFiles();
}

function escHtml(s) {
  var d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}
