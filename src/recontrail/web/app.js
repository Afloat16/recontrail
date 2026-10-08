/* Original local-workbench client. Credentials stay out of URL queries and logs. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const params = new URLSearchParams(location.hash.slice(1));
  let token = params.get('token') || sessionStorage.getItem('recontrail-token') || '';
  if (params.has('token')) {sessionStorage.setItem('recontrail-token', token);history.replaceState(null,'',location.pathname);}
  let files = [], job = null, busy = false, timer = null;
  const urls = [];
  const showError = message => {$('error').textContent=message;$('error').classList.remove('hidden');};
  function controls(){ $('start').disabled=busy || files.length<2 || !token;$('files').disabled=busy;$('cancel').disabled=!busy || !job; }
  async function api(path, method='GET', body=null, raw=false) {
    const headers = {'X-ReconTrail-Token': token};
    if(body!==null && !raw) headers['Content-Type']='application/json';
    const response = await fetch(path,{method,headers,body:body===null?null:raw?body:JSON.stringify(body),cache:'no-store'});
    if(!response.ok){let detail;try{detail=await response.json();}catch{detail={error:`HTTP ${response.status}`};}throw new Error(detail.error || 'Request failed');}
    return response;
  }
  function select(list){if(busy)return;files=Array.from(list).sort((a,b)=>a.name.localeCompare(b.name,undefined,{numeric:true}));
    const bytes=files.reduce((sum,f)=>sum+f.size,0);
    $('selection').textContent=`${files.length} 张照片 · ${(bytes/1024/1024).toFixed(1)} MiB · 不修改原图`;
    $('error').classList.add('hidden');
    if(files.length>160 || bytes>256*1024*1024 || files.some(f=>f.size>32*1024*1024)){showError('超过上传限额，请减少照片或缩小文件。');files=[];}
    controls();}
  $('files').addEventListener('change',e=>select(e.target.files));
  $('drop').addEventListener('click',()=>{if(!busy)$('files').click();});
  $('drop').addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();$('drop').click();}});
  $('drop').addEventListener('dragover',e=>{e.preventDefault();$('drop').classList.add('drag');});
  $('drop').addEventListener('dragleave',()=>$('drop').classList.remove('drag'));
  $('drop').addEventListener('drop',e=>{e.preventDefault();$('drop').classList.remove('drag');select(e.dataTransfer.files);});
  function artifact(name,label){const b=document.createElement('button');b.className='secondary';b.textContent=label;
    b.addEventListener('click',async()=>{b.disabled=true;try{const response=await api(`/api/jobs/${job}/files/${name}`);const blob=await response.blob();
      const url=URL.createObjectURL(blob);urls.push(url);const a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();
    }catch(error){showError(error.message);}finally{b.disabled=false;}});$('downloads').append(b);}
  function results(data){$('result').classList.remove('hidden');$('metrics').replaceChildren();$('downloads').replaceChildren();
    const m=data.metrics || {};
    for(const [label,value] of [['相机注册',`${m.registered_images??0}/${m.input_images??0}`],['稀疏点',m.points??0]]){
      const c=document.createElement('div');c.className='card';const l=document.createElement('div');l.className='label';l.textContent=label;const v=document.createElement('div');v.className='value';v.textContent=value;c.append(l,v);$('metrics').append(c);}
    if(data.report_available)artifact('report.html','保存离线报告');
    if(data.state==='complete'){if(m.points>0)artifact('cloud.ply','导出 PLY');artifact('audit.json','输入诊断 JSON');artifact('metrics.json','重建指标 JSON');}
  }
  const stages={prepare:'检查照片',match:'验证视角匹配',reconstruct:'注册相机与三角化',refine:'优化相机与点云',done:'完成'};
  async function poll(){try{const data=await (await api(`/api/jobs/${job}`)).json();
    $('state').textContent={complete:'处理完成',failed:'本次处理失败',cancelled:'任务已取消',interrupted:'任务曾被中断'}[data.state] || stages[data.progress?.stage] || '正在处理';
    $('message').textContent=data.progress?.message || data.message || data.state;
    $('progress').value=data.state==='complete'?1:data.progress?.stage_progress || 0;
    if(['complete','failed','cancelled','interrupted','uploading'].includes(data.state)){busy=false;controls();results(data);await historyList();return;}
    timer=setTimeout(poll,900);
  }catch(error){busy=false;controls();showError(error.message);}}
  async function historyList(){try{const data=await(await api('/api/jobs')).json();$('history').replaceChildren();
    for(const item of data.sort((a,b)=>b.created-a.created).slice(0,12)){const b=document.createElement('button');b.className='secondary';b.textContent=`${item.id.slice(0,8)} · ${item.state} · ${item.images} images`;
      b.addEventListener('click',()=>{if(busy){showError('请先完成或取消当前任务。');return;}if(timer)clearTimeout(timer);job=item.id;busy=['running','starting'].includes(item.state);controls();poll();});$('history').append(b);}
  }catch(error){showError(error.message);}}
  $('start').addEventListener('click',async()=>{busy=true;job=null;controls();$('error').classList.add('hidden');$('result').classList.add('hidden');
    try{let intrinsics=null;const selected=$('intrinsics').files[0];if(selected){if(selected.size>8192)throw new Error('标定文件超过 8 KiB。');intrinsics=JSON.parse(await selected.text());}
      const created=await(await api('/api/jobs','POST',{})).json();job=created.id;
      for(let i=0;i<files.length;i++){$('state').textContent=`导入照片 ${i+1}/${files.length}`;$('message').textContent=files[i].name;$('progress').value=i/files.length;
        await api(`/api/jobs/${job}/images?name=${encodeURIComponent(files[i].name)}`,'POST',files[i],true);}
      await api(`/api/jobs/${job}/start`,'POST',{mode:$('mode').value,preset:$('preset').value,intrinsics});controls();poll();
    }catch(error){busy=false;controls();showError(error.message);}});
  $('cancel').addEventListener('click',async()=>{try{$('cancel').disabled=true;await api(`/api/jobs/${job}/cancel`,'POST',{});$('message').textContent='已请求取消，等待进程退出。';}catch(error){showError(error.message);controls();}});
  window.addEventListener('beforeunload',()=>{for(const url of urls)URL.revokeObjectURL(url);});
  if(!token){showError('请使用终端输出的完整本地访问链接打开工作台。');}
  else historyList();controls();
})();
