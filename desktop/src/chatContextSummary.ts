/** What the next chat turn can draw on, in one readable line and a few exact items.
 *
 * The backend report is descriptive: stored sources, the entries the prompt would include, and the
 * byte/char bounds. It never claims a model used them. The panel previously showed none of this, so
 * a project answer that cited a convention had no visible source.
 */
export type ChatContextReport = {
  conversation_id:string; executed:boolean;
  history:{stored:number;prompt_input:number;excluded:number;prompt_chars:number;
    limits:{messages:number;chars:number}};
  project:{id:string;name:string|null}|null;
  memory:{stored:number;included:number;included_bytes:number;
    limits:{entries:number;bytes:number};note?:string}|null;
  attachments:{stored:number;included:number;names:string[];
    limits:{entries:number;bytes:number}}|null;
  documents:{indexed_sources:number;search_available:boolean;
    limits:{reference_bytes:number}}|null;
  notes:string[];
};

export type ContextItem = {key:string;label:string};
export type ContextSummary = {headline:string;items:ContextItem[]};

const count=(n:number,singular:string,plural=`${singular}s`)=>`${n} ${n===1?singular:plural}`;

export function contextSummary(report:ChatContextReport|null|undefined):ContextSummary {
  if(!report) return {headline:'No context report yet.',items:[]};
  const history=report.history;
  const headline=`${history.prompt_input} of ${count(history.stored,'stored message')} in the next prompt · `
    +`${history.prompt_chars.toLocaleString()} of ${history.limits.chars.toLocaleString()} characters`;
  const items:ContextItem[]=[];
  if(history.excluded>0) items.push({key:'excluded',
    label:`${count(history.excluded,'turn')} excluded (stopped, failed or still arriving)`});
  if(report.memory) items.push({key:'memory',
    label:`${report.memory.included} of ${count(report.memory.stored,'stored memory entry','stored memory entries')} included `
      +`(${report.memory.limits.entries} entries / ${report.memory.limits.bytes} bytes cap)`});
  if(report.attachments) items.push({key:'attachments',
    label:`${report.attachments.included} of ${count(report.attachments.stored,'attachment')} included`
      +`${report.attachments.names.length?`: ${report.attachments.names.join(', ')}`:''}`});
  if(report.documents) items.push({key:'documents',
    label:`${count(report.documents.indexed_sources,'indexed document')}`
      +(report.documents.search_available?'':' · document search unavailable on this backend')});
  if(!report.project) items.push({key:'project',label:'No project selected for this conversation'});
  return {headline,items};
}
