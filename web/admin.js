(() => {
'use strict';
const $=s=>document.querySelector(s), esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let csrf='',page=1,search='',status='',content=null;
async function api(url,options={}){
 const r=await fetch(url,{...options,credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf,...options.headers}});
 const d=await r.json();if(!r.ok){const e=new Error(typeof d.detail==='string'?d.detail:'请求未通过校验');e.status=r.status;throw e;}return d;
}
const error=e=>{const box=$('#error');if(box)box.textContent=e.message||e;};
function login(){
 $('#adminApp').innerHTML='<section class="card" style="max-width:560px;margin:40px auto"><span class="eyebrow">STAFF ONLY</span><h2>登录活动管理</h2><p class="muted">请使用部署时生成的独立管理员口令。这里不接收学生学号或恢复码。</p><form id="loginForm"><label class="label" for="username">管理员账号</label><input id="username" autocomplete="username" required><label class="label" for="password">口令</label><input id="password" type="password" autocomplete="current-password" required><p class="error" id="error"></p><button class="btn primary" id="loginBtn">登录</button></form></section>';
 $('#loginForm').onsubmit=async e=>{e.preventDefault();$('#loginBtn').disabled=true;try{const d=await api('/api/admin/login',{method:'POST',body:JSON.stringify({username:$('#username').value,password:$('#password').value})});csrf=d.csrf_token;await listing();}catch(e){error(e);if($('#loginBtn'))$('#loginBtn').disabled=false;}};
}
const consentLabels={CREATIVE_CONTACT:'学生会新媒体部邀请',RESEARCH_CONTACT:'科研邀请',ORG_CONTACT:'学生工作邀请',OPEN_ACTIVITY:'开放活动',NO_CONTACT:'不联系'};
async function listing(){
 try{
 const d=await api(`/api/admin/participants?page=${page}&limit=30&student_id=${encodeURIComponent(search)}&status=${encodeURIComponent(status)}`);
 $('#adminApp').innerHTML=`<section class="card"><div class="toolbar"><h2 style="flex:1;margin:0">参与记录</h2><a class="btn" href="/api/admin/export.csv">导出 CSV</a><button class="btn" id="auditBtn">操作审计</button><button class="btn" id="logoutBtn">退出</button></div><div class="notice">本届：已提交 ${d.stats.submitted||0} 人 · 未完成 ${d.stats.draft||0} 人。登记信息是否真实需要人工或获授权名册核对；字段匹配不等于本人身份认证。</div><form class="toolbar" id="searchForm"><input id="searchId" placeholder="完整学号精确查找" aria-label="按学号查找" value="${esc(search)}"><select id="status" aria-label="完成状态"><option value="">全部状态</option><option value="draft" ${status==='draft'?'selected':''}>未完成</option><option value="submitted" ${status==='submitted'?'selected':''}>已提交</option></select><button class="btn primary">查询</button><button class="btn" type="button" id="clearBtn">重置</button></form><p class="error" id="error"></p><div class="table-wrap"><table><thead><tr><th>姓名</th><th>学号</th><th>状态 / 进度</th><th>主结局</th><th>邀请意愿</th><th>作品评阅</th><th>详情</th></tr></thead><tbody>${d.items.map(r=>`<tr><td>${esc(r.name)}</td><td class="mono">${esc(r.student_id)}</td><td>${r.status==='submitted'?'已提交':'未完成'} / ${r.progress}</td><td>${esc(r.ending||'—')}</td><td>${esc(consentLabels[r.consent]||'未到此步骤')}</td><td>${r.review?esc(r.review.role+' '+r.review.score):'—'}</td><td><button class="btn small" data-record="${esc(r.id)}">查看</button></td></tr>`).join('')||'<tr><td colspan="7">暂无记录</td></tr>'}</tbody></table></div><div class="actions"><button class="btn" id="prevBtn" ${page<=1?'disabled':''}>上一页</button><span>第 ${page} 页 / 共 ${d.total} 条</span><button class="btn" id="nextPageBtn" ${page*30>=d.total?'disabled':''}>下一页</button></div></section>`;
 $('#searchForm').onsubmit=e=>{e.preventDefault();search=$('#searchId').value.trim();status=$('#status').value;page=1;listing();};
 $('#clearBtn').onclick=()=>{search='';status='';page=1;listing();};
 $('#prevBtn').onclick=()=>{page--;listing();};$('#nextPageBtn').onclick=()=>{page++;listing();};
 document.querySelectorAll('[data-record]').forEach(b=>b.onclick=()=>detail(b.dataset.record));
 $('#logoutBtn').onclick=async()=>{await api('/api/admin/logout',{method:'POST'});csrf='';login();};
 $('#auditBtn').onclick=audit;
 }catch(e){if(e.status===401)login();else error(e);}
}
function answerLabel(q,a){
 if(!q)return JSON.stringify(a);
 if(q.type==='single')return q.options.find(o=>o.id===a)?.text||a;
 if(['multi','allocation'].includes(q.type))return a.map(x=>q.options.find(o=>o.id===x)?.text||x).join(' → ');
 if(q.type==='contact')return (q.options.find(o=>o.id===a.choice)?.text||'')+(a.contact?' / '+a.contact:'');
 if(q.type==='mbti')return a||'跳过';
 return JSON.stringify(a,null,2);
}
async function detail(id){
 try{
 const d=await api('/api/admin/participants/'+id);
 if(!content)content=await api('/api/content');
 const r=d.result||{},w=r.workSample;
 const labels={writing:['吸引注意','叙事结构','受众意识','可执行性'],clips:['顺序结构','节奏设计','信息取舍','可执行性'],photos:['视觉判断','理由清晰','细节观察','表达完整']};
 const roles={writing:['编导策划','运营联络'],clips:['剪辑后期'],photos:['摄影摄像']};
 const rubric=w?labels[w.task]:null;
 const form=rubric?`<h3>作品人工评阅</h3><pre class="mono notice">${esc(JSON.stringify(w,null,2))}</pre><p class="muted">0 无有效证据；1 初步尝试；2 基本可用；3 清楚完整；4 表现突出。不能用文字提案证明实际摄影或软件操作能力。</p><form id="reviewForm"><label class="label" for="role">本次评阅覆盖岗位</label><select id="role">${roles[w.task].map(x=>`<option>${esc(x)}</option>`).join('')}</select><div class="grid2">${rubric.map((label,i)=>`<div><label class="label" for="score${i}">${esc(label)}</label><select id="score${i}" required><option value="">请选择</option>${[0,1,2,3,4].map(x=>`<option value="${x}" ${d.review?.scores?.[i]===x?'selected':''}>${x}</option>`).join('')}</select></div>`).join('')}</div><label class="label" for="note">评阅说明 / 可观察证据</label><textarea id="note" maxlength="1000">${esc(d.review?.note||'')}</textarea><div class="actions"><button class="btn primary">保存人工评阅</button></div></form>`:'<p class="notice">尚无可评阅作品。缺失作品不能直接记零分，也不自动降低学生资格。</p>';
 $('#adminApp').innerHTML=`<section class="card"><button class="btn small" id="backList">← 返回记录</button><h2>${esc(d.name)} <small class="mono">${esc(d.student_id)}</small></h2><p>记录状态：${esc(d.status)} / ${d.progress} 个节点<br>身份信息：${esc(d.identity_verification)}<br>邀请意愿：${esc(consentLabels[d.consent]||d.consent)}<br>联系方式：${esc(d.contact||'未提供')}<br>回执：${esc(d.receipt||'未提交')}<br>说明版本：${esc(d.privacy_version)}</p><div class="notice warning">姓名和学号仅用于登记，不计入任何分数。标记“不联系”的学生不得进入招募联络名单。</div><h3>本局结果：${esc(r.ending||'尚未结算')}</h3><p>${esc(r.endingCopy||'')}</p>${d.review?`<p class="notice">已评阅：${esc(d.review.role)}；作品得分 ${d.review.score}；该岗位评阅后参考分 ${d.review.reviewed_fit}。仅这一岗位计入本作品一次。</p>`:''}${form}<p class="error" id="error"></p><details><summary>原始作答（${d.progress}）</summary><div class="table-wrap"><table><thead><tr><th>节点</th><th>问题</th><th>选择 / 作品</th></tr></thead><tbody>${Object.entries(d.answers).map(([key,value])=>`<tr><td>${esc(key)}</td><td class="wrap">${esc(content.QUESTIONS[key]?.title||key)}</td><td class="wrap">${esc(answerLabel(content.QUESTIONS[key],value))}</td></tr>`).join('')}</tbody></table></div></details><details><summary>完整计算结果与判定门快照</summary><pre class="mono notice">${esc(JSON.stringify(r,null,2))}</pre></details><details><summary>记录恢复与删除</summary><p>补发恢复码前应人工核验本人。补发不清除进度，但旧恢复码立即失效。</p><div class="actions"><button class="btn" id="rotateBtn">补发恢复码</button><button class="btn danger" id="deleteBtn">删除本条全部记录</button></div><p class="mono" id="newCode"></p></details></section>`;
 $('#backList').onclick=listing;
 if($('#reviewForm'))$('#reviewForm').onsubmit=async e=>{e.preventDefault();try{await api(`/api/admin/participants/${id}/review`,{method:'POST',body:JSON.stringify({role:$('#role').value,scores:[0,1,2,3].map(i=>Number($('#score'+i).value)),note:$('#note').value})});await detail(id);}catch(e){error(e);}};
 $('#rotateBtn').onclick=async()=>{if(!confirm('已人工核验本人？确认使旧恢复码失效并补发新码。'))return;try{const x=await api(`/api/admin/participants/${id}/rotate-access`,{method:'POST'});$('#newCode').textContent='仅私下交给本人：'+x.access_token;}catch(e){error(e);}};
 $('#deleteBtn').onclick=async()=>{if(!confirm(`确认删除 ${d.name}（${d.student_id}）的身份、答案、结果和评阅？不可撤销。`))return;try{await api('/api/admin/participants/'+id,{method:'DELETE'});listing();}catch(e){error(e);}};
 }catch(e){error(e);}
}
async function audit(){try{const d=await api('/api/admin/audit');$('#adminApp').innerHTML=`<section class="card"><button class="btn" id="backList">返回</button><h2>最近200次审计事件</h2><p class="muted">审计不记录姓名、学号、口令或完整答案。导出和删除需负责人承担相应管理责任。</p><pre class="mono notice">${esc(JSON.stringify(d.items,null,2))}</pre></section>`;$('#backList').onclick=listing;}catch(e){error(e);}}
(async()=>{try{const d=await api('/api/admin/me');csrf=d.csrf_token;listing();}catch(_){login();}})();
})();