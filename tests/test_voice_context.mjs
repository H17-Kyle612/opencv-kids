import test from 'node:test';
import assert from 'node:assert/strict';
import {BackgroundContext} from '../voice_context.js';
class Source {
 constructor(url){this.url=url;Source.instance=this;}
 close(){this.closed=true;}
 emit(sequence,bites){this.onmessage({data:JSON.stringify({sequence,at:new Date().toISOString(),context:{react:true,priority:'urgent',bites}})});}
}
globalThis.EventSource=Source;
test('背景は発話を要求せず、詰まった場合は最新の一件だけを送る',()=>{
 const sent=[],reports=[];
 const channel={readyState:'open',bufferedAmount:0,send:data=>sent.push(JSON.parse(data))};
 const feed=new BackgroundContext(()=>channel,report=>reports.push(report),error=>assert.fail(error));
 feed.start();const source=Source.instance;
 source.emit(1,[1,2]);source.emit(1,[1,2]);
 assert.equal(sent.length,1);
 assert.equal(sent[0].channel,'commentary');
 assert.deepEqual(JSON.parse(sent[0].content[0].text),{react:false,priority:'background',bites:[1,2]});
 channel.bufferedAmount=20000;
 source.emit(2,[2,2]);source.emit(3,[3,2]);
 assert.equal(sent.length,1);
 channel.bufferedAmount=0;feed.flush();
 assert.equal(sent.length,2);
 assert.deepEqual(reports.at(-1).context.bites,[3,2]);
 assert.equal(feed.total,2);
 feed.close();assert.equal(source.closed,true);
 source.emit(4,[4,2]);assert.equal(sent.length,2);
});
