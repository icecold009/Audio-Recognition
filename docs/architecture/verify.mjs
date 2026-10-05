import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';
const dir=path.dirname(fileURLToPath(import.meta.url)),repo=path.resolve(dir,'../..');
const remoteRepository='icecold009/Audio-Recognition';
const read=f=>fs.readFileSync(path.join(repo,f),'utf8').replace(/\r\n/g,'\n');
const fail=message=>{throw new Error(message);};
const graphBlock=s=>s.match(/```mermaid\n([\s\S]*?)\n```/)?.[1]?.trim();
function validate(c){
 const snapshot=c.coverage.match(/Snapshot: `([a-f0-9]{40})`/)?.[1];
 if(snapshot!==c.snapshot)fail('Snapshot mismatch');
 const listed=[...c.coverage.split('## File accounting')[1]?.matchAll(/^- `([^`]+)`$/gm)??[]].map(m=>m[1]);
 if(new Set(listed).size!==listed.length)fail('Duplicate inventory path');
 if(JSON.stringify([...listed].sort())!==JSON.stringify([...c.paths].sort()))fail('Missing or extra inventory path');
 for(const f of listed)if(!c.exists(f))fail('Snapshot file missing: '+f);
 if(graphBlock(c.caseStudy)!==c.overview.trim())fail('Case-study Mermaid differs from overview');
 const rootBlock=c.rootReadme.split('## Source-reviewed architecture overview')[1];
 if(!rootBlock||graphBlock(rootBlock)!==c.overview.trim().replaceAll('"../../','"'))fail('Root Mermaid differs from overview');
 if(graphBlock(c.coverage)!==c.detail.trim())fail('Coverage Mermaid differs from detail');
 let links=0,edges=0;
 for(const [file,text] of [['docs/architecture/overview.mmd',c.overview],['docs/architecture/detail.mmd',c.detail]]){
  const nodes=[...text.matchAll(/^\s+(\w+)\[/gm)].map(m=>m[1]);
  if(new Set(nodes).size!==nodes.length)fail('Duplicate diagram node');
  for(const m of text.matchAll(/^\s+(\w+)\s+(?:-->|<-->|-\.(?:->|[^\n]*?\.->))(?:\|[^|]*\|)?\s*(\w+)/gm)){
   if(!nodes.includes(m[1])||!nodes.includes(m[2]))fail('Dangling diagram endpoint');edges++;
  }
  for(const m of text.matchAll(/click \w+ "([^\"]+)"/g)){
   const target=m[1],remote=target.match(/^https:\/\/github\.com\/([^/]+\/[^/]+)\/(?:blob|tree)\/([^/]+)\/(.+)$/);
   if(remote){if(remote[1]!==remoteRepository||remote[2]!==c.snapshot||!c.exists(decodeURIComponent(remote[3])))fail('Unpinned or missing source target');}
   else if(/^https?:/.test(target))fail('Unrecognized diagram source URL');
   else if(!c.exists(path.relative(repo,path.resolve(repo,path.dirname(file),decodeURIComponent(target)))))fail('Missing diagram link');
   links++;
  }
 }
 for(const [file,text] of [['docs/architecture/README.md',c.caseStudy],['docs/architecture/coverage.md',c.coverage],['docs/architecture/verification.md',c.verification]]){
  for(const m of text.matchAll(/\]\(([^)]+)\)/g)){
   if(/^https?:|^#/.test(m[1]))continue;
   const local=path.relative(repo,path.resolve(repo,path.dirname(file),decodeURIComponent(m[1])));
   if(!c.exists(local))fail('Missing documentation link');links++;
  }
 }
 const key=s=>s.match(/^\s*(\w+)/)?.[1]+(s.includes('<-->')?'<-->':'->')+s.match(/(\w+)\s*$/)?.[1];
 const expected=[...c.overview.split('\n').filter(s=>/^\s+\w+\s+(?:-->|<-->|-\.)/.test(s)).map(s=>'O:'+key(s)),...c.detail.split('\n').filter(s=>/^\s+\w+\s+(?:-->|<-->|-\.)/.test(s)).map(s=>'D:'+key(s))].sort();
 const sources=new Map([...c.verification.matchAll(/^- \[(S\d+)\]\(\.\.\/\.\.\/([^)]+)\)$/gm)].map(m=>[m[1],m[2]]));
 const rows=[...c.verification.matchAll(/^\| ([OD]) ([^|]+) \| ([^|]+) \|/gm)];
 if(JSON.stringify(rows.map(m=>m[1]+':'+key(m[2])).sort())!==JSON.stringify(expected))fail('Source map misses or duplicates an arrow');
 for(const row of rows){
  const ranges=[...row[3].matchAll(/\b(S\d+):(\d+)-(\d+)/g)];
  if(!ranges.length)fail('Missing source range');
  for(const range of ranges){
   const file=sources.get(range[1]);if(!file||!c.paths.includes(file))fail('Unknown source key');
   if(/(?:^|\/)(?:\.env|secrets|credentials)(?:\.|\/|$)|\.(?:pem|key|db|sqlite)$/i.test(file))fail('Sensitive source range refused');
   if(Number(range[2])<1||Number(range[3])<Number(range[2])||Number(range[3])>c.sourceLines(file))fail('Invalid source range');
  }
 }
 return {snapshot,inventoryPaths:listed.length,links,edges,sourceMappedArrows:rows.length};
}
try{
 const coverage=read('docs/architecture/coverage.md'),snapshot=coverage.match(/Snapshot: `([a-f0-9]{40})`/)?.[1];
 if(!snapshot)fail('Missing full snapshot commit');
 const paths=execFileSync('git',['-c',`safe.directory=${repo.replaceAll('\\','/')}`,'-C',repo,'ls-tree','-rz','--name-only',snapshot],{encoding:'utf8',stdio:['ignore','pipe','pipe']}).split('\0').filter(Boolean);
 const exists=f=>{const full=path.resolve(repo,f);return full.startsWith(repo+path.sep)&&fs.existsSync(full);};
 const lineCache=new Map();
 const sourceLines=file=>{if(!lineCache.has(file)){const content=execFileSync('git',['-c',`safe.directory=${repo}`,'-C',repo,'show',`${snapshot}:${file}`],{encoding:'utf8',maxBuffer:2*1024*1024,stdio:['ignore','pipe','pipe']});lineCache.set(file,content.split(/\r?\n/).length);}return lineCache.get(file);};
 const c={snapshot,paths,coverage,overview:read('docs/architecture/overview.mmd'),detail:read('docs/architecture/detail.mmd'),caseStudy:read('docs/architecture/README.md'),rootReadme:read('README.md'),verification:read('docs/architecture/verification.md'),exists,sourceLines};
 const result=validate(c);
 let negativeChecks=0;
 if(process.argv.includes('--self-test')){
  const brokenDetail=c.detail+'\n  SUPPORT --> MISSING_NODE\n';
  const mutants=[
   [{...c,paths:c.paths.slice(1)},'Missing or extra inventory path'],
   [{...c,coverage:c.coverage+'\n- `'+c.paths[0]+'`\n'},'Duplicate inventory path'],
   [{...c,exists:f=>f!==c.paths[0]&&exists(f)},'Snapshot file missing:'],
   [{...c,detail:brokenDetail,coverage:c.coverage.replace(graphBlock(c.coverage),brokenDetail.trim())},'Dangling diagram endpoint'],
   [{...c,rootReadme:c.rootReadme.replace('## Source-reviewed architecture overview','## Removed architecture overview')},'Root Mermaid differs from overview'],
   [{...c,caseStudy:c.caseStudy+'\n[broken](missing-documentation-link.invalid)\n'},'Missing documentation link'],
   [{...c,coverage:c.coverage.replace(c.snapshot,'0'.repeat(40))},'Snapshot mismatch'],
   [{...c,verification:c.verification.replace(/^\| O I --> W \|[^\n]+\n/m,'')},'Source map misses or duplicates an arrow'],
   [{...c,verification:c.verification.replace(/S\d+:(\d+)-/,'S999:$1-')},'Unknown source key'],
   [{...c,verification:c.verification.replace(/S\d+:\d+-/,'S1:0-')},'Invalid source range'],
  ];
  for(const [m,expected] of mutants){let reason='';try{validate(m);}catch(error){reason=error.message;}if(!reason.startsWith(expected))fail('Negative fixture did not fail at its intended check: '+expected);negativeChecks++;}
 }
 console.log(JSON.stringify({...result,negativeChecks,scope:'read-only documentation structure; not semantic, runtime, hosted or renderer proof'}));
}catch(error){console.error('Architecture verification failed: '+error.message);process.exitCode=1;}
