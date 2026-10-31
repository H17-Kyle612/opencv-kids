const $ = id => document.getElementById(id);
const start=$('start'), stop=$('stop'), status=$('status'), audio=$('audio'), transcript=$('transcript');
const editor=$('editor'), voice=$('voice'), apply=$('apply'), reset=$('reset');
let peer, channel, context, oscillator, analyser, signal, completed=false, connecting=false;
let speech=false, lastLoud=0, statsAt=0, previousStats, defaults, lastSequence=-1;
const json=value=>JSON.stringify(value,null,2);
const fmt=iso=>iso?new Date(iso).toLocaleTimeString('ja-JP',{hour12:false,hour:'2-digit',minute:'2-digit',second:'2-digit',fractionalSecondDigits:3}):'—';
async function get(path){const r=await fetch(path);const body=await r.json();if(!r.ok)throw Error(body.error||'取得できませんでした');return body;}
async function post(path,body={}){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw Error(data.error||'接続に失敗しました');return data;}
function cleanup(){
 completed=true;channel?.close();peer?.close();oscillator?.stop();context?.close();
 peer=channel=context=oscillator=analyser=signal=null;speech=false;previousStats=null;audio.srcObject=null;
 start.disabled=connecting||!defaults;stop.disabled=true;
}
async function connect(){
 if(connecting)return;
 connecting=true;start.disabled=apply.disabled=true;completed=false;transcript.textContent='';status.textContent='音声を接続しています…';
 try{
  context=new AudioContext({latencyHint:'interactive'});await context.resume();
  peer=new RTCPeerConnection();
  const connection=peer;
  peer.ontrack=event=>{
   if(peer!==connection)return;
   const stream=new MediaStream([event.track]);audio.srcObject=stream;
   audio.play().catch(()=>status.textContent='再生ボタンを押してください');
   const source=context.createMediaStreamSource(stream);analyser=context.createAnalyser();analyser.fftSize=256;
   signal=new Float32Array(analyser.fftSize);source.connect(analyser);
  };
  // Full-duplexモデルの音声クロック。マイクは取得せず、無音を送る。
  oscillator=context.createOscillator();const gain=context.createGain();gain.gain.value=0;
  const dest=context.createMediaStreamDestination();oscillator.connect(gain);gain.connect(dest);oscillator.start();
  peer.addTrack(dest.stream.getAudioTracks()[0],dest.stream);
  channel=peer.createDataChannel('oai-events');
  channel.onmessage=async({data})=>{
   if(peer!==connection)return;
   const event=JSON.parse(data);
   if(event.type==='session.started'){
    try{await post('ready');status.textContent='実況接続済み';stop.disabled=false;}
    catch(error){status.textContent=error.message;cleanup();}
   }else if(event.type==='session.closed'||event.type==='error'){status.textContent='実況の接続が終了しました';cleanup();}
  };
  channel.onclose=()=>{if(peer===connection&&!completed){status.textContent='実況の接続が終了しました';cleanup();}};
  peer.onconnectionstatechange=()=>{if(peer===connection&&connection.connectionState==='failed'){status.textContent='音声接続に失敗しました。もう一度開始してください';cleanup();}};
  await peer.setLocalDescription(await peer.createOffer());
  if(peer.iceGatheringState!=='complete')await new Promise((resolve,reject)=>{
   const timeout=setTimeout(()=>reject(Error('音声接続の準備が時間切れになりました')),10000);
   peer.addEventListener('icegatheringstatechange',()=>{if(peer.iceGatheringState==='complete'){clearTimeout(timeout);resolve();}});
  });
  const answer=await post('connect',{sdp:peer.localDescription.sdp});
  await peer.setRemoteDescription({type:'answer',sdp:answer.sdp});
 }catch(error){status.textContent=error.message;cleanup();}
 finally{connecting=false;apply.disabled=!defaults;start.disabled=!!peer||!defaults;}
}
start.onclick=connect;
stop.onclick=async()=>{cleanup();status.textContent='実況を停止しました';try{await post('stop');}catch{}};
apply.onclick=async()=>{
 apply.disabled=true;
 try{
  const result=await post('settings',{prompt:editor.value,voice:voice.value});
  const wasConnected=!!peer;
  $('settingsStatus').textContent=`設定 #${result.saved.revision} を保存しました。${wasConnected?'実況を再接続しています…':'次の実況開始から反映されます。'}`;
  if(wasConnected){cleanup();await post('stop');await connect();$('settingsStatus').textContent=peer?'保存した設定で再接続しました。':'保存済みです。実況を開始して再接続してください。';}
 }catch(error){$('settingsStatus').textContent=error.message;}
 finally{apply.disabled=false;}
};
reset.onclick=()=>{editor.value=defaults.default_prompt;voice.value=defaults.default_voice;$('settingsStatus').textContent='標準文を入力しました。「保存して反映」で適用します。';};
editor.oninput=voice.onchange=()=>{$('settingsStatus').textContent='未保存の変更があります。「保存して反映」を押してください。';};
async function loadSettings(){
 try{
  const [settings,catalog]=await Promise.all([get('prompt'),get('voices')]);defaults=settings;
  voice.replaceChildren(...catalog.voices.map(name=>{const option=document.createElement('option');option.value=option.textContent=name;return option;}));
  voice.value=catalog.voices.includes(settings.saved.voice)?settings.saved.voice:'';
  editor.value=settings.saved.prompt;editor.disabled=voice.disabled=apply.disabled=reset.disabled=start.disabled=false;
  $('settingsStatus').textContent=voice.value?'編集して「保存して反映」で変更できます。':'保存した声は現在利用できません。候補から選んで保存してください。';
 }catch(error){$('settingsStatus').textContent=error.message;}
}
const eventNames={start:'スタート',resume:'再開',cake_finished:'おかわり',lead_change:'リード変化',final_stretch:'終盤',finish:'フィニッシュ'};
const audioNames={speech_started:'発声を検出',speech_ended:'無音を検出',audio_waiting:'再生待ち',audio_stalled:'再生の停滞',audio_playing:'再生開始'};
function renderDebug(s){
 transcript.textContent=s.transcript;
 if(s.error&&!connecting){status.textContent=s.error;if(peer)cleanup();}
 const active=s.active_settings;
 $('activeSettings').textContent=active?`適用中：声 ${active.voice} ／ 設定 #${active.revision}`:'実況は未接続';
 $('prompt').textContent=active?`要求モデル：${defaults?.requested_model||defaults?.model||'App Serverの設定・既定値に従う'}\n実モデル：未取得（App Server応答に識別情報なし）\n声：${active.voice}\n\n${active.prompt}`:'まだ実況に適用されていません。上の入力欄は保存する設定です。';
 const d=s.debug;
 if(d.current){$('current').textContent=json(d.current.context);$('captured').textContent='取得 '+fmt(d.current.at);}
 const sent=d.sent.at(-1);
 if(sent){
  $('sentAt').textContent=`#${sent.sequence} 取得 ${fmt(sent.captured_at)} → 送信 ${fmt(sent.sent_at)}　${sent.status}`;
  $('payload').textContent=sent.request.params.text;$('request').textContent=json(sent.request);
  const age=Math.max(0,Date.now()-Date.parse(sent.captured_at));
  $('metrics').textContent=`実況制御：${d.speaking?'発話中・送信を待機':d.awaiting_audio?'音声を待機中':'次の展開に反応できます'}\n最新送信データの古さ ${age.toFixed(0)} ms ／ 送信待ち ${sent.queue_ms} ms ／ App Server受付 ${sent.ack_ms??'…'} ms\n音声受信 ${d.browser.bytes_received??'—'} bytes ／ 欠落パケット ${d.browser.packets_lost??'—'} ／ 破棄 ${d.browser.packets_discarded??'—'}\n直近の音声補間 ${d.browser.concealed_percent??'—'} %（うち無音 ${d.browser.silent_concealed_percent??'—'} %）\n平均ジッターバッファ ${d.browser.jitter_buffer_ms??'—'} ms ／ 往復通信 ${d.browser.rtt_ms??'—'} ms ／ 音声処理 ${d.browser.audio_context??'—'}`;
  if(sent.sequence!==lastSequence){
   lastSequence=sent.sequence;$('history').replaceChildren(...d.sent.slice().reverse().map(e=>{
    const row=document.createElement('tr');
    const values=[`#${e.sequence} ${fmt(e.sent_at)}`,`${e.context.state} ／ ${e.context.react?'実況を促す':'背景更新'}`,e.context.events.map(x=>eventNames[x.type]||x.type).join('、')||'—',`${e.queue_ms} ms ／ ${e.ack_ms??'…'} ms`];
    for(const value of values){const cell=document.createElement('td');cell.textContent=value;row.append(cell);}return row;
   }));
  }
 }
 $('audioLog').textContent=d.audio.map(e=>`${fmt(e.browser_at)}　${audioNames[e.type]||e.type}`).join('\n')||'音声未検出';
}
async function refresh(){try{renderDebug(await get('state'));}catch{}finally{setTimeout(refresh,500);}}
async function measure(){
 if(!peer||!analyser||!signal)return;
 const now=performance.now();analyser.getFloatTimeDomainData(signal);
 const rms=Math.sqrt(signal.reduce((sum,x)=>sum+x*x,0)/signal.length);let type;
 if(rms>.008){lastLoud=now;if(!speech){speech=true;type='speech_started';}}
 else if(speech&&now-lastLoud>1000){speech=false;type='speech_ended';}
 let metrics;
 if(now-statsAt>2000){
  statsAt=now;
  try{
   const reports=await peer.getStats();
   for(const report of reports.values())if(report.type==='inbound-rtp'&&report.kind==='audio'){
    const samples=report.totalSamplesReceived, concealed=report.concealedSamples;
    const silent=report.silentConcealedSamples;
    const delta=samples-(previousStats?.samples??samples), repaired=concealed-(previousStats?.concealed??concealed);
    const silentRepaired=silent-(previousStats?.silent??silent);
    metrics={bytes_received:report.bytesReceived,packets_lost:report.packetsLost,
     concealed_percent:delta>0?Math.round(repaired/delta*10000)/100:null,
     silent_concealed_percent:delta>0&&Number.isFinite(silentRepaired)?Math.round(silentRepaired/delta*10000)/100:null,
     packets_discarded:report.packetsDiscarded,
     jitter_buffer_ms:report.jitterBufferEmittedCount?Math.round(report.jitterBufferDelay/report.jitterBufferEmittedCount*1000):null,
     audio_context:context.state};
    previousStats={samples,concealed,silent};
   }
   for(const report of reports.values())if(report.type==='candidate-pair'&&report.state==='succeeded'&&report.nominated&&metrics)
    metrics.rtt_ms=report.currentRoundTripTime==null?null:Math.round(report.currentRoundTripTime*1000);
  }catch{}
 }
 if(type||metrics)post('playback',{type,at:new Date().toISOString(),metrics}).catch(()=>{});
}
for(const [name,type] of [['waiting','audio_waiting'],['stalled','audio_stalled'],['playing','audio_playing']])
 audio.addEventListener(name,()=>post('playback',{type,at:new Date().toISOString()}).catch(()=>{}));
loadSettings();refresh();setInterval(measure,100);
window.addEventListener('pagehide',()=>navigator.sendBeacon('stop',new Blob(['{}'],{type:'application/json'})));
