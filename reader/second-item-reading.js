"use strict";

(() => {
  const screenEl = document.getElementById("screen");
  if (!screenEl) return;

  const METHOD_BAND_LABELS = {G0:"最低档",G1:"较低档",G2:"中低档",G3:"中档",G4:"较高档",G5:"最高档"};
  const METHOD_MAX = {"A制度建设":100,"B1官僚治理":100,"B2反馈与约束":80};
  const FINANCE_MAX = {"C1民生":80,"C2经济财政":35,"C3社会安全":60};
  const HISTORICAL_SECOND_POOL = 185;
  const HISTORICAL_OUT_OF_CURRENT_POOL = 11;
  let scheduled = false;

  function finite(value){if(value==null||value==="")return null;const n=Number(value);return Number.isFinite(n)?n:null;}
  function fmt(value,digits=1){const n=finite(value);return n==null?"—":n.toFixed(digits);}
  function signedFmt(value,digits=1){const n=finite(value);return n==null?"—":`${n>0?"+":""}${n.toFixed(digits)}`;}
  function setNodeText(node,text){if(node&&node.textContent!==text)node.textContent=text;}
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
  function boundaryExcerpt(item){const t=String(item?.reader_boundary||"").trim();if(!t)return"";const first=t.match(/^.*?[。！？；;]/)?.[0]||t;return`边界：${first.trim()}`;}
  function rankText(t){return t.pool?`当前主池已完成第二项结算：第 ${fmt(t.pool.rank,0)} / ${fmt(t.pool.total,0)}`:"";}
  function personConclusion(t){
    const a=methodBand(t.method.get("A制度建设")),b1=methodBand(t.method.get("B1官僚治理")),b2=methodBand(t.method.get("B2反馈与约束"));
    return`三块总账：治理手段 ${fmt(t.methodScore)} / 165，治理结果 ${fmt(t.resultScore)} / 202，交接质量 ${fmt(t.handoffScore)} / 20。制度行政正式方向档：制度建设${a}、官僚治理${b1}、反馈约束${b2}；C1—C3记录统治窗口内状态，C4净调整 ${signedFmt(t.c4)}。`;
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
      .second-item-scale-note{display:block;margin-top:4px;font-size:11px;color:var(--green);font-weight:600}.second-item-group-intro{margin:0 0 14px;padding:11px 13px;border-left:3px solid var(--gold);background:#f1eee6;font-size:13px;line-height:1.75}.second-item-c4-note{margin:0 0 12px;padding:9px 11px;border-left:3px solid var(--green);background:#f1eee6;font-size:13px;line-height:1.75}
      .second-item-card-breakdown,.second-item-inline-rank{font-size:12px;color:var(--muted);line-height:1.65}.second-item-inline-rank{display:block;margin-top:3px;color:var(--green)}
      .net-formal-basis-raw{margin-top:12px;border-top:1px solid var(--line)}.net-formal-basis-raw>.net-formal-basis-content{padding-top:8px}.second-item-pool-note{margin-top:8px;font-size:12px;line-height:1.65;color:var(--muted)}
      .net-major-card.second-item-card .big{font-size:30px}@media(max-width:700px){.second-item-total-grid{grid-template-columns:1fr}}
    `;document.head.append(style);
  }
  function addGroupIntro(section,key,text){if(!section)return;let p=section.querySelector(`:scope > [data-second-intro="${key}"]`);if(!p){p=document.createElement("p");p.className="second-item-group-intro";p.dataset.secondIntro=key;const h=section.querySelector(":scope > h2");if(h?.nextSibling)section.insertBefore(p,h.nextSibling);else section.append(p);}setNodeText(p,text);}
  function metricDetail(section,labels){const wanted=new Set(Array.isArray(labels)?labels:[labels]);return Array.from(section?.querySelectorAll(":scope > .net-metric-detail")||[]).find(d=>wanted.has(d.dataset.secondSourceLabel||d.querySelector(":scope > summary strong")?.textContent.trim()))||null;}
  function markSourceLabel(detail,label){if(detail&&!detail.dataset.secondSourceLabel)detail.dataset.secondSourceLabel=label;}
  function setMetricDisplay(detail,valueText,noteText,titleText=""){if(!detail)return;const s=detail.querySelector(":scope > summary"),strong=s?.querySelector("strong"),value=s?.querySelector(":scope > b"),span=s?.querySelector(":scope > span");if(titleText)setNodeText(strong,titleText);setNodeText(value,valueText);if(!span)return;let note=span.querySelector(":scope > .second-item-scale-note");if(!note){note=document.createElement("small");note.className="second-item-scale-note";span.append(note);}setNodeText(note,noteText);}
  function joinNote(...parts){return parts.filter(Boolean).join("｜");}

  function ensureLandingCard(record,t){
    if(!location.hash.match(/^#net\/[^/?#]+\/(?:all)?$/))return;
    const card=Array.from(document.querySelectorAll(".net-major-card")).find(x=>x.getAttribute("href")?.includes("/second"));if(!card)return;
    card.classList.add("second-item-card");setNodeText(card.querySelector(".big"),t.totalScore==null?"—":`${fmt(t.totalScore)} / 387`);
    const desc=Array.from(card.querySelectorAll(":scope > p")).find(p=>!p.classList.contains("sources")&&!p.classList.contains("second-item-card-breakdown"));setNodeText(desc,"先看治理机器怎么运转、本人统治窗口内社会处于什么状态，再看离场时如何完成终局交班。");
    if([t.methodScore,t.resultScore,t.handoffScore].some(v=>v==null))return;
    let p=card.querySelector(":scope > .second-item-card-breakdown");if(!p){p=document.createElement("p");p.className="second-item-card-breakdown";const sources=card.querySelector(":scope > p.sources");card.insertBefore(p,sources||null);}const rank=rankText(t);setNodeText(p,`${rank?`${rank} · `:""}治理手段 ${fmt(t.methodScore)}/165 · 治理结果 ${fmt(t.resultScore)}/202 · 交接质量 ${fmt(t.handoffScore)}/20`);
  }
  function ensureSecondSummary(record,t){
    if(!location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/))return;const container=document.getElementById("net-major-body");if(!container||[t.methodScore,t.resultScore,t.handoffScore,t.totalScore].some(v=>v==null))return;
    const rank=rankText(t);let summary=container.querySelector(":scope > .second-item-reader-summary");if(!summary){summary=document.createElement("section");summary.className="second-item-reader-summary";container.insertBefore(summary,container.firstChild);}
    const key=[t.methodScore,t.resultScore,t.handoffScore,t.totalScore,t.c4,rank,methodBand(t.method.get("A制度建设")),methodBand(t.method.get("B1官僚治理")),methodBand(t.method.get("B2反馈与约束"))].join("|");
    if(summary.dataset.secondRenderKey!==key){summary.innerHTML=`<h2>先看这个人的治国结论</h2><p class="second-item-person-conclusion">${personConclusion(t)}</p>${rank?`<span class="second-item-rank">${rank}</span>`:""}<div class="second-item-total-grid"><div>治理手段<b>${fmt(t.methodScore)} / 165</b><small>A/B1先形成120分块，B2再折算45分</small></div><div>治理结果<b>${fmt(t.resultScore)} / 202</b><small>C1—C3状态账 + C4恢复、恶化与额外成本净调整</small></div><div>交接质量<b>${fmt(t.handoffScore)} / 20</b><small>离场前后的行政承接与继承稳定</small></div></div><div class="second-item-equation">${fmt(t.methodScore)} + ${fmt(t.resultScore)} + ${fmt(t.handoffScore)} = <strong>第二项 ${fmt(t.totalScore)} / 387</strong></div><p class="subline">本项量表理论范围为 -27.5～387。0不是及格线、历史平均或“中性线”；公开名次只在当前主池中已完成第二项结算的人物之间比较。</p>`;summary.dataset.secondRenderKey=key;}
    const page=document.querySelector(".net-detail-page"),intro=page?.querySelector(":scope > .panel");if(intro){const main=Array.from(intro.querySelectorAll(":scope > p")).find(p=>!p.classList.contains("subline")),score=intro.querySelector(":scope > p.subline");setNodeText(main,"治国净收益分三层看：治理机器如何运转、本人统治窗口内社会实际处于什么状态、本人离场前后是否完成稳定交班。状态本身不等于全部由本人造成。");setNodeText(score,`第二项总分：${fmt(t.totalScore)} / 387${rank?`；${rank}`:""}。下面先看正式结论，再展开到各指标。`);}
  }

  function ensureMethodGroup(t){
    const section=document.getElementById("net-group-method");if(!section)return;setNodeText(section.querySelector(":scope > h2"),"治理手段 · 制度与行政");addGroupIntro(section,"method",`这一组看国家机器怎么运转。A制度建设与B1官僚治理各用0—100方向指数，先共同形成最高120分的AB计分块；B2反馈与约束用0—80方向指数，再折算为最高45分。三者不是同一满分，也不能直接相加；当前人物治理手段小计为 ${fmt(t.methodScore)} / 165。`);
    for(const label of ["A制度建设","B1官僚治理","B2反馈与约束"]){const item=t.method.get(label),detail=metricDetail(section,label);markSourceLabel(detail,label);if(!item||!detail)continue;setMetricDisplay(detail,`${fmt(item.value)} / ${METHOD_MAX[label]} 指数`,joinNote(`正式方向档：${methodBand(item)}`,boundaryExcerpt(item)));}
  }
  function ensureC4Note(detail,value){const body=detail?.querySelector(":scope > .net-metric-body");if(!body)return;let note=body.querySelector(":scope > .second-item-c4-note");if(!note){note=document.createElement("p");note.className="second-item-c4-note";body.insertBefore(note,body.firstChild);}if(value==null)setNodeText(note,"这是净调整项，不与C1—C3使用同一满分尺度；具体正负构成以下方正式裁决为准。");else if(value>0)setNodeText(note,"这是净调整项。正数表示恢复增量在扣除本人可归责恶化与额外民力、治理成本后仍有净加分；最终社会状态仍看C1—C3。");else if(value<0)setNodeText(note,"这是净调整项。负数表示本人可归责恶化和/或额外民力、治理成本超过恢复增量，形成净扣分；具体是哪一部分造成负值，以下方正式裁决为准。");else setNodeText(note,"本调整项为0只表示这里的净调整为0：可能没有新增可计变化，也可能相关恶化已经在C1—C3消费而不再重复扣。0不等于“没有问题”。");}
  function ensureFinanceGroup(t){
    const section=document.getElementById("net-group-finance");if(!section)return;setNodeText(section.querySelector(":scope > h2"),"治理结果 · 财政与民生");addGroupIntro(section,"finance",`C1—C3首先记录本人统治窗口内观察到的实际状态，不等于把全部好坏归给本人；接手基线、外生冲击以及本人造成或放大的变化，由正式裁决另行分账。三项满分分别为民生80、经济财政35、社会安全60，不能直接拿绝对数字比高低。C4另记恢复增量、本人可归责恶化与额外民力/治理成本的净调整。四项合计为 ${fmt(t.resultScore)} / 202。`);
    for(const label of ["C1民生","C2经济财政","C3社会安全"]){const item=t.finance.get(label),detail=metricDetail(section,label);markSourceLabel(detail,label);if(!item||!detail)continue;setMetricDisplay(detail,`${fmt(item.value)} / ${FINANCE_MAX[label]} 分`,joinNote(`状态分·满分${FINANCE_MAX[label]}`,stateMeta(item),"状态不等于本人全责",boundaryExcerpt(item)));}
    const item=t.finance.get("C4恢复与成本"),detail=metricDetail(section,["C4恢复与成本","C4恢复、恶化与额外成本调整"]);markSourceLabel(detail,"C4恢复与成本");if(item&&detail){setMetricDisplay(detail,`${signedFmt(item.value)} 分`,joinNote("净调整项","恢复 − 可归责恶化 − 额外成本",boundaryExcerpt(item)),"C4恢复、恶化与额外成本调整");ensureC4Note(detail,item.value);}
  }
  function ensureHandoffGroup(t){
    const section=document.getElementById("net-group-handoff");if(!section)return;setNodeText(section.querySelector(":scope > h2"),"交接质量 · 政权交接");const d1i=t.handoff.get("D1继任行政连续性"),d3i=t.handoff.get("D3政权交接稳定"),d1=finite(d1i?.value),d3=finite(d3i?.value),cap=finite(t.handoff.get("低侧封顶")?.value),score=t.handoffScore;
    let exp="D1、D3主要评价本人离场前后的终局交班：D1看旧国家机器有多少被接住，D3看继承过程是否稳定。任内更早发生过继承危机，不会自动把终局交接判低；关键看离场前是否真正修复并完成可运行的承接。";if([d1,d3,cap,score].every(v=>v!=null))exp=`行政连续性为 ${fmt(d1,0)} / 5级，交接稳定为 ${fmt(d3,0)} / 5级。两项主要评价本人离场前后的终局交班：D1看旧国家机器有多少被接住，D3看继承过程是否稳定；任内更早的继承危机若在离场前被真正修复，不会自动把终局交接判低。较弱一侧把本项最高分限制在 ${fmt(cap)}，最终交接得分 ${fmt(score)} / 20。`;addGroupIntro(section,"handoff",exp);
    const d1d=metricDetail(section,"D1继任行政连续性"),d3d=metricDetail(section,"D3政权交接稳定");markSourceLabel(d1d,"D1继任行政连续性");markSourceLabel(d3d,"D3政权交接稳定");setMetricDisplay(d1d,d1==null?"—":`${fmt(d1,0)} / 5 级`,joinNote("等级输入·行政承接",boundaryExcerpt(d1i)));setMetricDisplay(d3d,d3==null?"—":`${fmt(d3,0)} / 5 级`,joinNote("等级输入·终局继承",boundaryExcerpt(d3i)));
    for(const strong of section.querySelectorAll(".net-calculations .component strong"))if(strong.textContent.trim()==="低侧封顶")setNodeText(strong,"交接短板上限");for(const small of section.querySelectorAll(".net-calculations .component small"))setNodeText(small,small.textContent.replace(/低侧封顶/g,"交接短板上限"));
  }

  function formalBasisDetails(detail){return Array.from(detail?.querySelectorAll(":scope > .net-metric-body > details")||[]).find(block=>{const text=block.querySelector(":scope > summary")?.textContent.trim()||"";return block.classList.contains("net-formal-basis-raw")||text==="当前人物的完整裁决原文"||text==="正式裁决原文（未改写）";})||null;}
  function restoreFormalBasis(section,itemMap){
    if(!section)return;for(const [label,item] of itemMap.entries()){const raw=String(item?.reader_full_basis||"").trim(),summaryRaw=String(item?.reader_summary||"").trim();if(!raw||raw===summaryRaw)continue;const display=label==="C4恢复与成本"?"C4恢复、恶化与额外成本调整":label,detail=metricDetail(section,[label,display]);if(!detail)continue;markSourceLabel(detail,label);const body=detail.querySelector(":scope > .net-metric-body");if(!body)continue;let block=formalBasisDetails(detail);if(!block){block=document.createElement("details");const audit=body.querySelector(":scope > .net-audit-sources");body.insertBefore(block,audit||null);block.append(document.createElement("summary"));}block.classList.add("net-formal-basis-raw");const summary=block.querySelector(":scope > summary");setNodeText(summary,"正式裁决原文（未改写）");let content=block.querySelector(":scope > .net-formal-basis-content");if(!content){for(const child of Array.from(block.children))if(child!==summary)child.remove();content=document.createElement("div");content.className="net-formal-basis-content";block.append(content);}if(content.dataset.rawKey!==raw){content.innerHTML=typeof prose==="function"?prose(raw):`<p class="prose"></p>`;if(typeof prose!=="function")setNodeText(content.querySelector("p"),raw);content.dataset.rawKey=raw;}}
  }
  function restoreFormalBasisForRoute(record){const route=parsedNetRoute();if(!route||!record?.net?.component_details)return;const groups=route.major==="second"?["method","finance","handoff"]:route.major==="third"?["strategic","military"]:route.major==="fourth"?["civilization"]:[];for(const key of groups)restoreFormalBasis(document.getElementById(`net-group-${key}`),itemsFor(record,key));}
  function ensureAuditPoolNotes(t){
    if(!location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/))return;const current=t.pool?.total;for(const audit of document.querySelectorAll("#net-major-body .net-audit-sources")){let note=audit.querySelector(":scope > .second-item-pool-note");if(!note){note=document.createElement("p");note.className="second-item-pool-note";const sources=audit.querySelector(":scope > .sources");audit.insertBefore(note,sources||null);}setNodeText(note,`排名口径：当前公开名次只比较当前主池中已完成第二项结算的${current??"现有"}人。原第二项总表仍保留${HISTORICAL_SECOND_POOL}人历史快照，其中含${HISTORICAL_OUT_OF_CURRENT_POOL}条现已不在当前184人主池的旧记录，因此原文件内旧rank不等于当前公开名次。`);}
  }

  function humanizeText(text){return text.replace(/B1-distributed\/personnel M3/gi,"多责任官的人事配置强机制链").replace(/distributed\/personnel M3/gi,"多责任官的人事配置强机制链").replace(/central M2/gi,"中央有限机制链").replace(/混负M3/g,"较强、持续的混合偏负机制链").replace(/混合偏负M3/g,"较强、持续的混合偏负机制链").replace(/核心M3链/g,"较强、持续或跨阶段的核心机制链").replace(/正向M3/g,"较强、持续或跨阶段的正向机制链").replace(/正M3/g,"较强、持续或跨阶段的正向机制链").replace(/负向M3/g,"较强、持续或跨阶段的负向机制链").replace(/负M3/g,"较强、持续或跨阶段的负向机制链").replace(/M3链/g,"较强、持续或跨阶段的机制链").replace(/\bM3\b/g,"较强机制链").replace(/平衡M2/g,"影响大致相抵的有限机制链").replace(/正向M2/g,"明确但有限的正向机制链").replace(/正M2/g,"明确但有限的正向机制链").replace(/负向M2/g,"明确但有限的负向机制链").replace(/负M2/g,"明确但有限的负向机制链").replace(/M2链/g,"有限机制链").replace(/\bM2\b/g,"有限机制链").replace(/\bS_end\b/g,"终点状态").replace(/\bS0\b/g,"接手状态").replace(/\bG0\b/g,"最低档").replace(/\bG1\b/g,"较低档").replace(/\bG2\b/g,"中低档").replace(/\bG3\b/g,"中档").replace(/\bG4\b/g,"较高档").replace(/\bG5\b/g,"最高档").replace(/\bL([0-3])\b/g,(_,level)=>`低谷修正${level}级`).replace(/\bH([0-5])\b/g,(_,level)=>`交接第${level}级`).replace(/\bDA([0-3])\b/g,(_,level)=>`额外成本第${level}级`).replace(/\bexternal_constraint\b/gi,"外部反馈约束").replace(/\bmixed_positive\b/gi,"混合偏正").replace(/\bcentral\b/gi,"中央").replace(/\bdistributed\b/gi,"地方分布式").replace(/\bcanonical\b/gi,"规范").replace(/\bcore\b/gi,"核心").replace(/\bsupport\b/gi,"辅助").replace(/V2净值/g,"复核净值").replace(/责任路线=NONE/g,"未进入本人军事归责路线");}
  function humanizeInternalLanguage(){const root=document.getElementById("net-major-body");if(!root)return;for(const body of root.querySelectorAll(".net-metric-body")){const walker=document.createTreeWalker(body,NodeFilter.SHOW_TEXT),nodes=[];while(walker.nextNode())nodes.push(walker.currentNode);for(const node of nodes){const parent=node.parentElement;if(!parent||parent.closest(".net-formal-basis-raw")||parent.closest(".net-audit-sources")||parent.closest(".sources")||parent.closest("a"))continue;const next=humanizeText(node.nodeValue||"");if(next!==node.nodeValue)node.nodeValue=next;}}}

  function groupKindFromSummary(summary){const text=summary?.textContent.trim()||"";if(text.includes("制度与行政"))return"method";if(text.includes("财政与民生"))return"finance";if(text.includes("政权交接")||text.includes("交接质量"))return"handoff";return"";}
  function replaceCompactNote(span,text){if(!span||!text)return;for(const small of Array.from(span.querySelectorAll(":scope > small")))small.remove();const note=document.createElement("small");note.className="second-item-scale-note";note.textContent=text;span.append(note);}
  function setRowLabel(span,label){if(!span)return;const textNode=Array.from(span.childNodes).find(c=>c.nodeType===Node.TEXT_NODE);if(textNode)textNode.nodeValue=`${label} `;else span.insertBefore(document.createTextNode(`${label} `),span.firstChild);}
  function formatCompactGroup(root,record,kind){
    if(!root||!record?.net||!kind)return;const map=itemsFor(record,kind);for(const row of root.querySelectorAll(":scope .component")){const span=row.querySelector(":scope > span"),value=row.querySelector(":scope > b");if(!span||!value)continue;const label=directText(span)||span.querySelector("strong")?.textContent.trim()||"",item=map.get(label);
      if(kind==="method"&&item&&METHOD_MAX[label]){setNodeText(value,`${fmt(item.value)} / ${METHOD_MAX[label]} 指数`);replaceCompactNote(span,joinNote(`正式方向档：${methodBand(item)}`,boundaryExcerpt(item)));}
      else if(kind==="finance"&&item&&FINANCE_MAX[label]){setNodeText(value,`${fmt(item.value)} / ${FINANCE_MAX[label]} 分`);replaceCompactNote(span,joinNote(stateMeta(item),"状态不等于本人全责",boundaryExcerpt(item)));}
      else if(kind==="finance"&&item&&label==="C4恢复与成本"){setRowLabel(span,"C4恢复、恶化与额外成本调整");setNodeText(value,`${signedFmt(item.value)} 分`);replaceCompactNote(span,joinNote("净调整项","恢复 − 可归责恶化 − 额外成本",boundaryExcerpt(item)));}
      else if(kind==="handoff"&&item&&label==="D1继任行政连续性"){setNodeText(value,`${fmt(item.value,0)} / 5 级`);replaceCompactNote(span,joinNote("离场前后的行政承接",boundaryExcerpt(item)));}
      else if(kind==="handoff"&&item&&label==="D3政权交接稳定"){setNodeText(value,`${fmt(item.value,0)} / 5 级`);replaceCompactNote(span,joinNote("离场前后的终局继承",boundaryExcerpt(item)));}
      else if(kind==="handoff"&&label==="低侧封顶"){setRowLabel(span,"交接短板上限");replaceCompactNote(span,"交接短板决定本项最高可得分");}
      else if(kind==="handoff"&&label==="交接得分"){setNodeText(value,`${fmt(item?.value)} / 20 分`);replaceCompactNote(span,"D1与D3合成后的交接质量");}
      else if(kind==="handoff"&&label==="第二项合计"){setNodeText(value,`${fmt(item?.value)} / 387 分`);replaceCompactNote(span,"治理手段 + 治理结果 + 交接质量");}
    }
  }
  function enhanceCompactGroups(record){if(!record?.detail_loaded||!record?.net)return;for(const details of screenEl.querySelectorAll("details")){const kind=groupKindFromSummary(details.querySelector(":scope > summary"));if(kind)formatCompactGroup(details,record,kind);}}
  function enhancePersonOverview(record){if(!record?.detail_loaded||!record?.net||!location.hash.startsWith("#person/"))return;const panel=document.getElementById("person-outcome");if(!panel)return;const t=secondTotals(record);for(const row of panel.querySelectorAll(":scope > .component")){const span=row.querySelector("span");if(!span||!directText(span).startsWith("治国净收益"))continue;setNodeText(row.querySelector("b"),`${fmt(t.totalScore)} / 387`);let rank=span.querySelector(":scope > .second-item-inline-rank");if(!rank){rank=document.createElement("small");rank.className="second-item-inline-rank";span.append(rank);}setNodeText(rank,rankText(t));}enhanceCompactGroups(record);}
  function pendingSecondLabel(record){return record?.settlement_readiness==="PENDING_SECOND_ITEM_FORMAL_SETTLEMENT"?"待正式结算":"未入榜";}
  function enhanceCompare(records){
    if(records.length<2||records.some(r=>!r?.detail_loaded))return;const rows=Array.from(screenEl.querySelectorAll(".comparison tbody tr")),secondRow=rows.find(r=>r.cells?.[0]?.textContent.trim()==="治国净收益");if(secondRow){records.forEach((record,index)=>{const cell=secondRow.cells[index+1];if(!cell)return;if(!record?.net){setNodeText(cell,pendingSecondLabel(record));return;}const t=secondTotals(record),key=`${t.totalScore}|${rankText(t)}`;if(cell.dataset.secondItemKey===key)return;cell.innerHTML=`<b>${fmt(t.totalScore)} / 387</b>${rankText(t)?`<small class="second-item-inline-rank">${rankText(t)}</small>`:""}`;cell.dataset.secondItemKey=key;});}
    const structureRow=rows.find(r=>r.cells?.[0]?.textContent.trim()==="构成与依据");if(structureRow){records.forEach((record,index)=>{const cell=structureRow.cells[index+1];if(!cell)return;if(!record?.net){if(record?.settlement_readiness==="PENDING_SECOND_ITEM_FORMAL_SETTLEMENT")setNodeText(cell,"第二项正式结算待补；当前不进入净收益总榜。");return;}for(const details of cell.querySelectorAll("details")){const kind=groupKindFromSummary(details.querySelector(":scope > summary"));if(kind)formatCompactGroup(details,record,kind);}});}
  }

  function enhanceNetRoute(record){
    if(!record?.net)return;restoreFormalBasisForRoute(record);const route=parsedNetRoute();if(!route)return;const t=secondTotals(record);
    if(route.major==="all"){ensureLandingCard(record,t);return;}
    if(route.major!=="second")return;
    ensureSecondSummary(record,t);ensureMethodGroup(t);ensureFinanceGroup(t);ensureHandoffGroup(t);ensureAuditPoolNotes(t);humanizeInternalLanguage();
  }
  function enhance(){ensureStyles();const netRecord=recordForNetRoute();if(netRecord)enhanceNetRoute(netRecord);const personRecord=recordForPersonRoute();if(personRecord)enhancePersonOverview(personRecord);const compareRecords=recordsForCompareRoute();if(compareRecords.length)enhanceCompare(compareRecords);}
  function schedule(){if(scheduled)return;scheduled=true;requestAnimationFrame(()=>{scheduled=false;enhance();});}
  new MutationObserver(schedule).observe(screenEl,{childList:true,subtree:true,characterData:true});window.addEventListener("hashchange",schedule);schedule();
})();
