export type PreviewJob={id:string;digest:string;status:string;output:string;logs:string;expires_at:number;process_id?:number;proposal:{root:string;command:string[];url:string;port:number;network:string;files:string;lifetime_seconds:number}};
export function previewRequest(job:PreviewJob,confirmed:boolean,now=Date.now()/1000){
  if(!confirmed||job.status!=='proposed'||job.expires_at<=now)throw new Error('Review and confirm the current preview.');
  return {id:job.id,digest:job.digest,confirm:true};
}
export const previewActive=(job:PreviewJob|null)=>!!job&&['starting','running'].includes(job.status);
