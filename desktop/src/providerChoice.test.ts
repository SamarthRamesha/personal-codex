import {describe,expect,it} from 'vitest';
import {providerForModel,usableProviders} from './providerChoice';
import type {Provider} from './api';

const provider=(id:string,model:string,extra:Partial<Provider>={}):Provider=>
  ({id,kind:'ollama',endpoint:'http://127.0.0.1:11434',model,cloud_allowed:false,enabled:true,...extra});

describe('provider choice',()=>{
  it('selects the provider that owns the chosen offline model',()=>{
    const providers=[provider('a','qwen3.5:9b'),provider('b','qwen2.5-coder:14b')];
    expect(providerForModel(providers,'qwen2.5-coder:14b')?.id).toBe('b');
    expect(providerForModel(providers,'qwen3.5:9b')?.id).toBe('a');
  });

  it('ignores disabled, cloud and gateway providers and an empty model',()=>{
    const providers=[provider('cloud','x',{cloud_allowed:true}),provider('off','y',{enabled:false}),
      provider('gate','z',{kind:'respan-gateway'})];
    expect(usableProviders(providers)).toEqual([]);
    expect(providerForModel(providers,'x')).toBeUndefined();
    expect(providerForModel(providers,'')).toBeUndefined();
  });
});
