import {describe,it,expect} from 'vitest';
import {canInstall,installationRequest} from './dependencyReview';
import type {DependencyJob} from './dependencyReview';
const job={id:'install-1',digest:'exact-digest',status:'proposed',expires_at:200} as DependencyJob;
describe('reviewed dependency execution',()=>{
  it('requires independent installation and network confirmation',()=>{
    expect(canInstall(job,true,false,100)).toBe(false);expect(canInstall(job,false,true,100)).toBe(false);
    expect(()=>installationRequest(job,false,false,100)).toThrow();
  });
  it('binds only the displayed id and digest without command authority',()=>{
    expect(installationRequest(job,true,true,100)).toEqual({id:'install-1',digest:'exact-digest',confirm:true,confirm_network:true});
  });
  it('refuses expired, executed and interrupted proposals',()=>{
    expect(canInstall(job,true,true,201)).toBe(false);
    for(const status of ['running','complete','failed','interrupted','cancelled'])expect(canInstall({...job,status},true,true,100)).toBe(false);
  });
});
