'use strict';
const $ = id => document.getElementById(id);
const el = (tag, text, className) => { const node=document.createElement(tag); if(text!==undefined) node.textContent=text; if(className) node.className=className; return node; };
function link(label, url) { const a=el('a',label); a.href=url; return a; }
async function refresh() {
  $('error').hidden=true;
  try {
    const response=await fetch('/api/research');
    if(!response.ok) throw new Error('無法讀取研究紀錄，請確認本機服務正在執行。');
    const data=await response.json();
    $('engine-status').textContent=data.installation.available ? '● 已偵測到本機 SPSS' : '尚未偵測到 SPSS 安裝';
    $('runs').replaceChildren();
    if(!data.runs.length) $('runs').append(el('p','尚未執行研究。先把上方想法交給 AI，完成後報告會出現在這裡。','empty'));
    for(const run of data.runs) {
      const card=el('article',undefined,'card run');
      card.append(el('span',run.status==='completed' ? (run.interpretation_id?'已完成 AI 解讀':'SPSS 結果已就緒'):'執行失敗，需檢查','badge'+(run.status==='failed'?' failed':'')));
      card.append(el('span',new Date(run.created_at).toLocaleDateString('zh-TW'),'date'));
      card.append(el('h3',run.question));
      card.append(el('p',`${run.analyses} 項分析 · ${run.charts} 張原生圖表 · ${run.id.slice(0,8)}`));
      const links=el('div',undefined,'links');
      const base='/api/research/runs/'+encodeURIComponent(run.id);
      links.append(link(run.interpretation_id?'閱讀完整解讀 ↗':'查看原生結果 ↗',base+'/report'+(run.interpretation_id?'?interpretation='+encodeURIComponent(run.interpretation_id):'')),link('SPSS 結果檔',base+'/viewer'),link('執行語法',base+'/syntax'));
      card.append(links); $('runs').append(card);
    }
    $('plans').replaceChildren();
    if(!data.plans.length) $('plans').append(el('p','AI 釐清研究問題並保存計畫後，你可以在這裡下載資料範本。','empty'));
    for(const plan of data.plans) {
      const row=el('div',undefined,'plan'); row.append(el('strong',plan.question));
      const links=el('div',undefined,'links'); const base='/api/research/plans/'+encodeURIComponent(plan.id);
      links.append(link('填資料範本 ↓',base+'/template'),link('欄位說明 ↓',base+'/dictionary'),link('研究計畫 ↓',base+'/json'));
      row.append(links); $('plans').append(row);
    }
  } catch(error) { $('error').textContent=error.message; $('error').hidden=false; }
}
$('copy-idea').addEventListener('click',async()=>{
  const idea=$('idea').value.trim();
  if(!idea) { $('copy-status').textContent='先輸入你想研究的問題。'; $('idea').focus(); return; }
  const prompt='使用 statstudio-spss 研究助理。我的想法是：'+idea+'\n請先問我缺少的必要資訊，告訴我要準備哪些資料，提供範本與統計方法建議。收到資料並確認條件後，透過 Python 執行本機 SPSS，製作原生圖表，再閱讀數值與圖形並保存有來源引用的解讀報告。';
  try { await navigator.clipboard.writeText(prompt); $('copy-status').textContent='已複製，貼到 Codex 或 Claude Code。'; }
  catch { $('copy-status').textContent='無法自動複製，請直接將你的想法貼給 AI。'; }
});
$('refresh').addEventListener('click',refresh);
refresh();
