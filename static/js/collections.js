async function loadCollections() {
  var container = document.getElementById('collection-list');
  container.innerHTML = '<div class="loading-pulse"></div>';
  var data = await api().list_collections();
  renderCollections(data.collections || []);
}

function renderCollections(collections) {
  var container = document.getElementById('collection-list');
  if (collections.length === 0) {
    container.innerHTML = '<div class="empty-state"><div class="empty-icon" id="coll-empty-icon"></div><p>暂无合集</p><p class="text-muted">创建合集来组织你的文件</p></div>';
    document.getElementById('coll-empty-icon').innerHTML = iconInbox();
    return;
  }
  var html = '';
  for (var i = 0; i < collections.length; i++) {
    var c = collections[i];
    html += '<div class="card">' +
      '<div class="card-title">' + iconFolder() + ' ' + escHtml(c.filename || c.id) + '</div>' +
      '<div class="card-meta">过期: ' + c.expires_at + '</div>' +
      '<div style="background:var(--bg-muted);border-radius:var(--radius-sm);padding:8px;margin:8px 0">' +
      '<div class="text-muted" style="font-size:10px">合集链接</div>' +
      '<div style="color:var(--accent);font-size:11px;word-break:break-all">' + c.url + '</div>' +
      '</div>' +
      '<div class="card-actions">' +
      '<button class="btn btn-sm" onclick="navigator.clipboard.writeText(\'' + c.url + '\');showToast(\'链接已复制\',\'success\')">' + iconCopy() + ' 复制</button>' +
      '<button class="btn btn-sm btn-danger" onclick="deleteColl(\'' + c.id + '\')">' + iconTrash() + ' 删除</button>' +
      '</div></div>';
  }
  container.innerHTML = html;
}

function refreshCollections() { withBtnLoading('coll-refresh-btn', loadCollections); }

function showCreateCollection() {
  showModal('新建合集',
    '<input type="text" id="modal-coll-name" placeholder="合集名称（可选）">' +
    '<button class="btn btn-primary modal-action" data-action="confirm-create-coll">创建</button>'
  );
}

async function doCreateCollection() {
  var name = document.getElementById('modal-coll-name').value;
  var result = await api().create_collection(name);
  closeModal();
  if (result.ok) {
    showToast('合集已创建', 'success');
    loadCollections();
  } else {
    showToast(result.error, 'error');
  }
}

async function deleteColl(id) {
  if (!confirm('确定删除此合集？')) return;
  var result = await api().delete_collection(id);
  showToast(result.ok ? '已删除' : result.error, result.ok ? 'success' : 'error');
  loadCollections();
}
