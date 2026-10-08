/* Original dependency-free CPU point-cloud viewer. No network or telemetry. */
(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('report-data').textContent);
  const $ = id => document.getElementById(id);
  const m = data.metrics || {}, audit = data.audit || {};
  const text = (id, value) => { $(id).textContent = value; };
  const number = value => Number.isFinite(value) ? value.toLocaleString(undefined, {maximumFractionDigits: 3}) : '—';
  text('registered', `${m.registered_images ?? 0} / ${m.input_images ?? (audit.images || []).length}`);
  text('points', number(m.points));
  text('scale', m.scale === 'arbitrary' ? '任意尺度' : (m.scale || '未定'));
  text('backend', m.backend || 'Input inspection / 输入预检');
  text('error', Number.isFinite(m.reprojection_median_px) ? `${number(m.reprojection_median_px)} px` : '—');
  if (m.backend === 'stereo-sgbm') {
    text('errorlabel', 'CONSISTENT PIXELS / 有效像素');
    text('error', `${number(100 * m.valid_pixel_fraction)}%`);
  }
  text('connectivity', `${(audit.components || []).length} connected groups · ${(audit.verified_pairs ?? audit.verified_edges ?? 0)} verified pairs`);
  text('verdict', m.status === 'partial' ? '部分相机未注册：检查缺失视角，不能把当前结果当成完整模型。' :
    m.backend === 'stereo-sgbm' ? '这是标定双目生成的开放表面。尺度继承自标定基线；不保证封闭或具有真实纹理贴图。' :
    data.points.length ? '这是稀疏几何，不是稠密或封闭网格。导出的相机和观测可供后续处理。' : '输入检查已记录。没有输出三维几何，不代表重建已经完成。');
  if (data.error) {
    text('title', '本次重建未完成。');
    const p = document.createElement('div'); p.className = 'notice error'; p.textContent = data.error;
    $('failure').append(p);
  }
  for (const note of (audit.notes || [])) {
    const p = document.createElement('p'); p.className = 'quiet'; p.textContent = note; $('notes').append(p);
  }
  const labels = {soft_image:'可能模糊',mostly_dark:'偏暗',mostly_bright:'高光过多',limited_texture:'纹理不足'};
  for (const image of (audit.images || [])) {
    const row = document.createElement('tr');
    const values = [image.name, image.features ?? image.keypoints, image.sharpness ?? image.blur_variance,
      (image.flags || []).map(x => labels[x] || x).join(' · ') || '未触发阈值'];
    values.forEach((value, i) => { const cell = document.createElement('td');
      cell.textContent = typeof value === 'number' ? number(value) : (value ?? '—');
      if (i === 3 && image.flags?.length) cell.style.color = 'var(--warn)'; row.append(cell); });
    $('auditrows').append(row);
  }
  if (!(audit.images || []).length) { const row = document.createElement('tr'); const cell = document.createElement('td');
    cell.colSpan = 4; cell.textContent = m.backend === 'stereo-sgbm' ? '双目模式使用独立的标定、视差与左右一致性检查。' : '没有可用的图像诊断。';
    row.append(cell); $('auditrows').append(row); }
  text('rejected', (audit.rejected || []).length ? `跳过的输入：${JSON.stringify(audit.rejected)}` : '未丢弃原始文件；标准化导出不包含 EXIF 元数据。');
  text('metadata', JSON.stringify({metrics: m, audit}, null, 2));
  text('previewcount', `${data.points.length.toLocaleString()} preview points`);
  const canvas = $('cloud'), ctx = canvas.getContext('2d');
  if (!ctx) return;
  let yaw = 0, pitch = 0, zoom = 1, pending = false;
  const points = data.points || [], colors = data.colors || [];
  const center = [0, 0, 0]; let radius = 1;
  if (points.length) {
    for (let k = 0; k < 3; k++) {
      const ordered = points.map(p => p[k]).sort((a,b) => a-b);
      center[k] = ordered[Math.floor(ordered.length / 2)];
    }
    const lengths = points.map(p => Math.hypot(...p.map((v,k) => v-center[k]))).sort((a,b)=>a-b);
    radius = Math.max(lengths[Math.floor(lengths.length * .95)], 1e-8);
  }
  const rotate = p => {
    const a = (p[0]-center[0])/radius, b = (p[1]-center[1])/radius, c = (p[2]-center[2])/radius;
    const x = a*Math.cos(yaw)+c*Math.sin(yaw), z = -a*Math.sin(yaw)+c*Math.cos(yaw);
    return [x, b*Math.cos(pitch)-z*Math.sin(pitch), b*Math.sin(pitch)+z*Math.cos(pitch)];
  };
  function draw() {
    pending = false;
    const ratio = Math.min(window.devicePixelRatio || 1, 2), w = canvas.clientWidth, h = canvas.clientHeight;
    canvas.width = Math.round(w*ratio); canvas.height = Math.round(h*ratio); ctx.scale(ratio,ratio); ctx.clearRect(0,0,w,h);
    ctx.strokeStyle = '#2b3b44'; ctx.lineWidth = .5;
    for(let x=0; x<w; x+=40){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.stroke();}
    for(let y=0; y<h; y+=40){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();}
    if (!points.length) {ctx.fillStyle = '#a0b1b9';ctx.font = '15px system-ui';ctx.textAlign='center';ctx.fillText('暂无点云 / No geometry available',w/2,h/2);return;}
    const scale = Math.min(w,h)*.39*zoom;
    const projected = points.map((p,i)=>{const q=rotate(p); return [q[0]*scale+w/2,q[1]*scale+h/2,q[2],i];}).sort((a,b)=>b[2]-a[2]);
    const size = Math.min(4,Math.max(1.4,2*zoom));
    for(const [x,y,z,i] of projected){if(x<0||y<0||x>w||y>h)continue;
      const c=colors[i] || [164,236,174];ctx.fillStyle=`rgb(${c[0]},${c[1]},${c[2]})`;ctx.fillRect(x,y,size,size);}
    ctx.strokeStyle='#a4ecae';ctx.lineWidth=1.4;
    for(const camera of (data.cameras||[])){const c=rotate(camera.center || [0,0,0]); const x=c[0]*scale+w/2,y=c[1]*scale+h/2;
      ctx.strokeRect(x-4,y-3,8,6);}
  }
  const schedule = () => {if(!pending){pending=true;requestAnimationFrame(draw);}};
  let last = null;
  canvas.addEventListener('pointerdown', e=>{last=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId);});
  canvas.addEventListener('pointermove', e=>{if(!last)return;yaw+=(e.clientX-last[0])*.008;pitch+=(e.clientY-last[1])*.008;last=[e.clientX,e.clientY];schedule();});
  for(const name of ['pointerup','pointercancel','lostpointercapture']) canvas.addEventListener(name,()=>{last=null;});
  canvas.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(.15,Math.min(8,zoom*Math.exp(-e.deltaY*.001)));schedule();},{passive:false});
  const reset = ()=>{yaw=0;pitch=0;zoom=1;schedule();}; canvas.addEventListener('dblclick',reset);$('reset').addEventListener('click',reset);
  new ResizeObserver(schedule).observe(canvas); schedule();
})();
