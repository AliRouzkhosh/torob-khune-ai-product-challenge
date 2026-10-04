// Tests the shipped bootstrap and theme interaction code without browser dependencies.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const bootstrap = fs.readFileSync('finder/static/finder/theme.js','utf8');
const appSource = fs.readFileSync('finder/static/finder/app.js','utf8');
// Run the actual theme block; unrelated dialogs/fetches need a real browser DOM.
const themeStart = appSource.indexOf('// Theme choice and saved homes');
const themeEnd = appSource.indexOf('const persianNumber',themeStart);
assert.ok(themeStart >= 0 && themeEnd > themeStart,'shipped theme block must be present');
const interactions = appSource.slice(themeStart,themeEnd);
function env(dark, stored, blocked=false) {
  const storage = new Map(stored ? [['khane-theme',stored]] : []);
  const media={matches:dark,addEventListener(name,fn){this.change=fn;}};
  const toggle={attrs:{},setAttribute(k,v){this.attrs[k]=v;},addEventListener(name,fn){this.click=fn;}};
  const choices=['light','dark','system'].map(choice=>({dataset:{themeChoice:choice},attrs:{},setAttribute(k,v){this.attrs[k]=v;},addEventListener(name,fn){this.click=fn;}}));
  const root={dataset:{}};
  const handlers={};
  const context={window:{addEventListener(){}},document:{documentElement:root,querySelector(){return null;},querySelectorAll(s){return s==='.theme-toggle'?[toggle]:s==='[data-theme-choice]'?choices:[];},addEventListener(type,fn){(handlers[type]??=[]).push(fn);}},matchMedia:()=>media,localStorage:{getItem:k=>{if(blocked)throw Error();return storage.get(k);},setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},location:{hash:''}};
  vm.createContext(context);vm.runInContext(bootstrap,context);vm.runInContext(interactions,context);
  // Theme controls use delegated document clicks in the shipped code.
  function click(control, selector) {
    for(const handler of handlers.click||[]) handler({target:{closest:s=>s===selector?control:null}});
  }
  toggle.click=()=>click(toggle,'.theme-toggle');
  choices.forEach(choice=>{choice.click=()=>click(choice,'[data-theme-choice]');});
  return {context,root,media,toggle,choices,storage};
}
assert.equal(env(false).root.dataset.theme,'light');
assert.equal(env(true).root.dataset.theme,'dark');
assert.equal(env(true,'light').root.dataset.theme,'light');
assert.equal(env(false,'dark').root.dataset.theme,'dark');
const app=env(false);app.toggle.click();assert.equal(app.root.dataset.theme,'dark');assert.equal(app.storage.get('khane-theme'),'dark');vm.runInContext(bootstrap,app.context);assert.equal(app.root.dataset.theme,'dark');
app.choices[2].click();assert.equal(app.storage.has('khane-theme'),false);app.media.matches=true;app.media.change();assert.equal(app.root.dataset.theme,'dark');
assert.equal(env(true,null,true).root.dataset.theme,'dark');
console.log('7 theme scenarios passed (system light/dark, overrides, persisted toggle, system change, blocked storage).');
