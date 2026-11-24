/** Which provider owns a model, so the model selector and the provider selector agree.
 *
 * Offline mode seeds one provider row per allowed local model, and the backend refuses a model the
 * conversation's provider does not own ("Switch models by selecting the corresponding offline
 * Ollama provider"). The composer offered both controls, so a model could be selected that could
 * never be sent. Selecting the owning provider keeps the two selects consistent.
 */
import type { Provider } from './api';

export function usableProviders(providers: Provider[]): Provider[] {
  return providers.filter(provider => provider.enabled && !provider.cloud_allowed && provider.kind !== 'respan-gateway');
}

export function providerForModel(providers: Provider[], model: string): Provider | undefined {
  if (!model) return undefined;
  return usableProviders(providers).find(provider => provider.model === model);
}
