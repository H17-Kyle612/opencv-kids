// App Serverで作ったV3セッションの背景情報を、同じWebRTC接続に流す。
// 0.166.0のwire形式ではcommentaryが背景、speakableが発話向け。
export class BackgroundContext {
 constructor(getChannel, report, failed){
  this.getChannel=getChannel;this.report=report;this.failed=failed;
  this.packet=null;this.lastSequence=0;this.total=0;this.source=null;
 }
 start(){
  const source=new EventSource('context-events');this.source=source;
  source.onmessage=({data})=>{
   if(this.source!==source)return;
   try{this.packet=JSON.parse(data);this.flush();}catch(error){this.failed(error.message);}
  };
 }
 flush(){
  const channel=this.getChannel(), packet=this.packet;
  if(!packet||packet.sequence===this.lastSequence||!channel||channel.readyState!=='open'||channel.bufferedAmount>16384)return;
  // 発話を要求するフラグを背景側へ流さない。常にその時点の最新情報1件だけを送る。
  const context={...packet.context,react:false,priority:'background'};
  const payload={type:'session.context.append',channel:'commentary',content:[{type:'input_text',text:JSON.stringify(context)}]};
  channel.send(JSON.stringify(payload));this.lastSequence=packet.sequence;this.total++;
  this.report({captured_at:packet.at,sent_at:new Date().toISOString(),context,payload});
 }
 close(){this.source?.close();this.source=null;}
}
