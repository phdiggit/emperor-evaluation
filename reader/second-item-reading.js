"use strict";

(() => {
  const screenEl = document.getElementById("screen");
  if (!screenEl) return;

  const METHOD_BAND_LABELS = {G0:"E",G1:"D",G2:"C",G3:"B",G4:"A",G5:"S"};
  const METHOD_MAX = {"A制度建设":100,"B1官僚治理":100,"B2反馈与约束":80};
  const METHOD_PUBLIC = {"A制度建设":"制度建设","B1官僚治理":"官僚治理","B2反馈与约束":"反馈与约束"};
  const FINANCE_MAX = {"C1民生":80,"C2经济财政":35,"C3社会安全":60};
  const FINANCE_PUBLIC = {"C1民生":"民生","C2经济财政":"经济财政","C3社会安全":"社会安全"};\n  const STATE_PUBLIC_GRADE = {1:"E",2:"D",3:"C",4:"B",5:"A",6:"S"};\n  const LOSS_PUBLIC_TEXT = {0:"未见独立有效低谷",1:"有局部或短时损害",2:"出现明显低谷",3:"出现严重低谷"};
  const HANDOFF_PUBLIC_GRADE = {0:"E",1:"D",2:"C",3:"B",4:"A",5:"S"};
  function handoffGrade(value){const n=finite(value);return n!=null&&Number.isInteger(n)?HANDOFF_PUBLIC_GRADE[n]||"—":"—";}
  const HISTORICAL_SECOND_POOL = 185;
  const HISTORICAL_OUT_OF_CURRENT_POOL = 11;
  let scheduled = false;

  function finite(value){if(value==null||value==="")return null;const n=Number(value);return Number.isFinite(n)?n:null;}
  function fmt(value,digits=1){const n=finite(value);return n==null?"—":n.toFixed(digits);}
  function signedFmt(value,digits=1){const n=finite(value);return n==null?"—":`${n>0?"+":""}${n.toFixed(digits)}`;}
  // Once a public renderer owns a leaf, do not replace its text with the
  // intermediate numerical/technical presentation on the next observer pass.
  function setNodeText(node,text){
    if(!node||["publicCopy","publicScore","publicValue","publicTitle"].some(key=>key in node.dataset))return;
    if(node.textContent!==text)node.textContent=text;
  }
  function safeText(value){return String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));}
  function directText(node){if(!node)return"";return Array.from(node.childNodes).filter(c=>c.nodeType===Node.TEXT_NODE).map(c=>c.nodeValue||"").join("").trim();}

  function parsedNetRoute(){
    const m=location.hash.match(/^#net\/([^/?#]+)\/(all|first|second|third|fourth)(?:\/|$)/);
    if(!m)return null;
    try{return{id:decodeURIComponent(m[1]),major:m[2]};}catch{return null;}
  }
  function recordForNetRoute(){if(typeof byId==="undefined")return null;const r=parsedNetRoute();return r?byId.get(r.id)||null:null;}
  function recordForPersonRoute(){if(typeof byId==="undefined")return null;const m=location.hash.match(/^#person\/([^/?#]+)/);if(!m)return null;try{return byId.get(decodeURIComponent(m[1]))||null;}catch{return null;}}
  function recordsForCompareRoute(){
    if(typeof byId==="undefined"||!location.hash.startsWith("#compare/"))return[];
    return location.hash.slice(9).split("/").filter(Boolean).slice(0,2).map(id=>{try{return byId.get(decodeURIComponent(id))||null;}catch{return null;}}).filter(Boolean);
  }
  function itemsFor(record,key){return new Map((record?.net?.component_details?.[key]||[]).map(item=>[item.label,item]));}

  function currentSecondPool(){
    if(typeof byId==="undefined")return[];
    return Array.from(byId.values()).filter(r=>!r?.supplementary&&finite(r?.net?.second_item_score)!=null).map(r=>({id:String(r.ruler_id||""),score:finite(r.net.second_item_score)}));
  }
  function secondPoolPosition(record){
    const score=finite(record?.net?.second_item_score);if(score==null)return null;
    const eligible=currentSecondPool();if(!eligible.length)return null;
    return{rank:1+eligible.filter(x=>x.score>score).length,total:eligible.length};
  }
  function secondTotals(record){
    const method=itemsFor(record,"method"),finance=itemsFor(record,"finance"),handoff=itemsFor(record,"handoff");
    return{method,finance,handoff,
      methodScore:finite(method.get("治理手段")?.value),resultScore:finite(finance.get("治理结果")?.value),handoffScore:finite(handoff.get("交接得分")?.value),
      c1:finite(finance.get("C1民生")?.value),c2:finite(finance.get("C2经济财政")?.value),c3:finite(finance.get("C3社会安全")?.value),c4:finite(finance.get("C4恢复与成本")?.value),
      totalScore:finite(record?.net?.second_item_score??handoff.get("第二项合计")?.value),pool:secondPoolPosition(record)};
  }
  function methodBand(item){const m=String(item?.grade||"").match(/\bG([0-5])\b/);return m?METHOD_BAND_LABELS[`G${m[1]}`]:"正式档未标明";}
  function stateMeta(item){const m=String(item?.grade||"").match(/\bC[123]-(\d+)\s*\/\s*L(\d+)\b/);if(!m)return"";const low=Number(m[2]);return`主要状态第${m[1]}档｜${low===0?"无额外低谷修正":`低谷修正${low}级`}`;}
  function boundaryExcerpt(item){return String(item?.reader_boundary||"").trim()?"适用范围与限制见展开说明":"";}
  function rankText(t){
    if(!t.pool)return"";
    const pct=Math.max(1,Math.min(100,Math.ceil(t.pool.rank/t.pool.total*100)));
    return`当前已结算人物：第 ${fmt(t.pool.rank,0)} / ${fmt(t.pool.total,0)}（约前 ${pct}%）`;
  }
  function componentTakeaway(t){
    const parts=[
      {label:"制度与行政",score:finite(t.methodScore),max:165},
      {label:"民生与社会",score:finite(t.resultScore),max:202},
      {label:"政权交接",score:finite(t.handoffScore),max:20},
    ].filter(x=>x.score!=null).map(x=>({...x,ratio:x.score/x.max})).sort((a,b)=>b.ratio-a.ratio);
    if(parts.length<2)return"先看三块构成，再展开到各项依据。";
    const best=parts[0],weak=parts[parts.length-1];
    if(Math.abs(best.ratio-weak.ratio)<0.08)return"三块得分相对接近，没有明显由单一分项主导。";
    return`从三块得分看，${best.label}是相对最强的一项，${weak.label}相对最弱。`;
  }
  function personConclusion(t,record){
    const readerSummary=String(record?.net?.reader_governance_summary||"").trim();
    return readerSummary||componentTakeaway(t);
  }

  function ensureStyles(){
    if(document.getElementById("second-item-reading-style"))return;
    const style=document.createElement("style");style.id="second-item-reading-style";
    style.textContent=`
      .second-item-reader-summary{border:1px solid var(--line);border-left:4px solid var(--green);border-radius:6px;padding:16px 18px;margin:0 0 18px;background:#f6f7f1}
      .second-item-reader-summary h2{font-size:21px;margin:0 0 8px}.second-item-person-conclusion{font-size:15px;line-height:1.8;margin:8px 0 10px}
      .second-item-rank{display:inline-block;margin:2px 0 8px;padding:4px 9px;border-radius:4px;background:#e8ece4;color:var(--green);font-size:12px;font-weight:600}
      .second-item-total-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:12px 0}.second-item-total-grid div{border:1px solid var(--line);border-radius:5px;padding:10px 12px;background:#fcfbf7;font-size:12px}.second-item-total-grid b{display:block;font:21px Georgia,serif;color:var(--green);margin-top:3px}
      .second-item-equation{margin-top:12px;padding-top:11px;border-top:1px solid var(--line);font-size:14px}.second-item-equation strong{color:var(--green)}
      .second-item-formula{margin-top:12px;border-top:1px solid var(--line);padding:10px 0 0}.second-item-formula>summary{font-size:13px;color:var(--muted)}.second-item-formula .second-item-equation{margin-top:8px;padding-top:0;border-top:0}
      .second-item-scale-note{display:block;margin-top:4px;font-size:11px;color:var(--green);font-weight:600}.second-item-group-intro{margin:0 0 14px;padding:11px 13px;border-left:3px solid var(--gold);background:#f1eee6;font-size:13px;line-height:1.75}.second-item-c4-note{margin:0 0 12px;padding:9px 11px;border-left:3px solid var(--green);background:#f1eee6;font-size:13px;line-height:1.75}
      .second-item-card-breakdown,.second-item-inline-rank{font-size:12px;color:var(--muted);line-height:1.65}.second-item-inline-rank{display:block;margin-top:3px;color:var(--green)}
      .net-formal-basis-raw{margin-top:12px;border-top:1px solid var(--line)}.net-formal-basis-raw>.net-formal-basis-content{padding-top:8px}.second-item-pool-note{margin-top:8px;font-size:12px;line-height:1.65;color:var(--muted)}
      .net-major-card.second-item-card .big{font-size:30px}@media(max-width:700px){.second-item-total-grid{grid-template-columns:1fr}}
    `;document.head.append(style);
  }
  function addGroupIntro(section,key,text){if(!section)return;let p=section.querySelector(`:scope > [data-second-intro="${key}"]`);if(!p){p=document.createElement("p");p.className="second-item-group-intro";p.dataset.secondIntro=key;const h=section.querySelector(":scope > h2");if(h?.nextSibling)section.insertBefore(p,h.nextSibling);else section.append(p);}setNodeText(p,text);}
  function metricDetail(section,labels){const wanted=new Set(Array.isArray(labels)?labels:[labels]);return Array.from(section?.querySelectorAll(":scope > .net-metric-detail")||[]).find(d=>wanted.has(d.dataset.secondSourceLabel||d.querySelector(":scope > summary strong")?.textContent.trim()))||null;}
  function markSourceLabel(detail,label){if(detail&&!detail.dataset.secondSourceLabel)detail.dataset.secondSourceLabel=label;}
  function setMetricDisplay(detail,valueText,noteText,titleText=""){if(!detail)return;const s=detail.querySelector(":scope > summary"),strong=s?.querySelector("strong"),value=s?.querySelector(":scope > b"),span=s?.querySelector(":scope > span");if(titleText)setNodeText(strong,titleText);setNodeText(value,valueText);if(!span||"publicGradeNote" in span.dataset)return;let note=span.querySelector(":scope > .second-item-scale-note");if(!note){note=document.createElement("small");note.className="second-item-scale-note";span.append(note);}setNodeText(note,noteText);}
  function joinNote(...parts){return parts.filter(Boolean).join("｜");}

  function ensureLandingCard(record,t){
    if(!location.hash.match(/^#net\/[^/?#]+\/(?:all)?$/))return;
    const card=Array.from(document.querySelectorAll(".net-major-card")).find(x=>x.getAttribute("href")?.includes("/second"));if(!card)return;
    card.classList.add("second-item-card");
    const heading=card.querySelector("h3,h2");if(heading&&heading.textContent.includes("治国净收益"))setNodeText(heading,"治国成效");
    setNodeText(card.querySelector(".big"),t.totalScore==null?"—":`${fmt(t.totalScore)} / 387`);
    const desc=Array.from(card.querySelectorAll(":scope > p")).find(p=>!p.classList.contains("sources")&&!p.classList.contains("second-item-card-breakdown"));
    setNodeText(desc,"评价实际掌权期间的制度行政、民生社会与最终交接；军事、边疆与统一功业在其他板块单独评价。");
    if([t.methodScore,t.resultScore,t.handoffScore].some(v=>v==null))return;
    let p=card.querySelector(":scope > .second-item-card-breakdown");if(!p){p=document.createElement("p");p.className="second-item-card-breakdown";const sources=card.querySelector(":scope > p.sources");card.insertBefore(p,sources||null);}const rank=rankText(t);
    setNodeText(p,`${rank?`${rank} · `:""}制度与行政 ${fmt(t.methodScore)}/165 · 民生与社会 ${fmt(t.resultScore)}/202 · 政权交接 ${fmt(t.handoffScore)}/20`);
  }
  function ensureSecondSummary(record,t){
    if(!location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/))return;const container=document.getElementById("net-major-body");if(!container||[t.methodScore,t.resultScore,t.handoffScore,t.totalScore].some(v=>v==null))return;
    const rank=rankText(t),takeaway=personConclusion(t,record);let summary=container.querySelector(":scope > .second-item-reader-summary");if(!summary){summary=document.createElement("section");summary.className="second-item-reader-summary";container.insertBefore(summary,container.firstChild);}
    const key=[t.methodScore,t.resultScore,t.handoffScore,t.totalScore,t.c4,rank,takeaway].join("|");
    if(summary.dataset.secondRenderKey!==key){summary.innerHTML=`<h2>先看治国结论</h2><p class="second-item-person-conclusion">${safeText(takeaway)}</p>${rank?`<span class="second-item-rank">${rank}</span>`:""}<div class="second-item-total-grid"><div>制度与行政<b>${fmt(t.methodScore)} / 165</b><small>制度建设、官僚治理与反馈约束</small></div><div>民生与社会<b>${fmt(t.resultScore)} / 202</b><small>民生、经济财政、社会安全与恢复成本</small></div><div>政权交接<b>${fmt(t.handoffScore)} / 20</b><small>行政承接与继承稳定</small></div></div><details class="second-item-formula"><summary>这个分数怎么算？</summary><div class="second-item-equation">${fmt(t.methodScore)} + ${fmt(t.resultScore)} + ${fmt(t.handoffScore)} = <strong>治国成效 ${fmt(t.totalScore)} / 387</strong></div><p class="subline">本项量表理论范围为 -27.5～387。0不是及格线、历史平均或“中性线”。小数位来自统一计分公式，不表示历史判断本身具有同等测量精度。</p></details>`;summary.dataset.secondRenderKey=key;}
    const page=document.querySelector(".net-detail-page"),intro=page?.querySelector(":scope > .panel");
    if(intro){const main=Array.from(intro.querySelectorAll(":scope > p")).find(p=>!p.classList.contains("subline")),score=intro.querySelector(":scope > p.subline");setNodeText(main,"治国成效看三件事：国家机器如何运转、统治时期民生与社会表现如何、离场时能否留下稳定可运行的交接。军事、边疆与统一功业另在其他板块评价。");setNodeText(score,`治国成效总分：${fmt(t.totalScore)} / 387${rank?`；${rank}`:""}。先看结论，再展开到各项依据。`);}
  }

  function ensureMethodGroup(t){
    const section=document.getElementById("net-group-method");if(!section)return;setNodeText(section.querySelector(":scope > h2"),"制度与行政");
    addGroupIntro(section,"method",`这一组看国家机器如何建立规则、配置官僚并形成反馈约束。三项使用不同原始量表，统一折算后本组最高165分；当前得分为 ${fmt(t.methodScore)} / 165。具体折算方法放在各项展开内容中。`);
    for(const label of ["A制度建设","B1官僚治理","B2反馈与约束"]){const item=t.method.get(label),detail=metricDetail(section,[label,METHOD_PUBLIC[label]]);markSourceLabel(detail,label);if(!item||!detail)continue;setMetricDisplay(detail,`${fmt(item.value)} / ${METHOD_MAX[label]} 指数`,joinNote(`正式方向档：${methodBand(item)}`,boundaryExcerpt(item)),METHOD_PUBLIC[label]);}
  }
  function ensureC4Note(detail,value){
    const body=detail?.querySelector(":scope > .net-metric-body");if(!body)return;let note=body.querySelector(":scope > .second-item-c4-note");if(!note){note=document.createElement("p");note.className="second-item-c4-note";body.insertBefore(note,body.firstChild);}
    if(value==null)setNodeText(note,"这是净调整项，不与前三项使用同一满分尺度；具体正负构成以下方正式裁决为准。");
    else if(value>0)setNodeText(note,"这是净调整项。正数表示恢复增量在扣除本人可归责恶化与额外民力、治理成本后仍有净加分。");
    else if(value<0)setNodeText(note,"这是净调整项。负数表示本人可归责恶化和/或额外民力、治理成本超过恢复增量，形成净扣分；具体构成以下方正式裁决为准。");
    else setNodeText(note,"本调整项为0只表示这里的净调整为0：可能没有新增可计变化，也可能相关恶化已经在前三项中体现而不再重复扣。0不等于“没有问题”。");
  }
  function ensureFinanceGroup(t){
    const section=document.getElementById("net-group-finance");if(!section)return;setNodeText(section.querySelector(":scope > h2"),"民生与社会");
    addGroupIntro(section,"finance",`这一组看统治时期的民生、经济财政、社会安全，以及恢复与额外成本。前三项满分分别为80、35、60，C4另记恢复增量、本人可归责恶化与额外民力/治理成本的净调整；四项合计为 ${fmt(t.resultScore)} / 202。`);
    for(const label of ["C1民生","C2经济财政","C3社会安全"]){const item=t.finance.get(label),detail=metricDetail(section,[label,FINANCE_PUBLIC[label]]);markSourceLabel(detail,label);if(!item||!detail)continue;setMetricDisplay(detail,`${fmt(item.value)} / ${FINANCE_MAX[label]} 分`,joinNote(`状态分·满分${FINANCE_MAX[label]}`,stateMeta(item),boundaryExcerpt(item)),FINANCE_PUBLIC[label]);}
    const item=t.finance.get("C4恢复与成本"),detail=metricDetail(section,["C4恢复与成本","恢复与额外成本（C4）","C4恢复、恶化与额外成本调整"]);markSourceLabel(detail,"C4恢复与成本");
    if(item&&detail){setMetricDisplay(detail,`${signedFmt(item.value)} 分`,joinNote("净调整项","恢复 − 可归责恶化 − 额外成本",boundaryExcerpt(item)),"恢复与额外成本（C4）");ensureC4Note(detail,item.value);}
  }
  function ensureHandoffGroup(t){
    const section=document.getElementById("net-group-handoff");if(!section)return;setNodeText(section.querySelector(":scope > h2"),"政权交接");
    const d1i=t.handoff.get("D1继任行政连续性"),d3i=t.handoff.get("D3政权交接稳定"),d1=finite(d1i?.value),d3=finite(d3i?.value),cap=finite(t.handoff.get("低侧封顶")?.value),score=t.handoffScore;
    let exp="统治如何收尾，会直接决定国家机器和继承秩序能否平稳延续，因此交接结果计入治国成效。行政连续性看旧国家机器有多少被接住，交接稳定看继承过程是否稳定。";
    if([d1,d3,cap,score].every(v=>v!=null))exp=`统治如何收尾，会直接决定国家机器和继承秩序能否平稳延续，因此交接结果计入治国成效。行政连续性为 ${handoffGrade(d1)}档，交接稳定为 ${handoffGrade(d3)}档；较弱一侧把本项最高分限制在 ${fmt(cap)}，最终得分 ${fmt(score)} / 20。`;
    addGroupIntro(section,"handoff",exp);
    const d1d=metricDetail(section,["D1继任行政连续性","行政连续性（D1）","行政连续性"]),d3d=metricDetail(section,["D3政权交接稳定","交接稳定（D3）","交接稳定"]);markSourceLabel(d1d,"D1继任行政连续性");markSourceLabel(d3d,"D3政权交接稳定");
    setMetricDisplay(d1d,d1==null?"—":`${handoffGrade(d1)}档`,joinNote("行政承接",boundaryExcerpt(d1i)),"行政连续性");
    setMetricDisplay(d3d,d3==null?"—":`${handoffGrade(d3)}档`,joinNote("终局继承",boundaryExcerpt(d3i)),"交接稳定");
    for(const strong of section.querySelectorAll(".net-calculations .component strong"))if(strong.textContent.trim()==="低侧封顶")setNodeText(strong,"交接短板上限");
    for(const small of section.querySelectorAll(".net-calculations .component small"))setNodeText(small,small.textContent.replace(/低侧封顶/g,"交接短板上限"));
  }

  function formalBasisDetails(detail){return Array.from(detail?.querySelectorAll(":scope > .net-metric-body > details")||[]).find(block=>{const text=block.querySelector(":scope > summary")?.textContent.trim()||"";return block.classList.contains("net-formal-basis-raw")||text==="当前人物的完整裁决原文"||text==="正式裁决原文（未改写）";})||null;}
  function restoreFormalBasis(section,itemMap){
    if(!section)return;
    for(const [label,item] of itemMap.entries()){
      const raw=String(item?.reader_full_basis||"").trim(),summaryRaw=String(item?.reader_summary||"").trim();if(!raw||raw===summaryRaw)continue;
      const displays=label==="C4恢复与成本"?[label,"恢复与额外成本（C4）","C4恢复、恶化与额外成本调整"]:label in METHOD_PUBLIC?[label,METHOD_PUBLIC[label]]:label in FINANCE_PUBLIC?[label,FINANCE_PUBLIC[label]]:[label];
      const detail=metricDetail(section,displays);if(!detail)continue;markSourceLabel(detail,label);const body=detail.querySelector(":scope > .net-metric-body");if(!body)continue;
      let block=formalBasisDetails(detail);if(!block){block=document.createElement("details");const audit=body.querySelector(":scope > .net-audit-sources");body.insertBefore(block,audit||null);block.append(document.createElement("summary"));}
      block.classList.add("net-formal-basis-raw");const summary=block.querySelector(":scope > summary");setNodeText(summary,"正式裁决原文（未改写）");
      let content=block.querySelector(":scope > .net-formal-basis-content");if(!content){for(const child of Array.from(block.children))if(child!==summary)child.remove();content=document.createElement("div");content.className="net-formal-basis-content";block.append(content);}
      if(content.dataset.rawKey!==raw){content.innerHTML=typeof prose==="function"?prose(raw):`<p class="prose"></p>`;if(typeof prose!=="function")setNodeText(content.querySelector("p"),raw);content.dataset.rawKey=raw;}
    }
  }
  function restoreFormalBasisForRoute(record){const route=parsedNetRoute();if(!route||!record?.net?.component_details)return;const groups=route.major==="second"?["method","finance","handoff"]:route.major==="third"?["strategic","military"]:route.major==="fourth"?["civilization"]:[];for(const key of groups)restoreFormalBasis(document.getElementById(`net-group-${key}`),itemsFor(record,key));}
  function ensureAuditPoolNotes(t){
    if(!location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/))return;const current=t.pool?.total;
    for(const audit of document.querySelectorAll("#net-major-body .net-audit-sources")){let note=audit.querySelector(":scope > .second-item-pool-note");if(!note){note=document.createElement("p");note.className="second-item-pool-note";const sources=audit.querySelector(":scope > .sources");audit.insertBefore(note,sources||null);}setNodeText(note,`排名口径：当前公开名次只比较已完成治国成效结算的${current??"现有"}人。原第二项总表仍保留${HISTORICAL_SECOND_POOL}人历史快照，其中含${HISTORICAL_OUT_OF_CURRENT_POOL}条现已不在当前正式评价对象中的旧记录，因此原文件内旧rank不等于当前公开名次。`);}
  }

  function groupKindFromSummary(summary){const text=summary?.textContent.trim()||"";if(text.includes("制度与行政"))return"method";if(text.includes("财政与民生")||text.includes("民生与社会"))return"finance";if(text.includes("政权交接")||text.includes("交接质量"))return"handoff";return"";}
  function publicGroupTitle(kind){return{method:"制度与行政",finance:"民生与社会",handoff:"政权交接"}[kind]||"";}
  function replaceCompactNote(span,text){
    if(!span||!text||"publicGradeNote" in span.dataset)return;
    let note=span.querySelector(":scope > .second-item-scale-note");
    for(const small of Array.from(span.querySelectorAll(":scope > small")))if(small!==note)small.remove();
    if(!note){note=document.createElement("small");note.className="second-item-scale-note";span.append(note);}
    setNodeText(note,text);
  }
  function setRowLabel(span,label){
    if(!span||"publicTitle" in span.dataset)return;
    const textNode=Array.from(span.childNodes).find(c=>c.nodeType===Node.TEXT_NODE);
    if(textNode){if(textNode.nodeValue!==`${label} `)textNode.nodeValue=`${label} `;}
    else span.insertBefore(document.createTextNode(`${label} `),span.firstChild);
  }
  function formatCompactGroup(root,record,kind){
    if(!root||!record?.net||!kind)return;const map=itemsFor(record,kind);
    for(const row of root.querySelectorAll(":scope .component")){
      const span=row.querySelector(":scope > span"),value=row.querySelector(":scope > b");if(!span||!value)continue;const label=span.dataset.secondSourceLabel||directText(span)||span.querySelector("strong")?.textContent.trim()||"";let sourceLabel=label;
      if(!map.has(sourceLabel)){sourceLabel=Object.keys(METHOD_PUBLIC).find(k=>METHOD_PUBLIC[k]===label)||Object.keys(FINANCE_PUBLIC).find(k=>FINANCE_PUBLIC[k]===label)||({"恢复与额外成本（C4）":"C4恢复与成本","行政连续性（D1）":"D1继任行政连续性","交接稳定（D3）":"D3政权交接稳定","行政连续性":"D1继任行政连续性","交接稳定":"D3政权交接稳定","交接短板上限":"低侧封顶","政权交接得分":"交接得分","治国成效合计":"第二项合计"}[label]||label);}
      span.dataset.secondSourceLabel=sourceLabel;const item=map.get(sourceLabel);
      if(kind==="method"&&item&&METHOD_MAX[sourceLabel]){setRowLabel(span,METHOD_PUBLIC[sourceLabel]);setNodeText(value,`${fmt(item.value)} / ${METHOD_MAX[sourceLabel]} 指数`);replaceCompactNote(span,joinNote(`正式方向档：${methodBand(item)}`,boundaryExcerpt(item)));}
      else if(kind==="finance"&&item&&FINANCE_MAX[sourceLabel]){setRowLabel(span,FINANCE_PUBLIC[sourceLabel]);setNodeText(value,`${fmt(item.value)} / ${FINANCE_MAX[sourceLabel]} 分`);replaceCompactNote(span,joinNote(stateMeta(item),boundaryExcerpt(item)));}
      else if(kind==="finance"&&item&&sourceLabel==="C4恢复与成本"){setRowLabel(span,"恢复与额外成本（C4）");setNodeText(value,`${signedFmt(item.value)} 分`);replaceCompactNote(span,joinNote("净调整项","恢复 − 可归责恶化 − 额外成本",boundaryExcerpt(item)));}
      else if(kind==="handoff"&&item&&sourceLabel==="D1继任行政连续性"){setRowLabel(span,"行政连续性");setNodeText(value,`${handoffGrade(item.value)}档`);replaceCompactNote(span,joinNote("行政承接",boundaryExcerpt(item)));}
      else if(kind==="handoff"&&item&&sourceLabel==="D3政权交接稳定"){setRowLabel(span,"交接稳定");setNodeText(value,`${handoffGrade(item.value)}档`);replaceCompactNote(span,joinNote("终局继承",boundaryExcerpt(item)));}
      else if(kind==="handoff"&&sourceLabel==="低侧封顶"){setRowLabel(span,"交接短板上限");replaceCompactNote(span,"交接短板决定本项最高可得分");}
      else if(kind==="handoff"&&sourceLabel==="交接得分"){setRowLabel(span,"政权交接得分");setNodeText(value,`${fmt(item?.value)} / 20 分`);replaceCompactNote(span,"行政连续性与交接稳定合成");}
      else if(kind==="handoff"&&sourceLabel==="第二项合计"){setRowLabel(span,"治国成效合计");setNodeText(value,`${fmt(item?.value)} / 387 分`);replaceCompactNote(span,"制度与行政 + 民生与社会 + 政权交接");}
    }
  }
  function enhanceCompactGroups(record){
    if(!record?.detail_loaded||!record?.net)return;
    for(const details of screenEl.querySelectorAll("details")){const summary=details.querySelector(":scope > summary"),kind=groupKindFromSummary(summary);if(kind){if(summary&&summary.textContent.trim()!==publicGroupTitle(kind))setNodeText(summary,publicGroupTitle(kind));formatCompactGroup(details,record,kind);}}
  }
  function enhancePersonOverview(record){
    if(!record?.detail_loaded||!record?.net||!location.hash.startsWith("#person/"))return;const panel=document.getElementById("person-outcome");if(!panel)return;const t=secondTotals(record);
    for(const row of panel.querySelectorAll(":scope > .component")){const span=row.querySelector("span");if(!span||!["治国净收益","治国成效"].some(label=>directText(span).startsWith(label)))continue;setRowLabel(span,"治国成效");setNodeText(row.querySelector("b"),`${fmt(t.totalScore)} / 387`);let rank=span.querySelector(":scope > .second-item-inline-rank");if(!rank){rank=document.createElement("small");rank.className="second-item-inline-rank";span.append(rank);}setNodeText(rank,rankText(t));}
    enhanceCompactGroups(record);
  }
  function pendingSecondLabel(record){return record?.settlement_readiness==="PENDING_SECOND_ITEM_FORMAL_SETTLEMENT"?"待正式结算":"未入榜";}
  function enhanceCompare(records){
    if(records.length<2||records.some(r=>!r?.detail_loaded))return;const rows=Array.from(screenEl.querySelectorAll(".comparison tbody tr")),secondRow=rows.find(r=>["治国净收益","治国成效"].includes(r.cells?.[0]?.textContent.trim()));
    if(secondRow){setNodeText(secondRow.cells?.[0],"治国成效");records.forEach((record,index)=>{const cell=secondRow.cells[index+1];if(!cell)return;if(!record?.net){setNodeText(cell,pendingSecondLabel(record));return;}const t=secondTotals(record),key=`${t.totalScore}|${rankText(t)}`;if(cell.dataset.secondItemKey===key)return;cell.innerHTML=`<b>${fmt(t.totalScore)} / 387</b>${rankText(t)?`<small class="second-item-inline-rank">${rankText(t)}</small>`:""}`;cell.dataset.secondItemKey=key;});}
    const structureRow=rows.find(r=>r.cells?.[0]?.textContent.trim()==="构成与依据");
    if(structureRow){records.forEach((record,index)=>{const cell=structureRow.cells[index+1];if(!cell)return;if(!record?.net){if(record?.settlement_readiness==="PENDING_SECOND_ITEM_FORMAL_SETTLEMENT")setNodeText(cell,"治国成效正式结算待补；当前不进入治国成效排名。");return;}for(const details of cell.querySelectorAll("details")){const summary=details.querySelector(":scope > summary"),kind=groupKindFromSummary(summary);if(kind){setNodeText(summary,publicGroupTitle(kind));formatCompactGroup(details,record,kind);}}});}
  }

  function enhanceNetRoute(record){
    if(!record?.net)return;restoreFormalBasisForRoute(record);const route=parsedNetRoute();if(!route)return;const t=secondTotals(record);
    if(route.major==="all"){ensureLandingCard(record,t);return;}
    if(route.major!=="second")return;
    ensureSecondSummary(record,t);ensureMethodGroup(t);ensureFinanceGroup(t);ensureHandoffGroup(t);ensureAuditPoolNotes(t);
  }
  function enhance(){ensureStyles();const netRecord=recordForNetRoute();if(netRecord)enhanceNetRoute(netRecord);const personRecord=recordForPersonRoute();if(personRecord)enhancePersonOverview(personRecord);const compareRecords=recordsForCompareRoute();if(compareRecords.length)enhanceCompare(compareRecords);}
  function schedule(){if(scheduled)return;scheduled=true;requestAnimationFrame(()=>{scheduled=false;enhance();});}
  new MutationObserver(schedule).observe(screenEl,{childList:true,subtree:true,characterData:true});window.addEventListener("hashchange",schedule);schedule();
})();
