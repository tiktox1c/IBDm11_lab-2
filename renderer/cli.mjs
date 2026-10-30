import { readFile } from 'node:fs/promises';
import readline from 'node:readline';
import { capture, checkChrome } from './capture.mjs';

// stdout is JSONL only. HTML console messages are JSON diagnostic records.
const send=event=>process.stdout.write(JSON.stringify(event)+'\n');
const controller=new AbortController();
const lines=readline.createInterface({input:process.stdin});
lines.on('line',line=>{if(line.trim()==='cancel') controller.abort();});
process.on('SIGTERM',()=>controller.abort());
try {
  const arg=process.argv[2];
  if(arg==='--check') send({type:'result',...await checkChrome(JSON.parse(process.argv[3] || '{}'))});
  else {
    const config=JSON.parse(await readFile(arg,'utf8'));
    const result=await capture(config,send,controller.signal);
    send({type:'result',...result});
  }
} catch(err) {
  send({type:'error',message:controller.signal.aborted?'Конвертация отменена.':err.message});
  process.exitCode=controller.signal.aborted?2:1;
} finally {lines.close();process.stdin.pause();}
