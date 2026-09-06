(() => {
  'use strict';
  const $ = s => document.querySelector(s);
  const esc = x => String(x ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const STORAGE = 'campusStartV11';
  let config, content, identity = {}, result = null, activeQ = null, draft = null, busy = false;
  let saveChain = Promise.resolve();
  const fresh = () => ({token:'',answers:{},index:0,revision:0,demo:false,started:false,submitted:false});
  let state = fresh();
  try {state = {...state,...JSON.parse(sessionStorage.getItem(STORAGE)||'{}')};} catch (_) {}
  const network = text => {$('#network').textContent=text;};
  function saveLocal(){
    const clone=JSON.parse(JSON.stringify(state));
    if(clone.answers.N27) delete clone.answers.N27.contact;
    try {sessionStorage.setItem(STORAGE,JSON.stringify(clone));} catch (_) {network('浏览器未允许临时存档，请私下保存恢复码。');}
  }
  async function api(path, options={}){
    const headers={'Content-Type':'application/json',...(state.token?{Authorization:'Bearer '+state.token}:{}),...options.headers};
    const response=await fetch(path,{...options,headers,cache:'no-store'});
    let data;try{data=await response.json();}catch(_){throw new Error('服务暂时不可用，请稍后重试。');}
    if(!response.ok){const failure=new Error(typeof data.detail==='string'?data.detail:'请求未通过校验，请核对内容。');failure.status=response.status;throw failure;}
    return data;
  }
  function routePoints(winter=true){
    const values=Object.fromEntries(Object.keys(content.INTERESTS).map(k=>[k,0]));
    ['N00','N04',...(winter?['N18']:[])].forEach(id=>{
      const answer=state.answers[id], q=content.QUESTIONS[id]; if(answer===undefined)return;
      if(q.type==='multi') answer.forEach((id,i)=>{const e=q.options.find(x=>x.id===id)?.effects;if(e?.interest)values[e.interest]+=q.interestWeights[i]||0;});
      else {const e=q.options.find(x=>x.id===answer)?.effects;Object.entries(e?.interests||{}).forEach(([k,v])=>values[k]+=v);}
    });
    const order=[...new Set([...(state.answers.N04||[]),...(state.answers.N00||[]),...Object.keys(content.ROUTE_CODE)])];
    return order.sort((a,b)=>values[b]-values[a])[0];
  }
  function sequence(){
    const first=(state.answers.N04||state.answers.N00||['creative'])[0];
    const a=content.ROUTE_CODE[first]||'C';
    const f=content.ROUTE_CODE[routePoints(false)],s=content.ROUTE_CODE[routePoints(true)];
    return ['N00','N01','N02','N03','N04','N05-'+a,'N06','N07','N08','N09','N10','N11','N12','N13','N14-'+f,'N15','N16','N17','N18','N19',s+'01',s+'02',s+'03','N20','N21','N22','N23','N24','N25','N26','N27','N28'];
  }
  function queueSave(){
    if(state.demo||!state.token||state.submitted)return;
    const snapshot={answers:JSON.parse(JSON.stringify(state.answers)),revision:state.revision};
    network('正在保存进度…');
    saveChain=saveChain.catch(()=>{}).then(async()=>{
      try{await api('/api/sessions/me/progress',{method:'PUT',body:JSON.stringify(snapshot)});if(snapshot.revision===state.revision)network('进度已同步。');}
      catch(e){if(!state.submitted)network('暂未同步：'+e.message+' 本页可继续，联网后会补交。');}
    });
  }
  function commit(id,value){
    const keep=sequence().slice(0,state.index);
    state.answers=Object.fromEntries(keep.filter(k=>state.answers[k]!==undefined).map(k=>[k,state.answers[k]]));
    state.answers[id]=value;state.index++;state.revision++;activeQ=null;
    saveLocal();queueSave();render();window.scrollTo({top:0,behavior:'smooth'});
  }
  function showError(message){const el=$('#error');if(el)el.textContent=message;else network(message);}
  function recovery(){
    if(!state.token)return;
    const modal=document.createElement('div');modal.className='modal';
    modal.innerHTML=`<section class="card"><h2>这是你的恢复码</h2><p>只发给自己，不要发到群里。拿到它的人可以查看或删除你的记录。</p><p class="mono">${esc(state.token)}</p><div class="actions"><button class="btn primary" id="copyToken">复制恢复码</button><button class="btn" id="closeModal">关闭</button></div></section>`;
    document.body.appendChild(modal);
    $('#copyToken').onclick=()=>copyText(state.token,$('#copyToken'));
    $('#closeModal').onclick=()=>modal.remove();
  }
  async function copyText(text,button){
    try{await navigator.clipboard.writeText(text);button.textContent='已复制';}
    catch(_){button.textContent='请长按上方文字复制';}
  }
  function landing(){
    $('#stage').textContent='新生专属 · 第一学年';
    $('#app').innerHTML=`<section class="card hero"><span class="eyebrow">CAMPUS MODE / ${esc(config.cohort)}</span><h1>大一，<br>启动！</h1><span class="sticker">你的大学，没有统一攻略。</span><p>进宿舍、选方向、赶 DDL、组队翻车。<br>把一整个大一，提前玩一遍。</p><div class="stats"><div class="stat"><strong>5</strong><span>探索路线</span></div><div class="stat"><strong>32</strong><span>本局剧情节点</span></div><div class="stat"><strong>12</strong><span>可能的主结局</span></div></div><small>建议预留约 10–15 分钟；作品任务可跳过。实际用时待现场试测。</small></section>
    <section class="card"><span class="eyebrow">先领一张入场券</span><h2>登记一下，准备开局。</h2><p class="muted">正式参与需填写姓名与学号，用于活动登记和区分记录。后续是否接受邀请，最后由你单独选择。</p><form id="joinForm"><div class="grid2"><div><label class="label" for="name">姓名</label><input id="name" autocomplete="name" maxlength="40" required placeholder="填写真实姓名"></div><div><label class="label" for="studentId">学号</label><input id="studentId" inputmode="numeric" autocomplete="off" maxlength="32" required placeholder="完整学号，不省略开头的 0"></div></div>${config.enrollment_required?'<label class="label" for="enrollment">参与口令</label><input id="enrollment" autocomplete="off" maxlength="200" required placeholder="活动负责人提供的口令">':''}<div class="notice">数据负责人：${esc(config.operator)}<br>姓名、学号、作答及作品保存于活动服务端；完成记录最多保存 ${config.retention_days} 天，未完成记录最多保存 ${config.draft_days} 天。姓名与学号不参与任何评分，也不出现在分享内容中。</div><label class="check"><input type="checkbox" id="consent" required><span>我已阅读<a href="/privacy" target="_blank" rel="noopener">数据使用与撤回说明</a>，同意本次活动登记及保存上述信息。我知道这是校园互动游戏，不是心理诊断或录取测试。</span></label><p class="error" id="error" role="alert"></p><button class="btn primary" id="joinBtn" type="submit">登记并开启第一学年 →</button></form><details><summary>之前已经登记？使用恢复码继续</summary><label class="label" for="resumeCode">恢复码（不要填写学号或管理员口令）</label><input id="resumeCode" type="password" autocomplete="off" maxlength="100"><div class="actions"><button class="btn" id="resumeBtn">恢复我的进度</button></div><p class="muted">没有恢复码时，请联系 ${esc(config.privacy_contact)} 核验处理。只填姓名、学号不能冒领已有记录。</p></details>${config.demo_enabled?'<details><summary>开发测试入口</summary><p class="muted">不登记身份、不保存作答记录。仅供在 staging 检查剧情。</p><button class="btn" id="demoBtn">匿名试玩（测试环境）</button></details>':''}</section>`;
    $('#joinForm').onsubmit=async e=>{
      e.preventDefault();if(busy)return;busy=true;$('#joinBtn').disabled=true;showError('');
      try{
        const payload={name:$('#name').value.trim(),student_id:$('#studentId').value.trim(),consent_core:$('#consent').checked,privacy_version:config.privacy_version,enrollment_code:$('#enrollment')?.value||''};
        const registered=await api('/api/sessions',{method:'POST',body:JSON.stringify(payload)});
        state={...fresh(),token:registered.access_token,started:true};identity={name:payload.name,student_id:payload.student_id};result=null;saveLocal();render();recovery();
      }catch(err){showError(err.message);}finally{busy=false;if($('#joinBtn'))$('#joinBtn').disabled=false;}
    };
    $('#resumeBtn').onclick=async()=>{
      const token=$('#resumeCode').value.trim();if(!token)return showError('请输入恢复码');
      const original=state;state={...fresh(),token};
      try{await restore(true);render();}catch(e){state=original;showError(e.message);}
    };
    if($('#demoBtn'))$('#demoBtn').onclick=()=>{state={...fresh(),demo:true,started:true};identity={};result=null;saveLocal();render();};
  }
  function render(){
    if(!state.started)return landing();
    if(result)return renderResult();
    const path=sequence();
    if(state.index>=path.length)return settle();
    const q=content.QUESTIONS[path[state.index]];
    if(activeQ!==q.id){activeQ=q.id;draft=JSON.parse(JSON.stringify(state.answers[q.id]??(q.type==='multi'||q.type==='allocation'?[]:q.type==='worksample'?{task:'skip'}:q.type==='contact'?{choice:'',contact:''}:'')));}
    paintQuestion(q);
  }
  function isReady(q){
    if(q.type==='single')return !!draft;
    if(q.type==='multi')return Array.isArray(draft)&&draft.length===q.limit;
    if(q.type==='allocation')return Array.isArray(draft)&&draft.length>0;
    if(q.type==='mbti')return true;
    if(q.type==='contact')return !!draft.choice;
    if(q.type==='worksample'){
      if(draft.task==='skip')return true;
      if(draft.task==='writing')return Array.from((draft.text||'').trim()).length>=1&&Array.from(draft.text||'').length<=80;
      if(draft.task==='clips')return draft.order?.length===4;
      if(draft.task==='photos')return draft.selected?.length===3&&draft.selected.every(i=>(draft.reasons?.[String(i)]||'').trim());
    }
    return false;
  }
  function paintQuestion(q){
    $('#stage').textContent=q.chapter;
    let body='';
    if(['single','multi','allocation','contact'].includes(q.type)){
      if(q.type==='multi')body+=`<div class="notice">选择 ${q.limit} 项，先点的是第一偏好。再次点击可取消。</div>`;
      if(q.type==='allocation'){
        const used=draft.reduce((sum,key)=>sum+q.costs[key],0);
        body+=`<div class="notice ${used>10?'warning':''}">本周行动力：<strong>${used} / 10</strong>${used>10?' · 超支会触发剧情提醒，不作为人格扣分。':''}</div>`;
      }
      body+='<div class="options">'+q.options.map((o,i)=>{
        const selected=Array.isArray(draft)?draft.includes(o.id):q.type==='contact'?draft.choice===o.id:draft===o.id;
        const label=Array.isArray(draft)&&selected?String(draft.indexOf(o.id)+1):String.fromCharCode(65+i);
        return `<button type="button" class="option ${selected?'selected':''}" data-choice="${esc(o.id)}" aria-pressed="${selected}"><span class="key">${label}</span><span class="option-text">${esc(o.text)}${o.sub?`<small>${esc(o.sub)}</small>`:''}</span></button>`;
      }).join('')+'</div>';
      if(q.type==='contact'&&draft.choice&&draft.choice!=='none')body+=`<div class="notice">这次选择表示愿意接收对应活动邀请。姓名与学号已经登记，不必重填。联系方式可以留空，由负责人按活动既有渠道联系。</div><label class="label" for="contact">微信号或手机号（自愿，不参与评分）</label><input id="contact" maxlength="100" autocomplete="off" value="${esc(draft.contact||'')}" placeholder="留空也可以继续">`;
    }else if(q.type==='mbti'){
      body=`<label class="label" for="mbti">仅作娱乐展示</label><select id="mbti"><option value="">不知道 / 不想填</option>${content.MBTIS.map(x=>`<option ${draft===x?'selected':''}>${x}</option>`).join('')}</select><div class="notice">跳过不影响结局、策略数值或体验方向推荐。</div>`;
    }else if(q.type==='worksample')body=workBody();
    $('#app').innerHTML=`<div class="progress"><div class="progress-label"><span>${state.demo?'匿名测试':'正式参与'} · ${state.index+1} / 32</span><span>${esc(q.chapter)}</span></div><div class="track"><div class="fill" style="width:${state.index/32*100}%"></div></div></div><section class="card"><span class="eyebrow">${esc(q.id)}</span><h2>${esc(q.title)}</h2><div class="scene">${esc(q.scene)}</div><p class="prompt">${esc(q.prompt)}</p>${body}<p id="error" class="error" role="alert"></p><div class="actions">${state.index>0?'<button class="btn" id="backBtn">← 上一步</button>':''}<button class="btn primary" id="nextBtn" ${isReady(q)?'':'disabled'}>${state.index===31?'结算我的大一':'继续 →'}</button></div>${state.token?'<details><summary>进度与隐私操作</summary><div class="actions"><button class="btn small" id="recoveryBtn">保存恢复码</button><button class="btn small danger" id="withdrawBtn">撤回并删除我的记录</button></div></details>':''}</section>`;
    document.querySelectorAll('[data-choice]').forEach(b=>b.onclick=()=>{
      const id=b.dataset.choice;
      if(Array.isArray(draft)){if(draft.includes(id))draft=draft.filter(x=>x!==id);else if(q.type==='allocation'||draft.length<q.limit)draft.push(id);}
      else if(q.type==='contact')draft={choice:id,contact:id==='none'?'':draft.contact||''};
      else draft=id;
      paintQuestion(q);
    });
    if($('#contact'))$('#contact').oninput=e=>{draft.contact=e.target.value;};
    if($('#mbti'))$('#mbti').onchange=e=>{draft=e.target.value;};
    if(q.type==='worksample')wireWork(q);
    $('#nextBtn').onclick=()=>{if(isReady(q))commit(q.id,JSON.parse(JSON.stringify(draft)));};
    if($('#backBtn'))$('#backBtn').onclick=()=>{state.index--;activeQ=null;saveLocal();render();window.scrollTo({top:0});};
    if($('#recoveryBtn'))$('#recoveryBtn').onclick=recovery;
    if($('#withdrawBtn'))$('#withdrawBtn').onclick=withdraw;
  }
  const clips=['迎新签到','操场','教学楼','食堂','实验室','海边'];
  function workBody(){
    let s=`<div class="tabs">${[['skip','这次跳过'],['writing','80字开场'],['clips','20秒剪辑方案'],...(config.photo_enabled?[['photos','照片选择']]:[])].map(([id,label])=>`<button class="btn small ${draft.task===id?'active':''}" data-task="${id}">${label}</button>`).join('')}</div>`;
    if(draft.task==='skip')return s+'<div class="notice">跳过不会扣分。作品由工作人员按公开标准人工评阅，不自动判断审美或能力。</div>';
    if(draft.task==='writing')return s+`<label class="label" for="workText">为“新生来到海洋学院的第一天”写一个视频开头。</label><textarea id="workText" placeholder="可以从一句对白、一个镜头或一个意外开始…">${esc(draft.text||'')}</textarea><div class="counter" id="wordCount">${Array.from(draft.text||'').length} / 80 字</div><p class="muted">评阅：吸引力、结构、受众意识、可执行性；每项0–4分。</p>`;
    if(draft.task==='clips')return s+`<div class="notice">从6类素材中挑4个，按顺序排成20秒短片方案。每段暂按5秒展示；本题评估结构提案，不等于真实剪辑技能。</div><div class="tabs">${clips.map((x,i)=>`<button class="btn small ${(draft.order||[]).includes(i)?'active':''}" data-clip="${i}">${esc(x)}</button>`).join('')}</div>${(draft.order||[]).map((x,i)=>`<div class="order-row"><b>${i*5}–${i*5+5}s</b><span>${esc(clips[x])}</span><button class="btn small" data-up="${i}" ${i===0?'disabled':''} aria-label="上移${esc(clips[x])}">↑</button><button class="btn small" data-remove="${i}" aria-label="移除${esc(clips[x])}">×</button></div>`).join('')}<label class="label" for="clipNote">你的节奏想法（自愿，120字以内）</label><textarea id="clipNote" maxlength="120">${esc(draft.note||'')}</textarea>`;
    return s+`<div class="photo-grid">${Array.from({length:8},(_,i)=>`<button class="option ${(draft.selected||[]).includes(i)?'selected':''}" data-photo="${i}"><img src="/static/assets/photos/${i}.jpg" alt="任务照片${i+1}"><span>照片 ${i+1}</span></button>`).join('')}</div>${(draft.selected||[]).map(i=>`<label class="label" for="reason${i}">照片 ${i+1}：留下它的理由</label><input id="reason${i}" data-reason="${i}" maxlength="80" value="${esc(draft.reasons?.[String(i)]||'')}">`).join('')}`;
  }
  function wireWork(q){
    document.querySelectorAll('[data-task]').forEach(b=>b.onclick=()=>{draft={task:b.dataset.task};paintQuestion(q);});
    if($('#workText'))$('#workText').oninput=e=>{draft.text=e.target.value;$('#wordCount').textContent=Array.from(draft.text).length+' / 80 字';$('#nextBtn').disabled=!isReady(q);};
    document.querySelectorAll('[data-clip]').forEach(b=>b.onclick=()=>{const n=Number(b.dataset.clip);draft.order=draft.order||[];if(draft.order.includes(n))draft.order=draft.order.filter(x=>x!==n);else if(draft.order.length<4)draft.order.push(n);paintQuestion(q);});
    document.querySelectorAll('[data-up]').forEach(b=>b.onclick=()=>{const i=Number(b.dataset.up);[draft.order[i-1],draft.order[i]]=[draft.order[i],draft.order[i-1]];paintQuestion(q);});
    document.querySelectorAll('[data-remove]').forEach(b=>b.onclick=()=>{draft.order.splice(Number(b.dataset.remove),1);paintQuestion(q);});
    if($('#clipNote'))$('#clipNote').oninput=e=>{draft.note=e.target.value;};
    document.querySelectorAll('[data-photo]').forEach(b=>b.onclick=()=>{const i=Number(b.dataset.photo);draft.selected=draft.selected||[];draft.selected=draft.selected.includes(i)?draft.selected.filter(x=>x!==i):draft.selected.length<3?[...draft.selected,i]:draft.selected;paintQuestion(q);});
    document.querySelectorAll('[data-reason]').forEach(b=>b.oninput=e=>{draft.reasons=draft.reasons||{};draft.reasons[b.dataset.reason]=e.target.value;$('#nextBtn').disabled=!isReady(q);});
  }
  async function settle(){
    if(busy)return;busy=true;
    $('#app').innerHTML='<section class="card center"><span class="eyebrow">学年结算</span><h2>正在生成你的结局…</h2><p>结果由服务器按本局原始选择计算。</p><p class="error" id="error"></p><div class="actions"><button class="btn" id="retryBtn" hidden>重新提交</button><button class="btn" id="goBack">返回最后一题</button></div></section>';
    $('#goBack').onclick=()=>{state.index=31;activeQ=null;busy=false;render();};
    try{
      await saveChain.catch(()=>{});
      const data=await api(state.demo?'/api/preview':'/api/sessions/me/submit',{method:'POST',body:JSON.stringify({answers:state.answers})});
      result=data.result;state.submitted=!state.demo;state.receipt=data.receipt||'';saveLocal();renderResult();network(state.demo?'测试结果未入库。':'结果已保存，请保存恢复码。');
    }catch(e){showError('尚未提交成功：'+e.message+' 你的进度仍保留在当前浏览器。');$('#retryBtn').hidden=false;$('#retryBtn').onclick=settle;}
    finally{busy=false;}
  }
  function barRows(values,labels={}){return Object.entries(values).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`<div class="bar"><span>${esc(labels[k]||k)}</span><div class="track"><div class="fill" style="width:${Number(v)}%"></div></div><b>${Number(v)}</b></div>`).join('');}
  function renderResult(){
    $('#stage').textContent='第一学年 · 通关';
    const r=result;
    const share=`我的《大一，启动！》结局：${r.ending}\n${r.endingCopy}\n${r.badges.join(' / ')}\n海洋学院新生模拟器，不是人格诊断。`;
    $('#app').innerHTML=`<section class="card hero"><span class="eyebrow">FIRST YEAR / CLEARED</span><div class="result-title">${esc(r.ending)}</div><p>${esc(r.endingCopy)}</p><small>${esc(r.endingBasis||'')}</small>${r.secondary?`<span class="tag">副标签 · ${esc(r.secondary)}</span>`:''}<div>${r.badges.map(x=>`<span class="tag">${esc(x)}</span>`).join('')}</div><small>${state.demo?'匿名试玩 · 未登记':`已提交 · 回执 ${esc(state.receipt)}`}</small></section><section class="card"><h2>你接下来想去哪？</h2><div class="bars">${barRows(r.interests,content.INTERESTS)}</div><h3>学生会新媒体部体验方向线索</h3><div class="bars">${barRows(r.roleFits)}</div><div class="notice">这些是本局选择产生的游戏参考分，不是能力百分位或录取线。你可以主动选择任何开放体验，不会因某项数值低而被自动淘汰。</div><p>可投入时间：${esc(r.availability)}<br>作品状态：${esc(r.sampleStatus)}</p><details><summary>查看15项本局策略指示</summary><p class="muted">没有选某种策略，不代表你缺乏那项能力；不同路线的观察机会也不同。</p><div class="metric-grid">${Object.keys(content.DIMS).map(d=>`<div class="metric"><b>${esc(content.DIMS[d])}</b><strong>${r.scores[d]}</strong><small>相关场景呈现 ${r.evidenceCounts[d]} 次</small></div>`).join('')}</div></details><h3>分享结局，不分享身份</h3><textarea id="shareText" readonly>${esc(share)}</textarea><div class="actions"><button class="btn primary" id="copyShare">复制分享文案</button>${state.token?'<button class="btn" id="recoveryBtn">保存恢复码</button>':''}</div>${state.token?'<details><summary>结束体验与数据操作</summary><p>“清除本机凭证”只退出这台设备，不会删除服务器记录；要继续请使用恢复码。</p><div class="actions"><button class="btn" id="leaveBtn">清除本机凭证</button><button class="btn danger" id="withdrawBtn">撤回并删除记录</button></div></details>':'<div class="actions"><button class="btn" id="leaveBtn">结束测试</button></div>'}</section>`;
    $('#copyShare').onclick=()=>copyText(share,$('#copyShare'));
    if($('#recoveryBtn'))$('#recoveryBtn').onclick=recovery;
    if($('#withdrawBtn'))$('#withdrawBtn').onclick=withdraw;
    $('#leaveBtn').onclick=()=>{if(confirm('确认结束本机体验？请先保存恢复码。')){sessionStorage.removeItem(STORAGE);state=fresh();result=null;identity={};render();}};
  }
  async function withdraw(){
    if(!confirm('确认撤回并删除活动数据库中的姓名、学号、答案及结果？该操作不可撤销。'))return;
    try{await saveChain.catch(()=>{});await api('/api/sessions/me',{method:'DELETE'});state=fresh();result=null;identity={};sessionStorage.removeItem(STORAGE);render();network('活动库记录已删除。已导出资料或备份的处理请联系数据负责人。');}
    catch(e){showError(e.message);}
  }
  async function restore(forceServer=false){
    const data=await api('/api/sessions/me');identity=data.identity||{};
    state.started=true;
    if(forceServer||data.revision>state.revision||data.status==='submitted'){
      state.answers=data.answers;state.revision=data.revision;state.index=Object.keys(data.answers).length;
    }
    if(data.status==='submitted'){state.submitted=true;state.receipt=data.receipt;result=data.result;}
    saveLocal();
  }
  async function init(){
    try{
      [config,content]=await Promise.all([api('/api/config'),api('/api/content')]);
      const filing=$('#filing');
      if(config.icp_number){const a=document.createElement('a');a.href='https://beian.miit.gov.cn/';a.target='_blank';a.rel='noopener';a.textContent=config.icp_number;filing.append(a);}
      if(config.police_number&&config.police_url?.startsWith('https://beian.mps.gov.cn/')){const a=document.createElement('a');a.href=config.police_url;a.target='_blank';a.rel='noopener';a.textContent=config.police_number;filing.append(a);}
      if(state.token){try{await restore();}catch(e){if(e.status===401){state=fresh();saveLocal();}network('原记录未能恢复：'+e.message);}}
      if(state.demo&&!config.demo_enabled)state=fresh();
      render();
    }catch(e){$('#app').innerHTML=`<section class="card"><h1>暂时没连上服务器</h1><p class="error">${esc(e.message)}</p><p>请检查网络，或稍后刷新。不要把“登记成功”误当成“已完成提交”。</p><button class="btn primary" id="reloadBtn">重试连接</button></section>`;$('#reloadBtn').onclick=()=>location.reload();}
  }
  window.addEventListener('online',()=>{network('网络已恢复，正在补存进度。');queueSave();});
  window.addEventListener('offline',()=>network('网络暂时断开。本页可继续选择；请保持页面，联网后补交。'));
  init();
})();