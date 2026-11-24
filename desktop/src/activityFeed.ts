/** The task activity trail, bounded and time-stamped.
 *
 * The backend records an event per agent step with its `created_at`. The workspace used to show only
 * the last thirty messages with no time and no sign that earlier history existed, which reads as if
 * that were the whole trail. This module keeps the same bound but says how much is hidden, and
 * shows a time only when the backend actually recorded one.
 */
export type ActivityEvent = {agent:string;level:string;message:string;created_at?:number|null};
export type ActivityRow = {agent:string;level:string;message:string;at:string;time:number|null};

export function clockLabel(createdAt:number|undefined|null):string {
  if(typeof createdAt!=='number'||!Number.isFinite(createdAt)||createdAt<=0) return 'time unknown';
  return new Date(createdAt*1000).toLocaleTimeString(undefined,{hour:'2-digit',minute:'2-digit',second:'2-digit'});
}

/** Newest `limit` events in the order the backend recorded them, with the hidden count. */
export function activityRows(events:ActivityEvent[], limit=30):{rows:ActivityRow[]; hidden:number} {
  const bounded = Number.isFinite(limit)&&limit>0 ? Math.floor(limit) : 0;
  const shown = bounded ? events.slice(-bounded) : [];
  return {
    rows: shown.map(event=>({
      agent:event.agent, level:event.level, message:event.message,
      at:clockLabel(event.created_at), time:typeof event.created_at==='number'?event.created_at:null,
    })),
    hidden: events.length - shown.length,
  };
}

export function activityNote(hidden:number, total:number, limit=30):string {
  if(hidden<=0) return '';
  return `Showing the newest ${total-hidden} of ${total} recorded events (limit ${limit}).`;
}
