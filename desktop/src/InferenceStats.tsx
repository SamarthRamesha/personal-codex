import type { InferenceMetrics } from './api';

export function InferenceStats({metrics}:{metrics?:InferenceMetrics}){
  if(!metrics)return null;
  const valid=(n:unknown):n is number=>typeof n==='number'&&Number.isFinite(n)&&n>=0;
  const milliseconds=(n:unknown)=>valid(n)?`${(n/1000).toFixed(2)} s`:'Unavailable';
  const usage=metrics.provider_reported||{};
  return <dl className="inference-stats" aria-label="Model call measurements">
    <div><dt>Call time</dt><dd>{milliseconds(metrics.client_duration_ms)}</dd></div>
    <div><dt>First text</dt><dd>{milliseconds(metrics.first_text_ms)}</dd></div>
    <div><dt>Input / output tokens</dt><dd>{valid(usage.input_tokens)?usage.input_tokens:'Unknown'} / {valid(usage.output_tokens)?usage.output_tokens:'Unknown'}</dd></div>
    <div><dt>Provider-reported rate</dt><dd>{valid(usage.tokens_per_second)?`${usage.tokens_per_second.toFixed(2)} tokens/s`:'Unavailable'}</dd></div>
  </dl>;
}
