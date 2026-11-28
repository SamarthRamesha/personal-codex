import {describe,it,expect} from 'vitest';
import {previewActive,previewRequest} from './previewReview';
import type {PreviewJob} from './previewReview';
const job={id:'preview-1',digest:'exact',status:'proposed',expires_at:200} as PreviewJob;
describe('managed preview confirmation',()=>{
  it('binds the exact reviewed proposal without accepting a command or URL',()=>expect(previewRequest(job,true,100)).toEqual({id:'preview-1',digest:'exact',confirm:true}));
  it('refuses missing confirmation, expiry and spent starts',()=>{
    expect(()=>previewRequest(job,false,100)).toThrow();expect(()=>previewRequest(job,true,201)).toThrow();
    expect(()=>previewRequest({...job,status:'running'},true,100)).toThrow();
  });
  it('only active processes offer stop',()=>{
    expect(previewActive({...job,status:'starting'})).toBe(true);expect(previewActive({...job,status:'running'})).toBe(true);
    for(const status of ['proposed','stopped','failed','exited','interrupted','expired'])expect(previewActive({...job,status})).toBe(false);
  });
});
