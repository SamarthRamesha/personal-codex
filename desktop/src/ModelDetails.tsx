import type { ModelDescriptor } from './api';

export function ModelDetails({model,context}:{model?:ModelDescriptor;context:number|null}){
  if(!model)return null;
  const size=typeof model.size_bytes==='number'&&Number.isFinite(model.size_bytes)&&model.size_bytes>=0
    ?`${(model.size_bytes/1e9).toFixed(2)} GB`:'Unknown';
  return <div className="model-observations" aria-label="Selected model details">
    <h4>{model.name}</h4>
    <dl>
      <div><dt>Quantization</dt><dd>{model.quantization||'Unknown'}</dd></div>
      <div><dt>Stored size</dt><dd>{size}</dd></div>
      <div><dt>Context setting</dt><dd>{context!=null&&context>0?`${context.toLocaleString()} tokens`:'Provider default'}</dd></div>
      <div><dt>Native tool support</dt><dd>{model.tool_calls===true?'Verified':model.tool_calls===false?'Unsupported':'Not verified'}</dd></div>
    </dl>
    <p className="muted small">Size is reported storage use. Memory fit has not been measured.</p>
  </div>;
}
