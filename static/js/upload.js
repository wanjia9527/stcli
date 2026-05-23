var uploadQueue = [];
var isUploading = false;
var uploadPollTimer = null;

var dropzone = document.getElementById('upload-dropzone');

dropzone.addEventListener('dragover', function(e) { e.preventDefault(); dropzone.classList.add('dragover'); });
dropzone.addEventListener('dragleave', function() { dropzone.classList.remove('dragover'); });

document.getElementById('upload-input').addEventListener('click', function(e) {
  e.preventDefault();
  pickFilesFromDialog();
});

// Prevent browser from opening dragged files globally
document.addEventListener('dragover', function(e) { e.preventDefault(); });
document.addEventListener('drop', function(e) { e.preventDefault(); });

async function pickFilesFromDialog() {
  var result = await api().browse_files('选择要上传的文件');
  if (!result.paths || result.paths.length === 0) return;
  for (var i = 0; i < result.paths.length; i++) {
    var p = result.paths[i];
    if (p) {
      uploadQueue.push({ path: p, name: p.split(/[\\/]/).pop(), size: 0, status: 'waiting', percent: 0, speed: '', eta: '', error: '' });
    }
  }
  renderQueue();
}

function renderQueue() {
  var container = document.getElementById('upload-queue');
  var actions = document.getElementById('upload-actions');
  var globalBar = document.getElementById('upload-progress-global');

  if (uploadQueue.length === 0) {
    container.innerHTML = '';
    actions.classList.add('hidden');
    globalBar.classList.add('hidden');
    return;
  }

  actions.classList.remove('hidden');
  if (isUploading) globalBar.classList.remove('hidden');

  var html = '';
  for (var i = 0; i < uploadQueue.length; i++) {
    var item = uploadQueue[i];
    var statusClass = item.status;
    var statusText;
    if (item.status === 'done') {
      statusText = '<span style="color:var(--green)">' + iconCheck() + ' 已完成</span>';
    } else if (item.status === 'error') {
      statusText = '<span style="color:var(--red)">' + iconX() + ' ' + escHtml(item.error || '失败') + '</span>';
    } else if (item.status === 'uploading') {
      statusText = item.percent.toFixed(0) + '%';
    } else {
      statusText = '等待中...';
    }

    html += '<div class="queue-item ' + statusClass + '">' +
      '<div class="queue-header"><span>' + escHtml(item.name) + '</span><span>' + statusText + '</span></div>';
    if (item.status === 'uploading') {
      html += '<div class="progress-bar"><div class="progress-fill" style="width:' + item.percent + '%"></div></div>' +
        '<div class="queue-meta"><span>' + (item.speed || '') + '</span><span>' + (item.eta || '') + '</span></div>';
    }
    html += '</div>';
  }
  container.innerHTML = html;
}

function clearQueue() {
  uploadQueue = [];
  isUploading = false;
  if (uploadPollTimer) { clearInterval(uploadPollTimer); uploadPollTimer = null; }
  renderQueue();
}

// Poll upload progress from Python backend
function startUploadPolling(pendingItems, total, onComplete) {
  if (uploadPollTimer) clearInterval(uploadPollTimer);

  uploadPollTimer = setInterval(async function() {
    var progress = await api().get_upload_progress();
    var allDone = true;

    for (var i = 0; i < pendingItems.length; i++) {
      var item = pendingItems[i];
      var p = progress[item.name];
      if (!p) continue;

      if (p.done) {
        if (item.status !== 'done' && item.status !== 'error') {
          item.status = p.result && p.result.ok ? 'done' : 'error';
          item.percent = p.result && p.result.ok ? 100 : 0;
          item.error = (p.result && p.result.error) || '';
        }
      } else {
        allDone = false;
        item.status = 'uploading';
        item.percent = p.percent || 0;
        item.speed = p.speed || '';
        item.eta = p.eta || '';
      }
    }

    // Update global progress
    var completedCount = 0;
    for (var j = 0; j < pendingItems.length; j++) {
      if (pendingItems[j].status === 'done' || pendingItems[j].status === 'error') completedCount++;
    }
    var globalPct = (completedCount / total * 100).toFixed(0);
    document.getElementById('global-progress-fill').style.width = globalPct + '%';
    document.getElementById('global-progress-text').textContent = completedCount + '/' + total + ' · ' + globalPct + '%';

    renderQueue();

    if (allDone) {
      clearInterval(uploadPollTimer);
      uploadPollTimer = null;
      onComplete();
    }
  }, 200);
}

async function startUpload() {
  if (isUploading) return;

  if (uploadQueue.length === 0) {
    await pickFilesFromDialog();
    if (uploadQueue.length === 0) return;
  }

  isUploading = true;
  var pending = uploadQueue.filter(function(i) { return i.status === 'waiting'; });
  var total = pending.length;
  if (total === 0) { isUploading = false; return; }

  document.getElementById('upload-progress-global').classList.remove('hidden');

  // Upload files sequentially, polling progress for each
  var completedCount = 0;
  for (var idx = 0; idx < pending.length; idx++) {
    var item = pending[idx];
    item.status = 'uploading';
    item.percent = 0;
    renderQueue();

    // Start background upload
    await api().upload_file(item.path);

    // Poll until this file is done
    await new Promise(function(resolve) {
      var poll = setInterval(async function() {
        var progress = await api().get_upload_progress();
        var p = progress[item.name];
        if (p && p.done) {
          clearInterval(poll);
          item.status = p.result && p.result.ok ? 'done' : 'error';
          item.percent = p.result && p.result.ok ? 100 : 0;
          item.error = (p.result && p.result.error) || '';
          completedCount++;
          // Update global progress
          var globalPct = (completedCount / total * 100).toFixed(0);
          document.getElementById('global-progress-fill').style.width = globalPct + '%';
          document.getElementById('global-progress-text').textContent = completedCount + '/' + total + ' · ' + globalPct + '%';
          renderQueue();
          resolve();
        } else if (p) {
          item.percent = p.percent || 0;
          item.speed = p.speed || '';
          item.eta = p.eta || '';
          renderQueue();
        }
      }, 200);
    });
  }

  isUploading = false;
  var okCount = pending.filter(function(i) { return i.status === 'done'; }).length;
  showToast('上传完成: ' + okCount + '/' + total, okCount === total ? 'success' : 'error');
}
