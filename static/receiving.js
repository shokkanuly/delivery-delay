'use strict';
(() => {
  const $ = (id) => document.getElementById(id);
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const state = {mode:null, credential: '', actor: null, plans: [], receipts: [], total: 0, location: null, correction: null, syncing: false, stream: null};
  const labels = {recorded:'Записано',confirmed:'Подтверждено',disputed:'Есть спор',expected:'Ожидается',completed:'Завершено',cancelled:'Отменено',local:'На устройстве',uploading:'Отправка',error:'Нужна проверка',synced:'Получено сервером'};
  const missingLabels = {delivery_match:'Не сопоставлена поставка',attachment:'Нет фото / талона',receiver_confirmation:'Нет подтверждения получателя',real_provenance:'Учебная запись SIM'};
  const dbReady = new Promise((resolve, reject) => {
    const req = indexedDB.open('sitepulse-receiving-v1', 1);
    req.onupgradeneeded = () => {req.result.createObjectStore('drafts', {keyPath:'id'});req.result.createObjectStore('context', {keyPath:'id'});};
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  async function transaction(store, mode, fn) {
    const db = await dbReady;
    return new Promise((resolve,reject) => {
      const tx = db.transaction(store, mode); let result;
      const req = fn(tx.objectStore(store));
      req.onsuccess = () => { result = req.result; };
      tx.oncomplete = () => resolve(result);
      tx.onerror = () => reject(tx.error || req.error);
      tx.onabort = () => reject(tx.error || new Error('Локальное сохранение прервано'));
    });
  }
  const read = (store,id) => transaction(store,'readonly',s=>s.get(id));
  const write = (store,value) => transaction(store,'readwrite',s=>s.put(value));
  const remove = (store,id) => transaction(store,'readwrite',s=>s.delete(id));
  const allDrafts = () => transaction('drafts','readonly',s=>s.getAll());
  async function ownDrafts() {return (await allDrafts()).filter(d => d.actorId === state.actor?.id && d.siteId === state.actor?.site.id);}
  function message(text,error=false) {$('message').textContent=text;$('message').classList.toggle('error',error);$('message').hidden=false;}
  function errorText(error) {return error?.name === 'QuotaExceededError' ? 'Хранилище устройства заполнено. Запись НЕ сохранена. Освободите место или сохраните резервную копию.' : error.message || String(error);}
  async function api(path, options={}) {
    if (!state.credential) throw new Error('Войдите по личному ключу для работы с сервером. Локальные записи сохранены.');
    const headers = {Authorization:`Bearer ${state.credential}`, ...options.headers};
    if (options.body && !(options.body instanceof FormData)) {headers['Content-Type']='application/json';options.body=JSON.stringify(options.body);}
    const response = await fetch('/receiving'+path,{...options,headers,cache:'no-store'});
    if (!response.ok) {
      const data = await response.json().catch(()=>({detail:'Ошибка сервера'}));
      if (response.status===401) {state.credential='';$('login-panel').hidden=false;connection();}
      const detail = Array.isArray(data.detail) ? data.detail.map(x=>`${x.loc?.join('.')}: ${x.msg}`).join('; ') : data.detail;
      throw new Error(`${response.status}: ${detail || 'Не удалось выполнить запрос'}`);
    }
    return options.raw ? response : response.json();
  }
  function badge(text,cls='') {return `<span class="badge ${cls}">${esc(text)}</span>`;}
  function statusBadge(status) {return badge(labels[status]||status,status==='confirmed'?'ok':status==='disputed'?'risk':'warn');}
  function dateText(value) {return value ? new Date(value).toLocaleString('ru-RU',{timeZone:state.actor?.site.timezone||'Asia/Almaty',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}) : 'Не указано';}
  function localInput(date=new Date()) {return new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16);}
  function connection() {
    $('mode-badge').textContent=navigator.onLine?(state.mode||'ПРИЁМКА'):'БЕЗ СЕТИ';
    $('connection').textContent = navigator.onLine ? (state.credential?'Онлайн · вход выполнен':'Онлайн · нужен вход') : 'Без сети · локальное сохранение';
    $('connection-dot').classList.toggle('offline',!navigator.onLine || !state.credential);
  }
  function show(view) {
    if (!state.actor && view!=='queue') {message('Сначала откройте объект по личному ключу.',true);return;}
    document.querySelectorAll('.view').forEach(el=>el.hidden=el.id!==`view-${view}`);
    document.querySelectorAll('.nav').forEach(el=>el.classList.toggle('active',el.dataset.view===view));
    stopCamera();
    if(view==='queue') renderQueue().catch(e=>message(errorText(e),true));
    if(view==='documents') loadDocuments().catch(e=>message(errorText(e),true));
    if(view==='slots') loadSlots().catch(e=>message(errorText(e),true));
    if(view==='today'&&state.credential&&state.actor?.features.operations)loadNotifications().catch(e=>message(errorText(e),true));
    if(view==='capture' && !state.correction) $('observed-at').value=localInput();
  }
  function bindNavigation() {
    document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>show(b.dataset.view)));
    document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>{if(b.dataset.go==='capture')resetCapture();show(b.dataset.go);}));
  }
  function addLine(target,line={}) {
    const container=$(target); const row=document.createElement('div');row.className='line-row';
    row.innerHTML=`<label>Строка<input data-field="line_id" required maxlength="64" value="${esc(line.line_id || String(container.children.length+1))}"></label><label>Материал<input data-field="material" required maxlength="160" value="${esc(line.material||'')}" placeholder="Арматура"></label><label>Количество<input data-field="quantity" required inputmode="decimal" pattern="[0-9]+([.,][0-9]{1,6})?" value="${esc(line.quantity||'')}" placeholder="10,25"></label><label>Ед.<input data-field="unit" required maxlength="20" value="${esc(line.unit||'')}" placeholder="т"></label><button type="button" class="remove-line" aria-label="Удалить строку">×</button>`;
    row.querySelector('button').addEventListener('click',()=>row.remove());container.append(row);
  }
  function getLines(target) {
    const rows=[...$(target).children].map(row=>Object.fromEntries([...row.querySelectorAll('[data-field]')].map(i=>[i.dataset.field,i.dataset.field==='quantity'?i.value.trim().replace(',','.'):i.value.trim()] )));
    if(!rows.length || new Set(rows.map(r=>r.line_id)).size!==rows.length)throw new Error('Добавьте материалы с уникальными номерами строк.');
    if(rows.some(r=>!r.material||!r.unit||!r.line_id||!/^\d+(\.\d{1,6})?$/.test(r.quantity)||Number(r.quantity)<=0))throw new Error('Проверьте материал, единицу и положительное количество каждой строки.');
    return rows;
  }
  function renderPlanSelect() {
    const selected=$('capture-plan').value;
    $('capture-plan').innerHTML='<option value="">Не найден / вне плана</option>'+state.plans.filter(p=>p.status==='expected'||p.id===state.correction?.payload.plan_id).map(p=>`<option value="${esc(p.id)}">${esc(p.reference)} · ${esc(p.supplier)} · ${esc(p.provenance)}</option>`).join('');
    if([...$('capture-plan').options].some(o=>o.value===selected))$('capture-plan').value=selected;
    $('document-plan').innerHTML=state.plans.map(p=>`<option value="${esc(p.id)}">${esc(p.reference)} · ${esc(p.supplier)}</option>`).join('');
  }
  function planDate(p) {return p.promised_date || `${dateText(p.window_start)} – ${dateText(p.window_end)}`;}
  function renderPlans() {
    const active=state.plans.filter(p=>p.status==='expected');
    $('plan-list').innerHTML=active.length ? `<div class="table-wrap"><table><thead><tr><th>ПОСТАВКА / ПОСТАВЩИК</th><th>МАТЕРИАЛ</th><th>ОЖИДАЕТСЯ</th><th>ИСТОЧНИК</th><th></th></tr></thead><tbody>${active.map(p=>`<tr><td><strong>${esc(p.reference)}</strong><small>${esc(p.supplier)}</small></td><td>${p.lines.map(l=>`${esc(l.material)} · ${esc(l.quantity)} ${esc(l.unit)}`).join('<br>')}</td><td>${esc(planDate(p))}</td><td>${badge(p.provenance,p.provenance==='SIM'?'sim':'')}</td><td><button class="row-button" data-capture-plan="${esc(p.id)}">Принять →</button><button class="row-button" data-open-plan="${esc(p.id)}">План / факт</button></td></tr>`).join('')}</tbody></table></div>` : '<div class="empty"><strong>Нет ожидаемых поставок</strong>Координатор может добавить план. Прибытие вне плана тоже можно записать.</div>';
    $('plan-list').querySelectorAll('[data-capture-plan]').forEach(b=>b.addEventListener('click',()=>{resetCapture();$('capture-plan').value=b.dataset.capturePlan;fillFromPlan();show('capture');}));
    const closed=state.plans.filter(p=>p.status!=='expected');
    $('closed-plan-list').innerHTML=closed.length?closed.map(p=>`<div class="file-row"><span>${esc(p.reference)} · ${esc(p.supplier)} · ${esc(labels[p.status])}</span><button class="row-button" data-open-plan="${p.id}">План / факт</button></div>`).join(''):'<p class="muted">Закрытых планов нет.</p>';
    for(const container of ['plan-list','closed-plan-list'])$(container).querySelectorAll('[data-open-plan]').forEach(b=>b.addEventListener('click',()=>openPlan(b.dataset.openPlan).catch(e=>message(errorText(e),true))));
    renderPlanSelect();
  }
  function renderReceipts() {
    const list=state.receipts;
    const counts=[['Ожидается',state.plans.filter(p=>p.status==='expected').length,'активных планов'],['Записано',state.total,'всего записей на сервере'],['Подтверждено',list.filter(r=>r.current.evidence_status==='confirmed').length,'среди загруженных записей'],['Нужна проверка',list.filter(r=>r.current.needs_review).length,'среди загруженных записей']];
    $('stats').innerHTML=counts.map(([label,n,hint])=>`<div class="stat"><span>${label}</span><strong>${n}</strong><small>${hint}</small></div>`).join('');
    const table=(rows)=>rows.length?`<div class="table-wrap"><table><thead><tr><th>ПОСТАВКА</th><th>ПРИБЫТИЕ</th><th>СОСТОЯНИЕ</th><th>ИСТОЧНИК</th><th></th></tr></thead><tbody>${rows.map(r=>`<tr><td><strong>${esc(r.current.payload.reference)}</strong><small>Версия ${r.current_revision} · ${esc(r.current.payload.lines.map(l=>l.material).join(', '))}</small></td><td>${esc(dateText(r.current.payload.observed_at))}</td><td>${statusBadge(r.current.evidence_status)}</td><td>${badge(r.current.payload.provenance,r.current.payload.provenance==='SIM'?'sim':'')}</td><td><button class="row-button" data-receipt="${r.receipt_id}">Открыть →</button></td></tr>`).join('')}</tbody></table></div>`:'<div class="empty"><strong>Пока нет записей</strong>Зафиксируйте прибытие и отправьте его с устройства.</div>';
    $('receipt-list').innerHTML=table(list);
    $('exception-list').innerHTML=table(list.filter(r=>r.current.needs_review));
    for(const id of ['receipt-list','exception-list'])$(id).querySelectorAll('[data-receipt]').forEach(b=>b.addEventListener('click',()=>openReceipt(b.dataset.receipt).catch(e=>message(errorText(e),true))));
    $('load-more').hidden=list.length>=state.total;
  }
  async function refresh(append=false) {
    const [planData, receiptData]=await Promise.all([api('/plans?limit=200'),api(`/receipts?limit=50&offset=${append?state.receipts.length:0}`)]);
    state.plans=planData.plans;state.total=receiptData.total;state.receipts=append?[...state.receipts,...receiptData.receipts]:receiptData.receipts;
    await write('context',{id:`plans:${state.actor.site.id}`,plans:state.plans});
    renderPlans();renderReceipts();
    if(planData.total>200)message('Показаны последние 200 планов. Для более ранней поставки используйте ручной номер.');
  }
  function actorUI() {
    $('site-name').textContent=state.actor.site.name;$('actor-label').textContent=state.actor.name;
    $('sign-out').hidden=false;$('plan-editor').hidden=state.actor.role!=='coordinator';
    $('coverage-nav').hidden=state.actor.role!=='coordinator';
    $('documents-nav').hidden=!state.actor.features?.reconciliation;
    $('slots-nav').hidden=!state.actor.features?.operations;
    $('notifications-panel').hidden=!state.actor.features?.operations;
    $('resource-editor').hidden=state.actor.role!=='coordinator';
    $('slot-editor').hidden=state.actor.role==='viewer';
    $('capture-form').querySelector('button[type=submit]').disabled=state.actor.role==='viewer';
  }
  function clearRemoteViews() {
    for(const id of ['receipt-detail','plan-detail','coverage-result','document-list','notification-list','supplier-history','slot-list','plan-list','closed-plan-list','receipt-list','exception-list'])$(id).replaceChildren();
  }
  $('login-form').addEventListener('submit',async event=>{
    event.preventDefault();state.credential=$('credential').value.trim();$('credential').value='';
    try{const actor=await api('/me');const changed=state.actor?.id!==actor.id;clearRemoteViews();state.actor=actor;if(changed){state.plans=[];state.receipts=[];state.total=0;resetCapture();}await write('context',{id:'lastActor',actor:state.actor});actorUI();$('login-panel').hidden=true;await refresh();await renderQueue();show('today');connection();message('Объект открыт. Локальные записи доступны только для вашего профиля.');}
    catch(e){state.credential='';connection();message(errorText(e),true);}
  });
  $('sign-out').addEventListener('click',async()=>{
    try{const drafts=await ownDrafts();if(drafts.some(d=>d.status!=='synced')&&!confirm('Есть неотправленные записи. Выйти и оставить их на этом устройстве до следующего входа тем же ключом?'))return;
      await remove('context','lastActor');await remove('context',`plans:${state.actor.site.id}`);
      clearRemoteViews();state.credential='';state.actor=null;state.plans=[];state.receipts=[];$('login-panel').hidden=false;$('sign-out').hidden=true;
      document.querySelectorAll('.view').forEach(v=>v.hidden=true);$('site-name').textContent='Войдите в свой объект';$('actor-label').textContent='Вход не выполнен';$('queue-count').textContent='0';resetCapture();connection();message('Вы вышли. Неотправленные записи сохранены для прежнего профиля.');
    }catch(e){message(errorText(e),true);}
  });
  $('plan-form').addEventListener('submit',async event=>{
    event.preventDefault();try{const body=Object.fromEntries(new FormData(event.target));body.lines=getLines('plan-lines');await api('/plans',{method:'POST',body});event.target.reset();$('plan-lines').replaceChildren();addLine('plan-lines');await refresh();message('План поставки создан.');}catch(e){message(errorText(e),true);}
  });
  function resetCapture() {state.correction=null;state.location=null;$('capture-form').reset();$('capture-lines').replaceChildren();addLine('capture-lines');$('observed-at').value=localInput();$('capture-title').textContent='Зафиксировать прибытие';$('correction-reason-label').hidden=true;$('correction-reason').required=false;$('location-status').textContent='Не получена — запись всё равно можно сохранить';renderPlanSelect();}
  function fillFromPlan() {
    const plan=state.plans.find(p=>p.id===$('capture-plan').value);if(!plan)return;
    $('capture-ref').value=plan.reference;$('capture-provenance').value=plan.provenance;$('capture-lines').replaceChildren();plan.lines.forEach(l=>addLine('capture-lines',l));
    message('Количество перенесено из плана. Проверьте и укажите фактически прибывшее количество.');
  }
  $('capture-plan').addEventListener('change',fillFromPlan);
  $('get-location').addEventListener('click',()=>{
    if(!navigator.geolocation){message('Геопозиция недоступна. Можно сохранить без неё.',true);return;}
    navigator.geolocation.getCurrentPosition(pos=>{state.location={latitude:pos.coords.latitude,longitude:pos.coords.longitude,accuracy_m:pos.coords.accuracy};$('location-status').textContent=`Получена · точность ±${Math.round(pos.coords.accuracy)} м`;},()=>{$('location-status').textContent='Нет разрешения или сигнала. Геопозиция не добавлена.';state.location=null;},{enableHighAccuracy:true,timeout:10000,maximumAge:0});
  });
  $('capture-form').addEventListener('submit',async event=>{
    event.preventDefault();const button=event.target.querySelector('button[type=submit]');button.disabled=true;
    try{
      if(!state.actor)throw new Error('Нет локального профиля. Сначала войдите онлайн.');
      const files=[...$('evidence-files').files];if(files.length>6||files.some(f=>f.size>5*1024*1024))throw new Error('До 6 файлов, каждый не более 5 МБ.');
      const selected=state.plans.find(p=>p.id===$('capture-plan').value);
      const payload={...(state.correction?.payload||{}),plan_id:selected?.id||null,reference:$('capture-ref').value.trim(),observed_at:new Date($('observed-at').value).toISOString(),time_source:$('time-source').value,location:state.location,provenance:$('capture-provenance').value,lines:getLines('capture-lines'),condition:$('condition').value,note:$('capture-note').value.trim(),document_references:$('document-refs').value.split(',').map(s=>s.trim()).filter(Boolean)};
      const operationId=crypto.randomUUID();
      const body=state.correction?{operation_id:operationId,expected_revision:state.correction.revision,reason:$('correction-reason').value.trim(),payload}:{receipt_id:crypto.randomUUID(),operation_id:operationId,payload};
      if(state.correction&&body.reason.length<3)throw new Error('Укажите причину исправления.');
      const draft={id:operationId,actorId:state.actor.id,siteId:state.actor.site.id,body,receiptId:state.correction?.receiptId||body.receipt_id,correction:!!state.correction,files:await Promise.all(files.map(evidenceFile)),uploadedFiles:[],status:'local',savedAt:new Date().toISOString(),error:null};
      await write('drafts',draft);try{Promise.resolve(navigator.storage?.persist?.()).catch(()=>{});}catch{/* Persistence permission is optional; never wait for its prompt after a committed save. */}resetCapture();await renderQueue();show('queue');message('Сохранено на устройстве. Отправьте запись, когда появится связь.');
    }catch(e){message(errorText(e),true);}finally{button.disabled=state.actor?.role==='viewer';}
  });
  async function evidenceFile(file) {
    const bytes=await file.arrayBuffer(),b=new Uint8Array(bytes);
    const isPNG=[137,80,78,71,13,10,26,10].every((v,i)=>b[i]===v);
    const isPDF=[37,80,68,70,45].every((v,i)=>b[i]===v);
    const type=isPNG?'image/png':b[0]===255&&b[1]===216&&b[2]===255?'image/jpeg':isPDF?'application/pdf':null;
    if(!type)throw new Error('Используйте JPEG, PNG или PDF. Файл не распознан; запись ещё не сохранена.');
    // ArrayBuffer avoids browser-specific IndexedDB Blob/File storage failures.
    return {name:file.name,type,bytes};
  }
  function draftBlob(file) {
    if(file.bytes instanceof ArrayBuffer)return new Blob([file.bytes],{type:file.type});
    if(file.blob instanceof Blob)return file.blob; // Existing v1 drafts remain readable.
    throw new Error('Файл черновика повреждён. Сохраните копию для восстановления.');
  }
  async function renderQueue() {
    const drafts=await ownDrafts();$('queue-count').textContent=String(drafts.filter(d=>d.status!=='synced').length);
    $('queue-list').innerHTML=drafts.length?drafts.sort((a,b)=>b.savedAt.localeCompare(a.savedAt)).map(d=>`<div class="queue-row"><div><strong>${esc(d.body.payload.reference)}</strong> ${badge(d.body.payload.provenance,d.body.payload.provenance==='SIM'?'sim':'')}<p>${esc(dateText(d.savedAt))} · ${d.files.length} файл(ов) · ${d.correction?'исправление':'прибытие'}</p>${statusBadge(d.status)}${d.error?`<p class="danger">${esc(d.error)}</p>`:''}</div><div class="queue-actions">${d.status==='synced'?`<button class="secondary" data-open-draft="${d.receiptId}">Открыть запись</button>`:`<button class="secondary" data-sync-draft="${d.id}">Отправить</button>`}<button class="text-button" data-backup-draft="${d.id}">Скачать копию</button><button class="text-button danger" data-delete-draft="${d.id}">Удалить локально</button></div></div>`).join(''):'<div class="empty"><strong>Локальных записей нет</strong>Здесь появятся прибытия, сохранённые с этого устройства.</div>';
    $('queue-list').querySelectorAll('[data-open-draft]').forEach(b=>b.addEventListener('click',()=>openReceipt(b.dataset.openDraft).catch(e=>message(errorText(e),true))));
    $('queue-list').querySelectorAll('[data-sync-draft]').forEach(b=>b.addEventListener('click',()=>syncAll(b.dataset.syncDraft)));
    $('queue-list').querySelectorAll('[data-backup-draft]').forEach(b=>b.addEventListener('click',()=>exportDrafts(b.dataset.backupDraft)));
    $('queue-list').querySelectorAll('[data-delete-draft]').forEach(b=>b.addEventListener('click',async()=>{if(state.syncing){message('Дождитесь завершения отправки перед удалением локальной копии.',true);return;}const d=await read('drafts',b.dataset.deleteDraft);if(!d)return;if(confirm(d.status==='synced'?'Удалить локальную копию? Запись на сервере останется.':'Запись ещё не отправлена. Удалить её и файлы без возможности восстановления?')){await remove('drafts',d.id);await renderQueue();}}));
  }
  async function syncAll(onlyId=null) {
    if(state.syncing)return;
    if(!state.credential){message('Для отправки войдите тем же личным ключом. Черновики сохранены.',true);$('login-panel').hidden=false;return;}
    const run=async()=>{
      state.syncing=true;$('sync-all').disabled=true;
      try{
        for(const draft of await ownDrafts()) {
          if(draft.status==='synced'||(onlyId&&draft.id!==onlyId))continue;
          try{
            draft.status='uploading';draft.error=null;await write('drafts',draft);await renderQueue();
            const url=draft.correction?`/receipts/${draft.receiptId}/corrections`:'/receipts';
            const response=await api(url,{method:'POST',body:draft.body});draft.appliedRevision=response.applied_revision;await write('drafts',draft);
            for(let i=0;i<draft.files.length;i++){
              if(draft.uploadedFiles.includes(i))continue;const form=new FormData();form.append('file',draftBlob(draft.files[i]),draft.files[i].name);
              await api(`/receipts/${draft.receiptId}/revisions/${draft.appliedRevision}/attachments`,{method:'POST',body:form});draft.uploadedFiles.push(i);await write('drafts',draft);
            }
            draft.status='synced';draft.error=null;await write('drafts',draft);
          }catch(e){draft.status='error';draft.error=errorText(e);await write('drafts',draft);if(!state.credential)break;}
        }
        await renderQueue();if(state.credential)await refresh();
        message((await ownDrafts()).some(d=>d.status==='error')?'Часть записей требует проверки. Они сохранены на устройстве.':'Отправка завершена. Подтвердите приёмку в карточке поставки.',(await ownDrafts()).some(d=>d.status==='error'));
      }catch(e){message(errorText(e),true);}finally{state.syncing=false;$('sync-all').disabled=false;}
    };
    if(navigator.locks)await navigator.locks.request('sitepulse-receiving-sync',run);else await run();
  }
  function download(blob,name){const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);}
  async function openReceipt(id) {
    const packet=await api(`/receipts/${id}`);const current=packet.current,p=current.payload;
    $('receipt-detail').innerHTML=`<div class="page-heading"><div><p class="eyebrow">ПОСТАВКА / ВЕРСИЯ ${packet.current_revision}</p><h1>${esc(p.reference)}</h1><p class="muted">Прибытие ${esc(dateText(p.observed_at))} · ${esc(current.recorded_by.name)}</p>${statusBadge(current.evidence_status)} ${badge(p.provenance,p.provenance==='SIM'?'sim':'')}</div><div class="detail-actions"><button id="export-packet" class="secondary">Скачать пакет JSON</button><button id="print-packet" class="secondary">Печать</button><button id="correct-packet" class="secondary">Исправить запись</button></div></div><div class="detail-grid"><div><div class="card"><h2>Фактически прибыло</h2>${current.plan?`<p class="hint">План: ${esc(current.plan.supplier)} · ${esc(planDate(current.plan))}</p>`:''}<div class="table-wrap"><table><thead><tr><th>СТРОКА</th><th>МАТЕРИАЛ</th><th>КОЛИЧЕСТВО</th></tr></thead><tbody>${p.lines.map(l=>`<tr><td>${esc(l.line_id)}</td><td>${esc(l.material)}</td><td>${esc(l.quantity)} ${esc(l.unit)}</td></tr>`).join('')}</tbody></table></div><p class="hint">Состояние: ${esc({ok:'без замечаний',damaged:'повреждение',uncertain:'нужна проверка'}[p.condition])}. Геопозиция: ${p.location?'получена':'не получена'}.</p><p>${esc(p.note)}</p><p class="hint">Документы: ${esc(p.document_references.join(', ')||'не указаны')}</p><div class="notice">${current.missing.length?current.missing.map(m=>esc(missingLabels[m])).join(' · '):'Полная запись с подтверждением получателя'}${current.partial_acceptance?'<br>Принято меньше прибывшего количества.':''}${(current.plan_comparison||[]).some(x=>x.status!=='matched')?'<br>Есть расхождение количества, материала или единицы с планом. Сопоставьте строки перед закрытием поставки.':''}${current.time_warning?'<br>Время устройства отличается от времени получения сервером. Проверьте часы и задержку отправки.':''}</div></div><div class="card"><h2>Файлы доказательств</h2>${current.attachments.length?current.attachments.map((f,i)=>`<div class="file-row"><span>Файл ${i+1} · ${esc(f.content_type)} · ${Math.ceil(f.size/1024)} КБ</span><button class="row-button" data-file="${f.id}">Скачать</button></div>`).join(''):'<p class="muted">Фото или талон не приложены. Добавьте их через новую версию записи.</p>'}</div><div class="card"><h2>История</h2>${packet.revisions.map(rev=>`<div class="revision-card"><strong>Версия ${rev.number}${rev.superseded?' · заменена':''}</strong><p class="hint">${esc(dateText(rev.received_at))} · ${esc(rev.recorded_by.name)}</p>${rev.reason?`<p>${esc(rev.reason)}</p>`:''}<div class="timeline">${rev.attestations.map(a=>`<p><strong>${esc(labels[a.decision])} · ${esc(a.actor_name)}</strong>${esc(dateText(a.at))}${a.reason?' · '+esc(a.reason):''}<br>${a.accepted.map(l=>`Строка ${esc(l.line_id)}: ${esc(l.quantity)}`).join(' · ')}</p>`).join('')||'<p>Без подтверждения получателя</p>'}</div><details><summary>Исходные данные версии</summary><pre class="revision-json"></pre></details></div>`).join('')}</div></div><div><div class="card" id="decision-card"><h2>Решение получателя</h2><p class="hint">Подтверждается только текущая версия. Укажите принятое количество по каждой строке.</p><form id="decision-form" class="decision-form">${p.lines.map(l=>`<label class="decision-line">${esc(l.material)} · ${esc(l.unit)}<input data-accepted-line="${esc(l.line_id)}" value="${esc(l.quantity)}" required inputmode="decimal"></label>`).join('')}<label>Решение<select name="decision"><option value="confirmed">Подтвердить приёмку</option><option value="disputed">Открыть спор</option></select></label><label>Причина / замечание<textarea name="reason" maxlength="1000" rows="3"></textarea></label><button class="primary">Записать решение</button></form></div><div class="card"><h3>О записи</h3><p class="hint">Получено сервером: ${esc(dateText(current.received_at))}</p><p class="hint">Запись фиксирует наблюдения и решение получателя. Фото, QR и хеш сами по себе не доказывают физическую поставку.</p><p class="hint">Идентификатор: ${esc(id)}</p></div><div id="grant-card" class="card" hidden><h3>Ограниченный доступ к данным</h3><p class="hint">Только согласованному получателю: количество и время, без фото, GPS и имён. Доступ истекает или отзывается.</p><form id="grant-form" class="grant-form"><label>Получатель<input name="recipient" required maxlength="160"></label><label>Цель<input name="purpose" required minlength="3" maxlength="500"></label><label>Основание согласия<input name="consent_reference" required minlength="3" maxlength="200"></label><label>Действует до<input name="expires_at" type="datetime-local" required></label><button class="secondary">Создать доступ</button></form><div id="grant-result"></div><div id="grant-list"></div></div></div></div>`;
    [...$('receipt-detail').querySelectorAll('.revision-json')].forEach((el,i)=>{el.textContent=JSON.stringify(packet.revisions[i].payload,null,2);el.style.whiteSpace='pre-wrap';el.style.wordBreak='break-word';});
    $('decision-card').hidden=state.actor.role==='viewer';$('correct-packet').hidden=state.actor.role==='viewer';
    $('grant-card').hidden=!state.actor.features.partner_sharing||state.actor.role!=='coordinator';
    $('export-packet').addEventListener('click',async()=>{try{const result=await api(`/receipts/${id}/export`);download(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}),`receipt-${id}.json`);}catch(e){message(errorText(e),true);}});
    $('print-packet').addEventListener('click',()=>window.print());
    $('correct-packet').addEventListener('click',()=>{resetCapture();state.correction={receiptId:id,revision:packet.current_revision,payload:p};if(current.plan&&!state.plans.some(plan=>plan.id===current.plan.id))state.plans.push({...current.plan,status:'historical'});renderPlanSelect();$('capture-plan').value=p.plan_id||'';$('capture-ref').value=p.reference;$('observed-at').value=localInput(new Date(p.observed_at));$('time-source').value=p.time_source;$('capture-provenance').value=p.provenance;$('condition').value=p.condition;$('capture-note').value=p.note;$('document-refs').value=p.document_references.join(', ');state.location=p.location;if(p.location)$('location-status').textContent=`Геопозиция исходной версии · точность ±${Math.round(p.location.accuracy_m)} м`;$('capture-lines').replaceChildren();p.lines.forEach(l=>addLine('capture-lines',l));$('capture-title').textContent=`Исправление · версия ${packet.current_revision+1}`;$('correction-reason-label').hidden=false;$('correction-reason').required=true;show('capture');message('Исходная версия сохранится. Для новой версии приложите актуальные файлы и получите новое подтверждение.');});
    $('receipt-detail').querySelectorAll('[data-file]').forEach(b=>b.addEventListener('click',async()=>{try{const response=await api(`/attachments/${b.dataset.file}`,{raw:true});const type=response.headers.get('content-type');download(await response.blob(),`evidence-${b.dataset.file}.${type.includes('pdf')?'pdf':type.includes('png')?'png':'jpg'}`);}catch(e){message(errorText(e),true);}}));
    const priorDecision=current.attestations.at(-1);
    if(priorDecision){
      $('decision-form').querySelector('[name=decision]').value=priorDecision.decision;
      $('decision-form').querySelectorAll('[data-accepted-line]').forEach(input=>{
        const prior=priorDecision.accepted.find(line=>line.line_id===input.dataset.acceptedLine);if(prior)input.value=prior.quantity;
      });
    }
    $('decision-form').addEventListener('submit',async event=>{event.preventDefault();const b=event.target.querySelector('button');b.disabled=true;try{const form=Object.fromEntries(new FormData(event.target));await api(`/receipts/${id}/decisions`,{method:'POST',body:{...form,decision_id:crypto.randomUUID(),expected_revision:packet.current_revision,accepted:[...event.target.querySelectorAll('[data-accepted-line]')].map(i=>({line_id:i.dataset.acceptedLine,quantity:i.value.trim().replace(',','.')}))}});await refresh();await openReceipt(id);message('Решение записано в истории.');}catch(e){message(errorText(e),true);b.disabled=false;}});
    $('grant-form').addEventListener('submit',async event=>{event.preventDefault();try{const form=Object.fromEntries(new FormData(event.target));form.expires_at=new Date(form.expires_at).toISOString();const grant=await api('/grants',{method:'POST',body:{...form,receipt_id:id,expected_revision:packet.current_revision}});$('grant-result').textContent=`Ключ показан один раз. Передайте по согласованному защищённому каналу: ${grant.credential}`;$('grant-result').className='grant-secret';await renderGrants(id);}catch(e){message(errorText(e),true);}});
    if(!$('grant-card').hidden)await renderGrants(id);show('detail');
  }
  async function openPlan(id) {
    const data=await api(`/plans/${id}`),plan=data.plan,progress=data.progress;
    const progressLabels={matched:'Количество совпало',partial:'Принято частично',not_accepted:'Не принято',over_accepted:'Принято сверх плана',unexpected_material_or_unit:'Другая строка, материал или единица'};
    $('plan-detail').innerHTML=`<div class="page-heading"><div><p class="eyebrow">ПЛАН / ФАКТ</p><h1>${esc(plan.reference)}</h1><p>${esc(plan.supplier)} · ${esc(planDate(plan))}</p>${statusBadge(plan.status)} ${badge(plan.provenance,plan.provenance==='SIM'?'sim':'')}</div></div><div class="notice">${progress.receipt_count} приёмок · ${progress.pending_receipts} без действующего подтверждения. Суммы рассчитаны по текущим версиям. Совпадение количества не закрывает план автоматически.</div><div class="plan-progress">${progress.lines.map(l=>`<article class="card"><h2>${esc(l.material)} · ${esc(l.unit)}</h2><p class="hint">Строка ${esc(l.line_id)} · ${esc(progressLabels[l.status])}</p><dl class="quantity-grid"><div><dt>По плану</dt><dd>${esc(l.planned_quantity??'—')}</dd></div><div><dt>Прибыло</dt><dd>${esc(l.observed_quantity)}</dd></div><div><dt>Принято</dt><dd>${esc(l.accepted_quantity)}</dd></div><div><dt>Осталось принять</dt><dd>${esc(l.remaining_quantity??'—')}</dd></div></dl></article>`).join('')}</div><div class="card"><h2>Приёмки по этому плану</h2>${data.receipts.map(r=>`<div class="file-row"><span>${esc(dateText(r.observed_at))} · версия ${r.revision} · ${esc(labels[r.evidence_status])}</span><button class="row-button" data-plan-receipt="${r.receipt_id}">Открыть</button></div>`).join('')||'<p class="muted">Прибытия ещё не записаны.</p>'}</div>${state.actor.role==='coordinator'?`<details class="card"><summary>Решение координатора по плану</summary><p class="hint">Проверьте частичные приёмки, споры, файлы и расхождения перед завершением. Закрытие плана не подтверждает отдельные приёмки.</p><form id="plan-status-form" class="form-grid"><label>Статус<select name="status"><option value="completed">Завершён</option><option value="cancelled">Отменён</option></select></label><label>Причина<input name="reason" required minlength="3" maxlength="1000"></label><button class="primary" type="submit">Сохранить решение</button></form></details>`:''}`;
    $('plan-detail').querySelectorAll('[data-plan-receipt]').forEach(b=>b.addEventListener('click',()=>openReceipt(b.dataset.planReceipt).catch(e=>message(errorText(e),true))));
    $('plan-status-form')?.addEventListener('submit',async event=>{event.preventDefault();try{await api(`/plans/${id}/status`,{method:'POST',body:Object.fromEntries(new FormData(event.target))});await refresh();await openPlan(id);message('Решение по плану сохранено. История приёмок не изменена.');}catch(e){message(errorText(e),true);}});
    $('message').hidden=true;show('plan');
  }
  $('coverage-form').addEventListener('submit',async event=>{
    event.preventDefault();$('coverage-result').replaceChildren();
    try {
      const fields=Object.fromEntries(new FormData(event.target));
      fields.start=new Date(fields.start).toISOString();fields.end=new Date(fields.end).toISOString();
      const report=await api('/metrics?'+new URLSearchParams(fields));
      const percent=value=>(value*100).toLocaleString('ru-RU',{maximumFractionDigits:1})+'%';
      $('coverage-result').innerHTML=`<div class="stats"><div class="stat"><span>Независимый журнал</span><strong>${report.eligible_arrivals}</strong><small>всего подходящих прибытий</small></div><div class="stat"><span>Записано в приложении</span><strong>${report.recorded}</strong><small>${percent(report.recorded_coverage)} от журнала</small></div><div class="stat"><span>Полные с подтверждением</span><strong>${report.complete_confirmed}</strong><small>${percent(report.confirmed_coverage)} от журнала</small></div></div><div class="card"><p>Спорных: ${report.disputed}. Без связи с планом: ${report.unmatched}.</p><p>Основание знаменателя: ${esc(report.register_reference)}</p><p class="hint">Расчёт: ${esc(dateText(report.evaluated_at))}. Состояния текущих версий могут измениться после исправлений. SIM исключены. Количество физических прибытий из независимого журнала указывает координатор.</p><p class="hint">Полнота записи не означает выполнение всего плана. Время ввода, исходы споров и решение покупателя фиксируются отдельно.</p><button id="download-coverage" class="secondary">Скачать отчёт JSON</button></div>`;
      $('download-coverage').addEventListener('click',()=>download(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}),'sitepulse-coverage.json'));
    }catch(e){message(errorText(e),true);}
  });
  async function renderGrants(receiptId){const data=await api('/grants');$('grant-list').innerHTML=data.grants.filter(g=>g.receipt_id===receiptId).map(g=>`<div class="file-row"><span>${esc(g.recipient)} · ${g.revoked?'отозван':esc(dateText(g.expires_at))}</span>${g.revoked?'':`<button class="row-button" data-revoke="${g.id}">Отозвать</button>`}</div>`).join('');$('grant-list').querySelectorAll('[data-revoke]').forEach(b=>b.addEventListener('click',async()=>{try{await api(`/grants/${b.dataset.revoke}/revoke`,{method:'POST'});await renderGrants(receiptId);}catch(e){message(errorText(e),true);}}));}
  async function loadDocuments(){if(!state.actor?.features.reconciliation)return;const data=await api('/documents');$('document-list').innerHTML=data.documents.length?data.documents.map(d=>`<div class="queue-row"><div><strong>${esc(d.kind)} ${esc(d.number)}</strong><p>${esc(d.issuer)} · ${esc(d.issued_on)}</p><div id="recon-${d.id}"></div></div><button class="secondary" data-reconcile="${d.id}">Сверить</button></div>`).join(''):'<div class="empty">Документы ещё не добавлены</div>';$('document-list').querySelectorAll('[data-reconcile]').forEach(b=>b.addEventListener('click',async()=>{try{const result=await api(`/documents/${b.dataset.reconcile}/reconciliation`);$(`recon-${b.dataset.reconcile}`).textContent=result.lines.map(l=>`Строка ${l.line_id}: ${l.status} (${l.declared_quantity??'нет'} / ${l.received_quantity??'нет'})`).join('; ')+(result.requires_review?' · Нужна ручная проверка распределения и расхождений':' · Количества совпали; учётное подтверждение отдельно');}catch(e){message(errorText(e),true);}}));}
  async function loadSlots() {
    const [resourceData, slotData] = await Promise.all([api('/resources'), api('/slots')]);
    const resources = new Map(resourceData.resources.map(r => [r.id, r.name]));
    $('slot-resource').innerHTML = resourceData.resources.map(r => `<option value="${esc(r.id)}">${esc(r.name)}</option>`).join('');
    $('slot-plan').innerHTML = '<option value="">Без привязки</option>' + state.plans.map(p => `<option value="${esc(p.id)}">${esc(p.reference)}</option>`).join('');
    const status = {requested:'Запрошено', approved:'Одобрено', rejected:'Отклонено', cancelled:'Отменено'};
    $('slot-list').innerHTML = slotData.slots.length ? slotData.slots.map(s => `<div class="revision-card"><strong>${esc(resources.get(s.resource_id) || s.resource_id)}</strong><p>${esc(dateText(s.start_at))} — ${esc(dateText(s.end_at))} · ${esc(status[s.status])}</p>${state.actor.role==='coordinator' && ['requested','approved'].includes(s.status) ? (s.status==='requested' ? ['approve','reject','move','cancel'] : ['move','cancel']).map(action => `<button class="secondary" data-slot="${s.id}" data-action="${action}" data-version="${s.version}">${{approve:'Одобрить',reject:'Отклонить',move:'Перенести',cancel:'Отменить'}[action]}</button>`).join(' ') : ''}</div>`).join('') : '<div class="empty">Пока нет заявок. Сначала зарегистрируйте физический ресурс.</div>';
    $('slot-list').querySelectorAll('[data-slot]').forEach(button => button.addEventListener('click', async () => {
      const reason = prompt('Причина решения (не менее 3 символов)');
      if (!reason) return;
      const body = {action:button.dataset.action, expected_version:Number(button.dataset.version), reason};
      try {
        if(body.action==='move') {
          const start=prompt('Новое начало в часовом поясе устройства: ГГГГ-ММ-ДДTЧЧ:ММ');if(!start)return;
          const end=prompt('Новый конец в часовом поясе устройства: ГГГГ-ММ-ДДTЧЧ:ММ');if(!end)return;
          body.start_at=new Date(start).toISOString();body.end_at=new Date(end).toISOString();
        }
        await api(`/slots/${button.dataset.slot}/decision`, {method:'POST',body});
        await loadSlots();message('Решение сохранено.');
      } catch(e) {message(errorText(e),true);}
    }));
  }
  $('resource-form').addEventListener('submit',async event=>{
    event.preventDefault();try{await api('/resources',{method:'POST',body:Object.fromEntries(new FormData(event.target))});event.target.reset();await loadSlots();message('Ресурс зарегистрирован.');}catch(e){message(errorText(e),true);}
  });
  $('slot-form').addEventListener('submit',async event=>{
    event.preventDefault();try{const body=Object.fromEntries(new FormData(event.target));body.slot_id=crypto.randomUUID();body.plan_id=body.plan_id||null;body.start_at=new Date(body.start_at).toISOString();body.end_at=new Date(body.end_at).toISOString();await api('/slots',{method:'POST',body});event.target.reset();await loadSlots();message('Заявка отправлена координатору.');}catch(e){message(errorText(e),true);}
  });
  async function loadNotifications() {
    const [data, history]=await Promise.all([api('/notifications'),api('/supplier-history')]);
    const kinds={receipt:'Записано прибытие',receipt_decision:'Решение по приёмке',confirmed:'Приёмка подтверждена',disputed:'Открыт спор',slot_requested:'Запрошено окно',slot_decision:'Решение по окну'};
    $('notification-list').innerHTML=data.notifications.length?data.notifications.map(n=>`<div class="file-row"><span>${esc(kinds[n.payload.kind]||'Обновление')} · ${esc(n.payload.reference||n.payload.status||'')} · ${esc(dateText(n.at))}</span>${n.read?'':`<button class="row-button" data-read="${n.id}">Прочитано</button>`}</div>`).join(''):'<p class="muted">Нет уведомлений.</p>';
    $('notification-list').querySelectorAll('[data-read]').forEach(b=>b.addEventListener('click',async()=>{try{await api(`/notifications/${b.dataset.read}/read`,{method:'POST'});await loadNotifications();}catch(e){message(errorText(e),true);}}));
    $('supplier-history').innerHTML='<h3>История подтверждённых поставок</h3><p class="hint">Только полные REAL-записи этого объекта. Доля прибытий к сроку и 95% интервал; это не кредитный рейтинг.</p>'+ (history.suppliers.length?history.suppliers.map(s=>`<p><strong>${esc(s.supplier)}</strong> · ${s.on_time}/${s.receipts} к сроку · интервал ${Math.round(s.ci_low*100)}–${Math.round(s.ci_high*100)}%</p>`).join(''):'<p class="muted">Недостаточно рабочих данных. SIM не учитывается.</p>');
  }
  $('document-form').addEventListener('submit',async event=>{event.preventDefault();try{await api('/documents',{method:'POST',body:{...Object.fromEntries(new FormData(event.target)),document_id:crypto.randomUUID(),lines:getLines('document-lines')}});await loadDocuments();message('Документ сохранён.');}catch(e){message(errorText(e),true);}});
  $('document-plan').addEventListener('change',()=>{const p=state.plans.find(p=>p.id===$('document-plan').value);if(p){$('document-lines').replaceChildren();p.lines.forEach(l=>addLine('document-lines',l));}});
  function stopCamera(){if(state.stream){state.stream.getTracks().forEach(t=>t.stop());state.stream=null;}$('qr-video').hidden=true;$('stop-qr').hidden=true;}
  $('scan-qr').addEventListener('click',async()=>{try{if(!('BarcodeDetector' in window))throw new Error('QR-сканер недоступен в этом браузере. Введите номер или выберите план вручную.');const detector=new BarcodeDetector({formats:['qr_code']});state.stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'environment'}});const video=$('qr-video');video.srcObject=state.stream;video.hidden=false;$('stop-qr').hidden=false;await video.play();const tick=async()=>{if(!state.stream)return;try{const codes=await detector.detect(video);if(codes.length){const code=codes[0].rawValue;const p=state.plans.find(p=>p.reference===code||p.id===code);if(p){$('capture-plan').value=p.id;fillFromPlan();}else if(code.length<=80){$('capture-plan').value='';$('capture-ref').value=code;}else{message('QR не содержит знакомый номер поставки. Введите номер вручную.',true);}stopCamera();return;}}catch(e){message(errorText(e),true);stopCamera();return;}setTimeout(tick,350);};tick();}catch(e){stopCamera();message(errorText(e),true);}});
  $('stop-qr').addEventListener('click',stopCamera);
  async function exportDrafts(onlyId=null) {
    try {
      const drafts=(await ownDrafts()).filter(d=>!onlyId||d.id===onlyId);
      const estimate=drafts.reduce((sum,d)=>sum+JSON.stringify({...d,files:[]}).length*3+d.files.reduce((n,f)=>n+Math.ceil(draftBlob(f).size/3)*4+1024,0),0);
      if(drafts.length>100||estimate>95*1024*1024)throw new Error('Очередь слишком велика для одного файла. Используйте «Скачать копию» у каждой записи.');
      const records=await Promise.all(drafts.map(async d=>({...d,files:await Promise.all(d.files.map(async f=>({name:f.name,type:f.type,data:await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(reader.error);reader.readAsDataURL(draftBlob(f));})})))})));
      const blob=new Blob([JSON.stringify({format:'sitepulse-drafts-v1',siteId:state.actor.site.id,actorId:state.actor.id,records})],{type:'application/json'});
      if(blob.size>100*1024*1024)throw new Error('Скачайте копии отдельных записей — общий файл больше 100 МБ.');
      download(blob,onlyId?`sitepulse-draft-${onlyId}.json`:'sitepulse-private-drafts.json');
      message('Копия содержит данные и фото. Храните её только в согласованном защищённом месте.');
    }catch(e){message(errorText(e),true);}
  }
  $('export-drafts').addEventListener('click',()=>exportDrafts());
  $('import-drafts').addEventListener('change',async event=>{try{const file=event.target.files[0];if(!file)return;if(file.size>100*1024*1024)throw new Error('Резервная копия больше 100 МБ.');const data=JSON.parse(await file.text());if(!state.actor||data.format!=='sitepulse-drafts-v1'||data.siteId!==state.actor.site.id||data.actorId!==state.actor.id||!Array.isArray(data.records)||data.records.length>100)throw new Error('Копия должна принадлежать вашему текущему профилю и объекту.');for(const d of data.records){if(d.actorId!==state.actor.id||d.siteId!==state.actor.site.id||d.id!==d.body?.operation_id||!d.body?.payload||!Array.isArray(d.files)||d.files.length>6)throw new Error('Неверная структура черновика.');if(await read('drafts',d.id))continue;const files=[];for(const f of d.files){if(!/^data:(image\/(png|jpeg)|application\/pdf);base64,/.test(f.data)||f.data.length>7*1024*1024)throw new Error('Неподдерживаемый файл в копии.');const bytes=Uint8Array.from(atob(f.data.split(',')[1]),c=>c.charCodeAt(0));files.push({name:f.name,type:f.data.slice(5,f.data.indexOf(';')),bytes:bytes.buffer});}await write('drafts',{...d,files,status:'local',uploadedFiles:[],error:null});}await renderQueue();message('Черновики восстановлены. Повторная отправка использует прежние идентификаторы.');}catch(e){message(errorText(e),true);}finally{event.target.value='';}});
  $('sync-all').addEventListener('click',()=>syncAll());$('refresh').addEventListener('click',()=>refresh().catch(e=>message(errorText(e),true)));$('load-more').addEventListener('click',()=>refresh(true).catch(e=>message(errorText(e),true)));
  for(const name of ['plan','capture','document'])$(`add-${name}-line`).addEventListener('click',()=>addLine(`${name}-lines`));
  window.addEventListener('online',connection);window.addEventListener('offline',connection);window.addEventListener('pagehide',stopCamera);
  window.addEventListener('unhandledrejection',event=>{message(errorText(event.reason),true);event.preventDefault();});
  async function init(){bindNavigation();for(const name of ['plan','capture','document'])addLine(`${name}-lines`);$('observed-at').value=localInput();$('coverage-form').elements.start.value=localInput(new Date(Date.now()-30*86400000));$('coverage-form').elements.end.value=localInput();$('today-date').textContent=new Date().toLocaleDateString('ru-RU',{day:'numeric',month:'long'});connection();try{const previous=await read('context','lastActor');if(previous){state.actor=previous.actor;state.plans=(await read('context',`plans:${state.actor.site.id}`))?.plans||[];actorUI();renderPlans();renderReceipts();await renderQueue();show('queue');message('Локальные записи восстановлены. Войдите снова для отправки; без сети можно продолжать фиксировать прибытия.');}}catch(e){message('Локальное хранилище недоступно. '+errorText(e),true);$('capture-form').querySelector('button[type=submit]').disabled=true;}
    try{const response=await fetch('/readyz',{cache:'no-store'});const data=await response.json();state.mode=data.mode==='customer'?'ОБЪЕКТ':'ЛОКАЛЬНЫЙ ПРОТОТИП';connection();}catch{$('mode-badge').textContent='БЕЗ СЕТИ';}
    if('serviceWorker' in navigator)navigator.serviceWorker.register('/receive-sw.js',{scope:'/'}).catch(e=>message('Офлайн-оболочка не установлена. '+errorText(e),true));
  }
  init();
})();
