const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../finder/static/finder/app.js'),'utf8');
async function cancelWithShadowedAction(){
 const marker=source.indexOf("const form=event.target.closest('[data-compare-form]')");
 const start=source.lastIndexOf("document.addEventListener('submit',async event=>{",marker);
 const end=source.indexOf('\n});',marker)+5;
 let handler,request,utilitiesUpdated=false,announcement;
 const cancel={name:'',disabled:false,isConnected:false};
 const form={action:{name:'action',value:'clear'},dataset:{},contains:()=>true,querySelector:()=>cancel,getAttribute:name=>name==='action'?'/compare/toggle/':null};
 const buttons=[0,1,2].map(value=>({value:String(value),closest:()=>null,setAttribute(name,value){this[name]=value;},classList:{toggle(){}},textContent:'✓ انتخاب‌شده'}));
 const sandbox={document:{activeElement:cancel,addEventListener(type,fn){handler=fn;},querySelectorAll:()=>buttons,querySelector:()=>null},FormData:class{constructor(f){assert.equal(f,form);this.action='clear';}set(){}},DOMParser:class{parseFromString(){return {};}},updateUtilities(){utilitiesUpdated=true;},announce(message,error){announcement={message,error};},fetch:async(url,options)=>{request={url,options};return{ok:true,json:async()=>({cleared:true,selected:false,count:0,error:'',utilities:'<template></template>'})};}};
 vm.runInNewContext(source.slice(start,end),sandbox);
 await handler({target:{closest:()=>form},submitter:cancel,preventDefault(){}});
 assert.equal(request.url,'/compare/toggle/');assert.equal(request.options.method,'POST');assert.equal(request.options.body.action,'clear');
 assert.equal(utilitiesUpdated,true);assert.equal(announcement.error,false);assert.equal(announcement.message,'مقایسه پاک شد');
 for(const button of buttons){assert.equal(button['aria-pressed'],'false');assert.equal(button.textContent,'+ مقایسه');}
 assert.equal(cancel.disabled,false);
}
function stableStickyThreshold(){
 const fullHeight=121.85,compactHeight=60;let observer,reads=0,writes=0,desktop=true;
 const classes=new Set();
 const form={classList:{remove(...names){names.forEach(n=>classes.delete(n));},add(n){classes.add(n);},toggle(n,on){writes++;if(on)classes.add(n);else classes.delete(n);}},getBoundingClientRect(){reads++;return{height:classes.has('is-compact')?compactHeight:fullHeight};}};
 const sentinel={},space={style:{height:'0px'}};
 const media={get matches(){return desktop;},addEventListener(type,fn){this.change=fn;}};
 const sandbox={window:{IntersectionObserver:true},document:{querySelector:s=>s==='.refinement-search'?form:s==='.search-sticky-sentinel'?sentinel:space},matchMedia:()=>media,getComputedStyle:()=>({getPropertyValue:()=>String(compactHeight)+'px'}),IntersectionObserver:class{constructor(fn){this.fn=fn;observer=this;}observe(node){assert.equal(node,sentinel);}disconnect(){}},Number,Math,parseFloat};
 vm.runInNewContext(source.slice(source.indexOf('let searchObserver;')),sandbox);
 const initReads=reads;
 const emit=compact=>observer.fn([{isIntersecting:!compact,boundingClientRect:{top:compact?-1:1}}]);
 for(let cycle=0;cycle<50;cycle++){
  emit(true);assert.equal(classes.has('is-compact'),true);assert.ok(Math.abs(compactHeight+parseFloat(space.style.height)-fullHeight)<0.001);
  const stableWrites=writes;for(let repeat=0;repeat<10;repeat++)emit(true);assert.equal(writes,stableWrites);
  emit(false);assert.equal(classes.has('is-compact'),false);assert.equal(space.style.height,'0px');
 }
 // No geometry read may force layout between compaction and spacer restoration.
 assert.equal(reads,initReads);
 desktop=false;media.change();assert.equal(classes.has('search-sticky-ready'),false);assert.equal(space.style.height,'0px');
}
(async()=>{await cancelWithShadowedAction();stableStickyThreshold();console.log('PASS: shadowed action cancellation; 50 sticky threshold cycles; repeated callback stability; mobile reset');})().catch(error=>{console.error(error);process.exitCode=1;});
