import {renderToStaticMarkup} from 'react-dom/server';
import {describe,expect,it} from 'vitest';
import {InferenceStats} from './InferenceStats';
import {ModelDetails} from './ModelDetails';
import type {ModelDescriptor} from './api';

describe('inference observations',()=>{
  it('keeps missing counts and first-text time unknown instead of displaying zero',()=>{
    const html=renderToStaticMarkup(<InferenceStats metrics={{client_duration_ms:1250,first_text_ms:null,provider_reported:{}}}/>);
    expect(html).toContain('1.25 s');
    expect(html).toContain('Unknown / Unknown');
    expect(html).not.toContain('0.00 s');
    expect(html).not.toContain('0.00 tokens/s');
  });
  it('remains compatible with backends that do not provide observations',()=>{
    expect(renderToStaticMarkup(<InferenceStats/>)).toBe('');
    expect(renderToStaticMarkup(<ModelDetails context={null}/>)).toBe('');
  });
  it('separates configured context and stored size from model capability claims',()=>{
    const model:ModelDescriptor={name:'fixture:9b',digest:null,size_bytes:2e9,format:'gguf',family:'fixture',
      parameter_size:'9B',quantization:'Q4_K_M',context_length:null,tool_calls:null,vision:null,
      hardware_fit:'unmeasured',metadata_source:'ollama-tags'};
    const html=renderToStaticMarkup(<ModelDetails model={model} context={8192}/>);
    expect(html).toContain('Context setting');
    expect(html).toContain('8,192 tokens');
    expect(html).toContain('2.00 GB');
    expect(html).toContain('Not verified');
    expect(html).toContain('Memory fit has not been measured');
  });
});
