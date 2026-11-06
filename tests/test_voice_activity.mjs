import test from 'node:test';
import assert from 'node:assert/strict';
import {SpeechActivity} from '../voice_activity.js';
test('小さめの声と短い息継ぎでは発話を終了しない',()=>{
 const activity=new SpeechActivity();
 assert.equal(activity.update(.006,0).type,'speech_started');
 assert.equal(activity.update(0,1200),null);
 assert.equal(activity.speaking,true);
 assert.deepEqual(activity.update(.006,1250),{type:'speech_gap',gap_ms:1250});
 assert.equal(activity.speaking,true);
 assert.equal(activity.update(.006,1300),null);
});
test('十分な無音のあとだけ終了し、再開を検出する',()=>{
 const activity=new SpeechActivity();
 assert.equal(activity.update(0,0),null);
 activity.update(.1,100);
 assert.equal(activity.update(0,1499),null);
 assert.deepEqual(activity.update(0,1500),{type:'speech_ended'});
 assert.equal(activity.update(0,1600),null);
 assert.deepEqual(activity.update(.1,2000),{type:'speech_started',gap_ms:1900});
});
