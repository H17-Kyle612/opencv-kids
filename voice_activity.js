// 無音は受信音声の推定。短い息継ぎを発話終了として扱わない。
export class SpeechActivity {
 constructor(){this.speaking=false;this.lastLoud=null;}
 update(rms,now){
  if(rms>.004){
   const gap=this.lastLoud===null?null:Math.round(now-this.lastLoud);
   this.lastLoud=now;
   if(!this.speaking){this.speaking=true;return {type:'speech_started',gap_ms:gap};}
   if(gap>=350)return {type:'speech_gap',gap_ms:gap};
  }else if(this.speaking&&now-this.lastLoud>=1400){
   this.speaking=false;return {type:'speech_ended'};
  }
  return null;
 }
}
