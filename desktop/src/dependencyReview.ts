export type DependencyJob={id:string;digest:string;status:string;output:string;expires_at:number;proposal:{root:string;command:string[];hashes:Record<string,string>;packages:{path:string;version:string;url:string;integrity:string}[];network:{origin:string;max_download_bytes:number};writes:string[];scripts:string}};
export function canInstall(job:DependencyJob|null,confirmed:boolean,networkConfirmed:boolean,now=Date.now()/1000){return !!job&&job.status==='proposed'&&job.expires_at>now&&confirmed&&networkConfirmed;}
export function installationRequest(job:DependencyJob,confirmed:boolean,networkConfirmed:boolean,now=Date.now()/1000){
  if(!canInstall(job,confirmed,networkConfirmed,now))throw new Error('Review and confirm the current installation and downloads.');
  return {id:job.id,digest:job.digest,confirm:true,confirm_network:true};
}
