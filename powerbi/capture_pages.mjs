import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {connectToBridge,requireMethod} from '@microsoft/powerbi-desktop-bridge-cli';
import {setTimeout} from 'node:timers/promises';
const pid=process.argv[2];
if(!pid || !/^\d+$/.test(pid)) throw new Error('Provide the verified Taxi Desktop PID');
const root=path.dirname(fileURLToPath(import.meta.url));
const connection=await connectToBridge({pid,waitMs:10000});
try {
  requireMethod(connection.manifest,'report.snapshot.capture/v2');
  const pages=JSON.parse(fs.readFileSync(path.join(root,'Taxi.Report/definition/pages/pages.json'),'utf8')).pageOrder;
  for(const pageId of pages){
    let result;
    const deadline=Date.now()+40000;
    for(;;){
      try{result=await connection.client.sendBridgeMethod('report.snapshot.capture/v2',{pageId,scale:2,region:{x:0,y:0,width:1600,height:900}});break;}
      catch(error){if(!error.retryable||Date.now()>=deadline)throw error;await setTimeout(error.retryAfterMs??2000);}
    }
    if(result.mimeType!=='image/png'||!result.payload)throw new Error('No PNG for '+pageId);
    const file=path.join(root,'../reports/figures/powerbi/report_'+pageId+'.png');
    fs.writeFileSync(file,Buffer.from(result.payload,result.encoding||'base64'));
    console.log(JSON.stringify({pageId,file}));
  }
} finally {connection.client.dispose();}
