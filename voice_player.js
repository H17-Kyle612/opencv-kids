const $=id=>document.getElementById(id);
const start=$('start'),stop=$('stop'),status=$('status'),audio=$('audio'),transcript=$('transcript');
let peer,channel,context,oscillator,completed=false,analyser,signal,speech=false,lastLoud=0,statsAt=0;
const post=async(path,body={})=>{const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw Error(data.error||'接続に失敗しました');return data;};
function cleanup(){completed=true;channel?.close();peer?.close();oscillator?.stop();context?.close();peer=channel=context=oscillator=analyser=signal=null;speech=false;audio.srcObject=null;start.disabled=false;stop.disabled=true;}
start.onclick=async()=>{start.disabled=true;completed=false;transcript.textContent='';status.textContent='音声を接続しています…';try{
 context=new AudioContext({latencyHint:'interactive'});await context.resume();
 peer=new RTCPeerConnection();
 peer.ontrack=event=>{const stream=new MediaStream([event.track]);audio.srcObject=stream;audio.play().catch(()=>status.textContent='再生ボタンを押してください');
  const source=context.createMediaStreamSource(stream);analyser=context.createAnalyser();analyser.fftSize=256;signal=new Float32Array(analyser.fftSize);source.connect(analyser);
 };
 // Full-duplexモデルの音声クロック。マイクは取得せず、無音を送る。
 oscillator=context.createOscillator();const gain=context.createGain();gain.gain.value=0;const dest=context.createMediaStreamDestination();oscillator.connect(gain);gain.connect(dest);oscillator.start();peer.addTrack(dest.stream.getAudioTracks()[0],dest.stream);
 channel=peer.createDataChannel('oai-events');
 channel.onmessage=async({data})=>{const event=JSON.parse(data);if(event.type==='session.started'){status.textContent='実況接続済み';stop.disabled=false;await post('ready');}
 else if(event.type==='session.closed'||event.type==='error'){status.textContent='実況の接続が終了しました';cleanup();}};
 channel.onclose=()=>{if(!completed){status.textContent='実況の接続が終了しました';cleanup();}};
 peer.onconnectionstatechange=()=>{if(peer?.connectionState==='failed'){status.textContent='音声接続に失敗しました。もう一度開始してください';cleanup();}};
 await peer.setLocalDescription(await peer.createOffer());
 if(peer.iceGatheringState!=='complete')await new Promise((resolve,reject)=>{const timeout=setTimeout(()=>reject(Error('音声接続の準備が時間切れになりました')),10000);peer.addEventListener('icegatheringstatechange',()=>{if(peer.iceGatheringState==='complete'){clearTimeout(timeout);resolve();}});});
 const answer=await post('connect',{sdp:peer.localDescription.sdp});await peer.setRemoteDescription({type:'answer',sdp:answer.sdp});
}catch(error){status.textContent=error.message;cleanup();}};
stop.onclick=async()=>{cleanup();status.textContent='実況を停止しました';try{await post('stop');}catch{}};
const fmt=iso=>iso?new Date(iso).toLocaleTimeString('ja-JP',{hour12:false,hour:'2-digit',minute:'2-digit',second:'2-digit',fractionalSecondDigits:3}):'—';
const json=value=>JSON.stringify(value,null,2);
const eventNames={start:'スタート',resume:'再開',cake_finished:'おかわり',lead_change:'リード変化',final_stretch:'終盤',finish:'フィニッシュ'};
let lastSequence=-1;
async function refresh(){try{
 const r=await fetch('state');if(!r.ok)throw Error();const s=await r.json();transcript.textContent=s.transcript;
 if(s.error){status.textContent=s.error;if(peer)cleanup();}
 const d=s.debug;if(d.current){$('current').textContent=json(d.current.context);$('captured').textContent='取得 '+fmt(d.current.at);}
 const sent=d.sent.at(-1);
 if(sent){$('sentAt').textContent=`#${sent.sequence} 取得 ${fmt(sent.captured_at)} → 送信 ${fmt(sent.sent_at)}　${sent.status}`;$('payload').textContent=sent.request.params.text;$('request').textContent=json(sent.request);
  const age=Math.max(0,Date.now()-Date.parse(sent.captured_at));
  $('metrics').textContent=`実況制御：${d.speaking?'発話中・追加の実況合図を待機':d.awaiting_audio?'音声を待機中':'次の展開に反応できます'}\n最新送信データの古さ ${age.toFixed(0)} ms ／ 送信待ち ${sent.queue_ms} ms ／ App Server受付 ${sent.ack_ms??'…'} ms\n音声パケット受信 ${d.browser.bytes_received??'—'} bytes ／ 平均ジッターバッファ ${d.browser.jitter_buffer_ms??'—'} ms`;
  if(sent.sequence!==lastSequence){lastSequence=sent.sequence;$('history').replaceChildren(...d.sent.slice().reverse().map(e=>{const row=document.createElement('tr');const values=[`#${e.sequence} ${fmt(e.sent_at)}`,`${e.context.state} ／ ${e.context.react?'実況を促す':'背景更新'}`,e.context.events.map(x=>eventNames[x.type]||x.type).join('、')||'—',`${e.queue_ms} ms ／ ${e.ack_ms??'…'} ms`];for(const value of values){const cell=document.createElement('td');cell.textContent=value;row.append(cell);}return row;}));}
 }
 $('audioLog').textContent=d.audio.map(e=>`${fmt(e.browser_at)}　${e.type==='speech_started'?'発声を検出':'無音を検出'}`).join('\n')||'音声未検出';
}catch{}finally{setTimeout(refresh,250);}}
fetch('prompt').then(r=>r.json()).then(value=>$('prompt').textContent=`モデル：${value.model}\n音声：${value.voice}\n\n${value.prompt}`).catch(()=>$('prompt').textContent='取得できませんでした');
refresh();
setInterval(async()=>{if(!peer||!analyser||!signal)return;const now=performance.now();analyser.getFloatTimeDomainData(signal);const rms=Math.sqrt(signal.reduce((sum,x)=>sum+x*x,0)/signal.length);let type;
 if(rms>.008){lastLoud=now;if(!speech){speech=true;type='speech_started';}}else if(speech&&now-lastLoud>600){speech=false;type='speech_ended';}
 let metrics;
 if(now-statsAt>2000){statsAt=now;try{const reports=await peer.getStats();for(const report of reports.values())if(report.type==='inbound-rtp'&&report.kind==='audio')metrics={bytes_received:report.bytesReceived,jitter_buffer_ms:report.jitterBufferEmittedCount?Math.round(report.jitterBufferDelay/report.jitterBufferEmittedCount*1000):0};}catch{}}
 if(type||metrics)post('playback',{type,at:new Date().toISOString(),metrics}).catch(()=>{});
},100);
window.addEventListener('pagehide',()=>navigator.sendBeacon('stop',new Blob(['{}'],{type:'application/json'})));
