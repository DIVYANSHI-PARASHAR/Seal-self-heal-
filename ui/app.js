(function(){
"use strict";
const $ = selector => document.querySelector(selector);
const question = $("#question"), suggestions = $("#suggestions"), runButton = $("[data-run-button]");
const examples = [
  "How many available units are in the East warehouse?",
  "How many available units are in the West warehouse?",
  "What are the available units in each warehouse?"
];
let activeSuggestion = -1, visibleSuggestions = [], selectedRun = null, currentPage = 0;
function el(tag, className, content) {
  const node = document.createElement(tag);
  if(className) node.className = className;
  if(content !== undefined && content !== null) node.textContent = String(content);
  return node;
}
function set(selector, value){ $(selector).textContent = value === undefined || value === null || value === "" ? "—" : String(value); }
function announce(message){ $("[data-announcement]").textContent = message; }
async function request(path, options){
  const response = await fetch(path, options), body = await response.json().catch(() => ({}));
  if(!response.ok) throw new Error(body.error || "Request failed");
  return body;
}
function outcomeName(outcome){ return outcome === "answered" ? "Answered" : outcome === "unsupported" ? "Capability gap" : outcome === "error" ? "Error" : outcome || "Recorded"; }
function date(value){ return value ? new Date(value).toLocaleString() : "—"; }
function closeSuggestions(){
  suggestions.hidden = true; question.setAttribute("aria-expanded","false");
  question.removeAttribute("aria-activedescendant"); activeSuggestion = -1;
}
function paintActive(){
  [...suggestions.querySelectorAll('[role="option"]')].forEach((node,index) => node.setAttribute("aria-selected",String(index === activeSuggestion)));
  if(activeSuggestion >= 0) question.setAttribute("aria-activedescendant","suggestion-"+activeSuggestion);
  else question.removeAttribute("aria-activedescendant");
}
function openSuggestions(){
  const query = question.value.trim().toLowerCase();
  visibleSuggestions = examples.filter(item => !query || item.toLowerCase().includes(query));
  suggestions.replaceChildren(el("div","suggestion-label","Suggested questions"));
  visibleSuggestions.forEach((item,index) => {
    const option = el("button","suggestion",item);
    option.type = "button"; option.id = "suggestion-"+index;
    option.setAttribute("role","option"); option.setAttribute("aria-selected","false");
    option.addEventListener("mousedown",event => event.preventDefault());
    option.addEventListener("click",() => chooseSuggestion(index));
    suggestions.append(option);
  });
  if(!visibleSuggestions.length) suggestions.append(el("div","empty-state","No matching suggestions. You can ask your own question."));
  suggestions.append(el("div","suggestion-help","↑ ↓ to navigate · Enter to select · Esc to close"));
  suggestions.hidden = false; question.setAttribute("aria-expanded","true");
  activeSuggestion = -1;
}
function chooseSuggestion(index){
  if(!visibleSuggestions[index]) return;
  question.value = visibleSuggestions[index]; question.setCustomValidity("");
  closeSuggestions(); question.focus(); announce("Suggested question selected");
}
question.addEventListener("focus",openSuggestions);
question.addEventListener("input",()=>{ question.setCustomValidity(""); openSuggestions(); });
question.addEventListener("keydown",event => {
  if(event.key === "Escape"){ if(!suggestions.hidden){event.preventDefault();closeSuggestions();} return; }
  if(event.key === "ArrowDown" || event.key === "ArrowUp"){
    event.preventDefault(); if(suggestions.hidden) openSuggestions();
    if(visibleSuggestions.length) activeSuggestion = (activeSuggestion + (event.key === "ArrowDown" ? 1 : -1) + visibleSuggestions.length) % visibleSuggestions.length;
    paintActive(); return;
  }
  if(event.key === "Enter" && !suggestions.hidden && activeSuggestion >= 0){ event.preventDefault(); chooseSuggestion(activeSuggestion); }
});
document.addEventListener("pointerdown",event => { if(!$("#analysis-form").contains(event.target)) closeSuggestions(); });
function disclosure(label, value){
  const details = el("details","disclosure"), summary = el("summary","",label), pre = el("pre","",JSON.stringify(value,null,2));
  details.append(summary,pre); return details;
}
function renderAtlas(run){
  const root = $("[data-atlas-content]"); root.replaceChildren(); currentPage=0;
  const atlas = run.evidence && run.evidence.atlas, measured = run.resources || {};
  const pageCount = atlas ? atlas.pages.length : Number(measured.table_pages || 0);
  set("[data-atlas-summary]",pageCount+" "+(pageCount === 1 ? "page" : "pages"));
  if(!atlas){
    root.append(el("p","empty-state",pageCount ? "This older run did not store its row snapshot." : "0 table pages read. No Atlas rows were read for this run.")); return;
  }
  const source = el("div","source-line");
  source.append(el("span","", "Collection: "),el("strong","",atlas.collection || "analyst_rows"),el("span","", "Source: "),el("strong","",atlas.source || (run.dataset && run.dataset.id) || "—"),el("span","",atlas.row_count+" rows actually read"));
  root.append(source);
  if(!atlas.pages.length){ root.append(el("p","empty-state","0 rows read. No Atlas table data was used.")); return; }
  const view = el("div"), pager = el("div","pager"); root.append(view,pager);
  function showPage(){
    view.replaceChildren(); pager.replaceChildren();
    const page = atlas.pages[currentPage], rows = page.rows || [], columns = atlas.columns || [];
    const wrap = el("div","table-wrap"), table = el("table"), head = el("thead"), headerRow = el("tr");
    columns.forEach(column => headerRow.append(el("th","",column)));
    head.append(headerRow); table.append(head);
    const tbody=el("tbody");
    rows.forEach(row => {const tr=el("tr"); columns.forEach(column => tr.append(el("td","",row[column] === undefined ? "—" : row[column]))); tbody.append(tr);});
    table.append(tbody); wrap.append(table); view.append(wrap);
    const prev=el("button","","← Previous"), next=el("button","","Next →");
    prev.type=next.type="button"; prev.disabled=currentPage===0; next.disabled=currentPage===atlas.pages.length-1;
    prev.addEventListener("click",()=>{currentPage--;showPage();});next.addEventListener("click",()=>{currentPage++;showPage();});
    pager.append(prev,el("span","","Page "+(currentPage+1)+" of "+atlas.pages.length+" · "+page.row_count+" rows"),next);
  }
  showPage(); root.append(disclosure("Raw data read during this run",atlas.pages));
}
function renderTools(run){
  const root=$("[data-tool-content]"); root.replaceChildren();
  let calls=run.evidence && run.evidence.tool_calls;
  let recovered=false;
  if(!calls && Array.isArray(run.spans) && (run.resources && run.resources.tool_calls)){
    calls=run.spans.filter(span=>span.name && span.name.startsWith("tool.")).map(span=>({
      name:span.name.slice(5), arguments:span.arguments, result:span.result_preview,
      duration_ms:span.duration_ms, error:span.error
    }));
    recovered=Boolean(calls.length);
  }
  set("[data-tools-summary]",(calls ? calls.length : (run.resources && run.resources.tool_calls) || 0)+" calls");
  if(!calls){root.append(el("p","empty-state",run.resources && run.resources.tool_calls ? "Tool details were not stored for this older run." : "0 tool calls recorded."));return;}
  if(!calls.length){root.append(el("p","empty-state","0 tool calls recorded. The analyst did not invoke a tool."));return;}
  if(recovered) root.append(el("p","muted","Recovered from the redacted LangSmith trace."));
  calls.forEach((call,index)=>{
    const details=el("details","tool-row"), summary=el("summary"), name=el("strong","",(index+1)+". "+call.name);
    summary.append(name,el("span","",call.duration_ms === null ? "Timing unavailable" : call.duration_ms+" ms"),el("span",call.error ? "trace-error" : "",call.error ? "Error" : "Completed"));
    const content=el("div","tool-detail");
    const args=el("div"), result=el("div"); args.append(el("label","","Arguments"),el("pre","",JSON.stringify(call.arguments,null,2)));
    result.append(el("label","","Result preview"),el("pre","",JSON.stringify(call.result || {error:call.error || "No result"},null,2)));
    content.append(args,result); details.append(summary,content); root.append(details);
  });
}
function renderTrace(run){
  const root=$("[data-trace-content]"); root.replaceChildren();
  const link=$("[data-trace-link]"), trace=run.trace || {};
  const safeUrl=typeof trace.url === "string" && /^https:\/\//.test(trace.url);
  link.hidden=!safeUrl; if(safeUrl) link.href=trace.url; else link.removeAttribute("href");
  if(!Array.isArray(run.spans)){
    root.append(el("p","empty-state",trace.status === "disabled" ? "Tracing was disabled for this run." : trace.status === "available" ? "Span metadata could not be loaded. Open the full trace." : "No verified trace spans are available."));return;
  }
  if(!run.spans.length){root.append(el("p","empty-state","No trace spans were returned."));return;}
  run.spans.forEach(span=>{
    const details=el("details","trace-row"), summary=el("summary");
    summary.append(el("strong","",span.name || span.type || "Span"),el("span","",span.type || "—"),el("span",span.status === "error" ? "trace-error" : "",span.status || "—"),el("span","",span.duration_ms === null ? "—" : span.duration_ms+" ms"));
    const meta=el("div","source-line");meta.append(el("span","","Model: "+(span.model || "—")),el("span","","Tokens: "+(span.tokens ?? "—")),el("span","","Started: "+date(span.start_time)));
    if(span.error) meta.append(el("span","trace-error",span.error));
    details.append(summary,meta);root.append(details);
  });
}
function renderGap(run){
  const panel=$("#evaluations"), root=$("[data-gap-content]"); panel.hidden=run.outcome !== "unsupported";root.replaceChildren();
  if(panel.hidden)return;
  const gap=run.gap || {cases:[],candidates:[],active_version:"—"};
  root.append(el("p","gap-note",(run.limitation_reason || "The analyst could not answer with the current capability.")+" Active version remains "+gap.active_version+"."));
  const caseLinks=el("div","case-links");
  (gap.cases || []).forEach(item=>{const link=el("a","","Evaluation case "+item.id);link.href=item.url;caseLinks.append(link);});
  if(caseLinks.children.length)root.append(caseLinks);
  if(!(gap.candidates || []).length){root.append(el("p","empty-state","No candidate test is recorded for this gap."));return;}
  gap.candidates.forEach(candidate=>{
    const row=el("div","candidate-row");
    row.append(el("strong","",candidate.id),el("span",candidate.status === "Rejected" ? "rejected" : "",candidate.status));
    const checks=el("div","checks");
    [["Correctness",candidate.correctness],["Regression",candidate.regression]].forEach(([label,value])=>checks.append(el("span",value,label+": "+value)));
    row.append(checks);
    if(candidate.diff_url){const link=el("a","","Candidate diff ↗");link.href=candidate.diff_url;row.append(link);}
    root.append(row);
    if(candidate.reasons && candidate.reasons.length)root.append(el("p","muted",candidate.reasons.join("; ")));
  });
}
function renderRun(run){
  selectedRun=run; closeSuggestions(); $("#run-details").hidden=false;
  set("[data-run-question]",run.question || "Run "+run.run_id);
  const badge=$("[data-outcome]"); badge.className="outcome-badge "+run.outcome; badge.textContent=outcomeName(run.outcome);
  set("[data-run-message]",run.message || (run.outcome === "unsupported" ? run.limitation_reason || "The analyst cannot answer this question with its current capabilities." : run.outcome === "answered" && run.answer ? JSON.stringify(run.answer) : run.error || "No answer was stored."));
  set("[data-run-id]",run.run_id);set("[data-version]",run.version && run.version.length > 22 ? run.version.slice(0,12)+"…" : run.version || "—");
  $("[data-version]").title=run.version || "";
  set("[data-duration]",run.resources && run.resources.elapsed_seconds !== undefined ? run.resources.elapsed_seconds+" s" : "—");
  const resources=run.resources || {};set("[data-resource-summary]",(resources.model_calls ?? 0)+" model · "+(resources.tool_calls ?? 0)+" tools · "+(resources.table_pages ?? 0)+" pages · "+(resources.total_tokens ?? 0)+" tokens");
  renderAtlas(run);renderTools(run);renderTrace(run);renderGap(run);
  announce(outcomeName(run.outcome)+" run loaded");$("#run-details").scrollIntoView({block:"start"});
}
function historyRow(run){
  const button=el("button","history-row");button.type="button";
  button.append(el("span","",run.question || run.run_id),el("span",run.outcome || "",outcomeName(run.outcome)),el("span","",run.version || "—"),el("span","",date(run.created_at)));
  button.addEventListener("click",async()=>{
    try{renderRun(await request("/api/runs/"+encodeURIComponent(run.run_id)));location.hash="run-details";}
    catch(error){announce(error.message);}
  });return button;
}
async function loadHistory(){
  const list=$("[data-history-list]");list.replaceChildren();
  try{const data=await request("/api/runs?limit=20");if(!data.runs.length)list.append(el("p","empty-state","No completed runs yet."));data.runs.forEach(run=>list.append(historyRow(run)));}
  catch(error){list.append(el("p","empty-state",error.message));}
}
$("#analysis-form").addEventListener("submit",async event=>{
  event.preventDefault();closeSuggestions();if(runButton.disabled)return;
  const original=runButton.innerHTML;runButton.disabled=true;runButton.setAttribute("aria-busy","true");runButton.textContent="Running analysis…";announce("Analysis in progress");
  try{
    const run=await request("/api/runs",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question:question.value})});
    const full=await request("/api/runs/"+encodeURIComponent(run.run_id)).catch(()=>run);
    renderRun(full);loadHistory();
  }catch(error){question.setCustomValidity(error.message);question.reportValidity();announce(error.message);}
  finally{runButton.disabled=false;runButton.removeAttribute("aria-busy");runButton.innerHTML=original;}
});
$("[data-copy-run-id]").addEventListener("click",async()=>{if(!selectedRun)return;try{await navigator.clipboard.writeText(selectedRun.run_id);announce("Run ID copied");}catch{announce("Could not copy run ID");}});
request("/api/health").then(data=>{set("[data-atlas-status]",data.atlas === "connected" ? "Atlas connected" : "Atlas unavailable");set("[data-active-version]",data.active_version);runButton.disabled=false;}).catch(error=>{set("[data-atlas-status]","Atlas unavailable");announce(error.message);});
loadHistory();
})();
