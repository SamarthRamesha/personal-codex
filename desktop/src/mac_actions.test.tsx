import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import {MacActions,MacActionReview} from './MacActions';

describe('Mac action consent',()=>{
  it('shows the exact target as escaped text and requires a distinct confirmation',()=>{
    const html=renderToStaticMarkup(<MacActionReview preview={{id:'one',kind:'open_document',label:'<script>untrusted</script>',target:'/tmp/<img>.txt',expires_in_seconds:120}}
      busy={false} confirm={()=>{throw new Error('render must not execute');}} cancel={()=>{}}/>);
    expect(html).toContain('Confirm and open');expect(html).toContain('Cancel action');
    expect(html).toContain('/tmp/&lt;img&gt;.txt');expect(html).not.toContain('<script>');
    expect(html).toContain('used once');
  });
  it('offers local selection without a backend or pre-authorized action',()=>{
    const html=renderToStaticMarkup(<MacActions close={()=>{}}/>);
    expect(html).toContain('work without a backend connection');
    expect(html).toContain('Choose document to open');expect(html).toContain('Search installed applications');
    expect(html).not.toContain('Confirm and open');
  });
});
