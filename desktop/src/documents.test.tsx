import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { DocumentResults, ProjectDocuments } from './ProjectDocuments';
import type { DocumentHit } from './ProjectDocuments';

describe('project document provenance',()=>{
  const hit:DocumentHit={attachment_id:'synthetic',name:'design.txt',mechanism:'local extraction',source_hash:'a'.repeat(64),chunk:2,start_char:1600,end_char:2500,excerpt:'<script>untrusted()</script>',trust:'untrusted-reference'};
  it('renders source identity and untrusted text without interpreting HTML',()=>{
    const html=renderToStaticMarkup(<DocumentResults hits={[hit]}/>);
    expect(html).toContain('design.txt');expect(html).toContain('Excerpt 3');expect(html).toContain('1600');
    expect(html).toContain('aaaaaaaaaaaa');expect(html).toContain('Untrusted reference');
    expect(html).toContain('&lt;script&gt;');expect(html).not.toContain('<script>');
  });
  it('shows opt-in selection controls before documents can be added',()=>{
    const html=renderToStaticMarkup(<ProjectDocuments projectId="synthetic" attachments={[]} onImport={async()=>{}}/>);
    expect(html).toContain('Choose an imported document');expect(html).toContain('Add to search');
    expect(html).toContain('disabled');expect(html).not.toContain('Verified memory');
  });
});
