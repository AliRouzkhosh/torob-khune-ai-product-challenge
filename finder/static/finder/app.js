// Small progressive enhancements only; search/review/filter forms work without JS.
document.documentElement.classList.add('enhanced');
document.querySelectorAll('[data-example]').forEach(button => {
  button.addEventListener('click', event => {
    event.preventDefault();
    const input = document.querySelector('#query');
    input.value = button.dataset.example;
    input.focus();
    input.scrollIntoView({block: 'center', behavior: 'instant'});
    document.querySelector('#example-status').textContent = 'مثال وارد شد؛ می‌تونی متن را تغییر بدهی و جستجو کنی.';
  });
});
document.addEventListener('invalid', event => {
  const disclosure = event.target.closest('details');
  if (disclosure) disclosure.open = true;
}, true);
function initializeCriteria() {
  const criteria = document.querySelector('.criteria-details');
  if (criteria) criteria.open = !matchMedia('(max-width: 1023px)').matches;
}
initializeCriteria();
matchMedia('(max-width: 1023px)').addEventListener('change',initializeCriteria);
// Theme choice and saved homes are small progressive enhancements, not new state stores.
const themeSystem = matchMedia('(prefers-color-scheme: dark)');
function themeChoice() { try { return localStorage.getItem('khane-theme') || 'system'; } catch (_) { return 'system'; } }
function applyTheme(choice, persist = false) {
  if (persist) { try { choice === 'system' ? localStorage.removeItem('khane-theme') : localStorage.setItem('khane-theme', choice); } catch (_) {} }
  const dark = choice === 'dark' || (choice === 'system' && themeSystem.matches);
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  document.querySelectorAll('.theme-toggle').forEach(b => { b.setAttribute('aria-pressed', String(dark)); b.setAttribute('aria-label', dark ? 'حالت روشن' : 'حالت تیره'); });
  document.querySelectorAll('[data-theme-choice]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.themeChoice === choice)));
}
applyTheme(themeChoice());
document.addEventListener('click',event=>{
  const toggle=event.target.closest('.theme-toggle');
  const choice=event.target.closest('[data-theme-choice]');
  if(toggle) applyTheme(document.documentElement.dataset.theme==='dark'?'light':'dark',true);
  if(choice) applyTheme(choice.dataset.themeChoice,true);
});
themeSystem.addEventListener('change',()=>{if(themeChoice()==='system')applyTheme('system');});
document.addEventListener('keydown',event=>{
  const user=document.querySelector('.user-center');
  if(event.key==='Escape' && user?.open){user.open=false;user.querySelector('summary').focus();}
});
document.addEventListener('click',event=>{
  const user=document.querySelector('.user-center');
  if(user?.open && !user.contains(event.target))user.open=false;
});
const persianNumber = n => String(n).replace(/\d/g, d => '۰۱۲۳۴۵۶۷۸۹'[d]);
document.addEventListener('submit', async event => {
  const form=event.target.closest('[data-save-form]'); if(!form)return;
  event.preventDefault();
  const saveHadFocus=form.contains(document.activeElement);
  const buttons = [...document.querySelectorAll(`[data-save-form][data-listing="${form.dataset.listing}"] button`)];
  buttons.forEach(b => b.disabled = true);
  const data = new FormData(form); data.set('listing', form.dataset.listing);
  try {
    const response = await fetch(form.action, {method:'POST', body:data, headers:{'X-Requested-With':'XMLHttpRequest'}});
    if (!response.ok) throw new Error();
    const state = await response.json();
    buttons.forEach(b => { b.setAttribute('aria-pressed', String(state.saved)); b.setAttribute('aria-label', state.saved ? 'حذف از ذخیره‌ها' : 'ذخیره خانه'); b.querySelector('svg').setAttribute('fill', state.saved ? 'currentColor' : 'none'); });
    document.querySelectorAll('.saved-count').forEach(el => el.textContent = persianNumber(state.count));
    document.querySelectorAll(`[data-saved-indicator="${state.id}"]`).forEach(el => el.querySelector('svg').toggleAttribute('hidden', !state.saved));
    announce(state.saved ? 'خانه ذخیره شد' : 'از ذخیره‌ها حذف شد');
    if (!state.saved && document.querySelector('.saved-grid')) { form.closest('.listing-card')?.remove(); if (!document.querySelector('.saved-grid .listing-card')) document.querySelector('.saved-empty').hidden = false; }
  } catch (_) { document.querySelector('#save-status').textContent = 'تغییر ذخیره‌ها تأیید نشد. صفحه را تازه کن و دوباره بررسی کن.'; }
  finally { buttons.forEach(b => b.disabled = false); if(saveHadFocus)(form.isConnected?form.querySelector('button'):document.querySelector('.saved-grid [data-save-form] button,.saved-empty a'))?.focus({preventScroll:true}); }
});
// Required amenities and priorities remain coherent during review, before submission.
document.querySelectorAll('[name="required_amenities"]').forEach(box => box.addEventListener('change', () => {
  const priority = document.querySelector(`select[name="${box.value}"]`);
  if (priority) priority.value = box.checked ? 'high' : 'low';
}));
['parking','elevator','storage'].forEach(key => document.querySelector(`select[name="${key}"]`)?.addEventListener('change', e => {
  if (['low','ignored','medium'].includes(e.target.value)) { const box = document.querySelector(`[name="required_amenities"][value="${key}"]`); if (box) box.checked = false; }
}));
function openProjectAnchor() {
  if (['#project','#ranking','#data'].includes(location.hash)) {
    const disclosure = document.querySelector('.project-disclosure');
    if (disclosure) { disclosure.open = true; document.querySelector(location.hash)?.scrollIntoView({block:'start'}); }
  }
}
openProjectAnchor();
window.addEventListener('hashchange', openProjectAnchor);

document.querySelector('[data-dismiss-save]')?.addEventListener('click', () => { document.querySelector('#save-feedback').hidden = true; });

const neighborhoodControl=document.querySelector('[name="neighborhood"]');
const scopeControl=document.querySelector('[data-neighborhood-scope]');
if(neighborhoodControl && scopeControl) neighborhoodControl.addEventListener('change',()=>{scopeControl.hidden=!neighborhoodControl.value; document.querySelector('[name="neighborhood_scope"]').value='exact';});

// Delegation keeps contact actions working after the authenticated partial updates.
document.addEventListener('click', async event => {
  const copy = event.target.closest('[data-copy-contact]');
  const link = event.target.closest('[data-contact-action]');
  const target = document.querySelector('#contact-result');
  if (copy && target) {
    const phone = target.querySelector('.demo-phone');
    const feedback = target.querySelector('.contact-feedback');
    if (!phone) return;
    try {
      if (!navigator.clipboard?.writeText) throw new Error();
      await navigator.clipboard.writeText(phone.textContent.trim());
      feedback.textContent = 'شماره کپی شد';
    } catch (_) {
      const range = document.createRange(); range.selectNodeContents(phone);
      const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
      phone.focus({preventScroll:true});
      feedback.textContent = 'کپی خودکار در دسترس نیست؛ متن شماره انتخاب شد، آن را کپی کن.';
    }
    return;
  }
  if (!link || !target) return;
  event.preventDefault();
  if (target.getAttribute('aria-busy') === 'true') return;
  const action = link.dataset.contactAction;
  if (action === 'phone' && link.dataset.revealed && target.querySelector('.demo-phone')) {
    target.querySelector('.demo-phone').focus(); return;
  }
  // Reserve a new tab during the gesture only when a validated destination is configured.
  // The source page stays put, and the new tab has no opener.
  const popup = action === 'bale' && link.hasAttribute('data-bale-external') ? window.open('about:blank', '_blank') : null;
  if (popup) popup.opener = null;
  target.setAttribute('aria-busy', 'true'); link.setAttribute('aria-disabled', 'true');
  try {
    const response = await fetch(link.href, {headers: {'X-Requested-With':'XMLHttpRequest'}, cache:'no-store'});
    if (response.redirected) { popup?.close(); location.assign(response.url); return; }
    if (!response.ok) throw new Error();
    const fragment = new DOMParser().parseFromString(await response.text(), 'text/html');
    if (action === 'bale') {
      target.querySelector('.contact-feedback').innerHTML = fragment.querySelector('.contact-feedback').innerHTML;
      const destination = fragment.querySelector('[data-bale-link]');
      if (popup && destination) popup.location.replace(destination.href);
      else popup?.close();
    } else {
      target.innerHTML = fragment.body.innerHTML;
      document.querySelectorAll('.mobile-contact [data-contact-action="phone"]').forEach(button => {
        button.textContent = 'شماره نمایش داده شد'; button.dataset.revealed = 'true';
      });
      target.querySelector('.demo-phone')?.focus({preventScroll:true});
    }
    if (link.closest('.mobile-contact')) target.scrollIntoView({block:'center',behavior:'instant'});
  } catch (_) {
    popup?.close();
    target.querySelector('.contact-feedback').textContent = 'نمایش اطلاعات تماس انجام نشد؛ دوباره تلاش کن.';
  } finally { target.removeAttribute('aria-busy'); link.removeAttribute('aria-disabled'); }
});
document.querySelector('[data-description-toggle]')?.addEventListener('click', event => {
  const button = event.currentTarget;
  const expanded = button.getAttribute('aria-expanded') !== 'true';
  document.querySelector('#source-description').classList.toggle('is-collapsed', !expanded);
  button.setAttribute('aria-expanded', String(expanded));
  button.textContent = expanded ? 'بستن توضیحات ↑' : 'مشاهده توضیحات کامل ↓';
  if (!expanded) document.querySelector('.source-description').scrollIntoView({block:'start',behavior:'instant'});
});
// Revalidate gated content when a browser restores detail from its back/forward cache.
window.addEventListener('pageshow', event => { if (event.persisted && document.body.classList.contains('has-contact')) location.reload(); });

// Re-bind only replaced dialog nodes; controls themselves use delegated actions.
let filterOpener;
function openFilters(button) {
  const drawer=document.querySelector('#advanced-filters');if(!drawer)return;
  filterOpener=button;closeOtherSheets(drawer);drawer.showModal();
  document.querySelectorAll('[data-advanced-open]').forEach(b=>b.setAttribute('aria-expanded','true'));
  const section=button?.dataset.section;
  if(section){const target=document.getElementById('advanced-'+section);if(target){drawer.querySelector('.advanced-expansion').open=true;if(target.tagName==='DETAILS')target.open=true;target.scrollIntoView({block:'start'});target.querySelector('summary')?.focus({preventScroll:true});}}
}
function initializeFilters() {
  const drawer=document.querySelector('#advanced-filters');if(!drawer||drawer.dataset.bound)return;
  drawer.dataset.bound='true';
  drawer.addEventListener('close',()=>{document.querySelectorAll('[data-advanced-open]').forEach(b=>b.setAttribute('aria-expanded','false'));if(filterOpener?.isConnected)filterOpener.focus({preventScroll:true});});
  const age=drawer.querySelector('[name="advanced-age_preset"]'),custom=drawer.querySelector('[data-custom-age]');
  const showCustom=()=>{if(custom)custom.hidden=age.value!=='custom'&&!custom.querySelector('.errorlist');};
  age?.addEventListener('change',showCustom);if(age&&custom)showCustom();
  if(drawer.hasAttribute('data-open-on-load'))openFilters(document.querySelector('[data-advanced-open]'));
}
document.addEventListener('click',event=>{
  const open=event.target.closest('[data-advanced-open]');if(open)openFilters(open);
  if(event.target.closest('[data-advanced-close]'))document.querySelector('#advanced-filters')?.close();
  const rule=event.target.closest('[data-remove-rule]');if(rule){rule.form.querySelector('input[name="action"]').value='remove_logic';rule.form.noValidate=true;}
});
initializeFilters();
// Keep Tab within sheets as well as suppressing the page behind native modals.
document.addEventListener('keydown',event=>{
  if(event.key!=='Tab')return;
  const dialog=event.target.closest('dialog[open]');if(!dialog)return;
  const controls=[...dialog.querySelectorAll('button,input,select,textarea,a[href],summary')].filter(el=>!el.disabled&&el.getClientRects().length);
  const first=controls[0],last=controls[controls.length-1];
  if(event.shiftKey&&(document.activeElement===first||!controls.includes(document.activeElement))){event.preventDefault();last?.focus();}
  else if(!event.shiftKey&&(document.activeElement===last||!controls.includes(document.activeElement))){event.preventDefault();first?.focus();}
});
// Native dialogs contain focus and suppress controls behind mobile overlays.
let menuOpener;
const menu=document.querySelector('#mobile-menu');
menu?.addEventListener('close',()=>{menuOpener?.setAttribute('aria-expanded','false');menuOpener?.focus({preventScroll:true});});
document.addEventListener('click',event=>{
  const open=event.target.closest('[data-menu-open]');if(open){closeOtherSheets(menu);menuOpener=open;menu.showModal();open.setAttribute('aria-expanded','true');}
  if(event.target.closest('[data-menu-close]'))menu?.close();
});
const userSheet=document.createElement('dialog');userSheet.id='mobile-user-sheet';userSheet.className='mobile-user-sheet';userSheet.setAttribute('aria-label','فضای من');document.body.append(userSheet);
let userOwner,userOpener;
function closeUserSheet(){if(userSheet.open)userSheet.close();}
userSheet.addEventListener('close',()=>{
  const panel=userSheet.querySelector('.user-panel');if(panel&&userOwner?.isConnected)userOwner.append(panel);
  userOpener?.setAttribute('aria-expanded','false');if(userOpener?.isConnected)userOpener.focus({preventScroll:true});
});
document.addEventListener('click',event=>{
  const summary=event.target.closest('.user-center>summary');
  if(summary && matchMedia('(max-width:768px), (max-width:1023px) and (max-height:500px)').matches){event.preventDefault();closeOtherSheets(userSheet);userOwner=summary.parentElement;userOwner.open=false;userOpener=summary;userSheet.append(userOwner.querySelector('.user-panel'));userSheet.showModal();summary.setAttribute('aria-expanded','true');}
  if(event.target.closest('[data-user-close]')){closeUserSheet();const user=document.querySelector('.user-center');if(user?.open){user.open=false;user.querySelector('summary').focus();}}
});
matchMedia('(max-width:768px), (max-width:1023px) and (max-height:500px)').addEventListener('change',closeUserSheet);

function updateUtilities(fragment) {
  const template=fragment.querySelector('template[data-utility-update]');if(!template)return;
  closeUserSheet();const user=template.content.querySelector('.user-center');
  if(user)document.querySelector('.user-center')?.replaceWith(user);
  document.querySelector('.comparison-tray')?.remove();
  const tray=template.content.querySelector('.comparison-tray');if(tray)document.body.append(tray);
  document.body.classList.toggle('has-comparison',!!tray);applyTheme(themeChoice());
}
let feedbackTimer;
function announce(message,error=false){
  const status=document.querySelector('#save-status');if(!status)return;
  status.textContent=message;const feedback=document.querySelector('#save-feedback');
  feedback.hidden=!error;clearTimeout(feedbackTimer);
  if(error)feedbackTimer=setTimeout(()=>feedback.hidden=true,5000);
  // Success is discoverable without a redundant toast covering a listing.
  document.querySelector('#utility-announcement').textContent=message;
}
const utilityAnnouncement=document.createElement('p');utilityAnnouncement.id='utility-announcement';utilityAnnouncement.className='sr-only';utilityAnnouncement.setAttribute('role','status');document.body.append(utilityAnnouncement);
function closeOtherSheets(except){document.querySelectorAll('dialog[open]').forEach(dialog=>{if(dialog!==except)dialog.close();});const owner=document.querySelector('.user-center');if(owner?.open)owner.open=false;}
// Require the gesture to start AND finish on the backdrop, never inside a form.
let backdropStart;
function outsideSheet(dialog,event){const r=dialog.getBoundingClientRect();return event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom;}
document.addEventListener('pointerdown',event=>{const dialog=event.target.closest('dialog[open]');backdropStart=dialog&&event.target===dialog&&outsideSheet(dialog,event)?dialog:null;});
document.addEventListener('click',event=>{
  const dialog=event.target.closest('dialog[open]');
  if(dialog&&dialog===backdropStart&&event.target===dialog&&outsideSheet(dialog,event))dialog.close();
  backdropStart=null;
  if(event.target.closest('#mobile-menu nav a'))menu?.close();
});
// Inline contact replaces the sticky action layer while its own card is visible.
const contactCard=document.querySelector('.contact-section'),contactBar=document.querySelector('.mobile-contact');
if(contactCard&&contactBar&&'IntersectionObserver' in window){
  new IntersectionObserver(entries=>{contactBar.classList.toggle('contact-card-visible',entries[0].isIntersecting);},{threshold:0}).observe(contactCard);
}

// Reuse existing server-rendered Results; normal forms remain the no-JS fallback.
let resultsBusy=false;
async function updateResults(url,options={},historyMode=false) {
  const region=document.querySelector('[data-results-region]');if(!region||resultsBusy)return;
  resultsBusy=true;region.setAttribute('aria-busy','true');
  const active=document.activeElement;const focusId=active?.id||active?.closest('.refinement-search')?.querySelector('input:not([type=hidden])')?.id;
  const fromDialog=!!active?.closest('#advanced-filters');
  const fromSort=!!active?.closest('#sort-sheet');
  const sortHref=active?.closest('[data-results-sort]')?.getAttribute('href');
  const chipKey=active?.name==='key'?active.value:null;
  const criteriaOpen=region.querySelector('.criteria-details')?.open;
  const scrollPosition={left:scrollX,top:scrollY};
  try {
    const response=await fetch(url,{...options,headers:{...(options.headers||{}),'X-Results-Partial':'1'},cache:'no-store'});
    if(!response.ok)throw new Error();
    const fragment=new DOMParser().parseFromString(await response.text(),'text/html');
    const replacement=fragment.querySelector('[data-results-region]');
    if(!replacement){location.assign(response.url);return;}
    document.querySelector('#advanced-filters')?.close();document.querySelector('#sort-sheet')?.close();region.replaceWith(replacement);
    updateUtilities(fragment);initializeCriteria();initializeFilters();initializeSort();initializeStickySearch();
    const criteria=replacement.querySelector('.criteria-details');if(criteria&&criteriaOpen!==undefined)criteria.open=criteriaOpen;
    if(historyMode)history.pushState({results:true},'',response.url);
    if(!replacement.querySelector('#advanced-filters[open]')){
      const focus=fromSort?replacement.querySelector('[data-sort-open]'):fromDialog?replacement.querySelector('[data-advanced-open]'):focusId?document.getElementById(focusId):null;
      const sortFocus=sortHref?[...replacement.querySelectorAll('[data-results-sort]')].find(link=>link.getAttribute('href')===sortHref):null;
      const chipFocus=chipKey?replacement.querySelector('.active-filters button'):null;
      (focus||sortFocus||chipFocus||replacement.querySelector('[data-advanced-open]'))?.focus({preventScroll:true});
    }
    window.scrollTo(scrollPosition);
    const status=replacement.querySelector('[data-results-status]');if(status){const message=status.textContent;status.textContent='';requestAnimationFrame(()=>status.textContent=message);}
  }catch(_){announce('به‌روزرسانی تأیید نشد؛ دوباره تلاش کن.',true);}
  finally{resultsBusy=false;document.querySelector('[data-results-region]')?.removeAttribute('aria-busy');}
}
document.addEventListener('submit',event=>{
  const form=event.target;if(!form.closest('[data-results-region]')||form.matches('[data-save-form],[data-compare-form]'))return;
  // A canonical hidden input named "action" shadows form.action in the DOM.
  const actionUrl=new URL(form.getAttribute('action')||location.href,location.href);
  if(actionUrl.pathname!==location.pathname)return;
  event.preventDefault();const data=new FormData(form);
  if(event.submitter?.name)data.set(event.submitter.name,event.submitter.value);
  updateResults(actionUrl.href,{method:'POST',body:data});
});
document.addEventListener('click',event=>{
  const link=event.target.closest('[data-results-sort]');if(!link||event.ctrlKey||event.metaKey||event.shiftKey)return;
  event.preventDefault();updateResults(link.href,{},true);
});
window.addEventListener('popstate',()=>{if(document.querySelector('[data-results-region]'))updateResults(location.href);});
document.addEventListener('submit',async event=>{
  const form=event.target.closest('[data-compare-form]');if(!form)return;event.preventDefault();
  if(form.dataset.busy)return;form.dataset.busy='true';const button=event.submitter||form.querySelector('button');
  const compareHadFocus=form.contains(document.activeElement);
  const data=new FormData(form);if(button?.name)data.set(button.name,button.value);button.disabled=true;
  try{
    const response=await fetch(form.getAttribute('action'),{method:'POST',body:data,headers:{'X-Requested-With':'XMLHttpRequest'}});if(!response.ok)throw new Error();
    const state=await response.json();
    updateUtilities(new DOMParser().parseFromString(state.utilities,'text/html'));
    document.querySelectorAll('[data-compare-form] button[name="listing"]').forEach(b=>{
      if((!state.cleared&&b.value!==state.id)||b.closest('.comparison-tray'))return;
      b.setAttribute('aria-pressed',String(state.selected));b.classList.toggle('selected',state.selected);
      b.textContent=state.selected?'✓ انتخاب‌شده':'+ مقایسه';
    });
    announce(state.error || (state.cleared?'مقایسه پاک شد':state.selected?'خانه به مقایسه اضافه شد':'خانه از مقایسه حذف شد'),!!state.error);
    if(state.cleared&&compareHadFocus)document.querySelector('[data-advanced-open],main a')?.focus({preventScroll:true});
    if(document.querySelector('#compare-region')){
      const tableResponse=await fetch(location.href,{headers:{'X-Compare-Partial':'1'},cache:'no-store'});
      if(!tableResponse.ok)throw new Error();
      const tableFragment=new DOMParser().parseFromString(await tableResponse.text(),'text/html');
      const table=tableFragment.querySelector('#compare-region');
      if(!table)throw new Error();
      const oldTable=document.querySelector('.comparison-scroll'),tableScroll=oldTable?.scrollLeft;
      document.querySelector('#compare-region').replaceWith(table);
      const scroll=table.querySelector('.comparison-scroll');if(scroll){scroll.scrollLeft=tableScroll||0;scroll.focus({preventScroll:true});}
      else table.querySelector('.primary')?.focus({preventScroll:true});
    }
  }catch(_){announce('تغییر مقایسه تأیید نشد؛ دوباره تلاش کن.',true);}
  finally{delete form.dataset.busy;button.disabled=false;if(compareHadFocus&&button.isConnected)button.focus({preventScroll:true});}
});

// Sort uses the existing server-rendered values and Results partial response.
let sortOpener;
function initializeSort(){
  const sheet=document.querySelector('#sort-sheet');if(!sheet||sheet.dataset.bound)return;
  sheet.dataset.bound='true';
  sheet.addEventListener('close',()=>{sortOpener?.setAttribute('aria-expanded','false');if(sortOpener?.isConnected)sortOpener.focus({preventScroll:true});});
}
document.addEventListener('click',event=>{
  const opener=event.target.closest('[data-sort-open]');
  if(opener){const sheet=document.querySelector('#sort-sheet');if(!sheet)return;closeOtherSheets(sheet);sortOpener=opener;sheet.showModal();opener.setAttribute('aria-expanded','true');sheet.querySelector('[aria-current]')?.focus();}
  if(event.target.closest('[data-sort-close]'))document.querySelector('#sort-sheet')?.close();
});
initializeSort();
// One form, one sticky system. Reserve its reduced height to avoid moving cards.
let searchObserver;
const desktopSearch=matchMedia('(min-width:1024px)');
function initializeStickySearch(){
  searchObserver?.disconnect();
  const form=document.querySelector('.refinement-search'),sentinel=document.querySelector('.search-sticky-sentinel'),space=document.querySelector('.search-sticky-space');
  if(!form||!sentinel||!space)return;
  form.classList.remove('search-sticky-ready','is-compact');space.style.height='0px';
  if(!desktopSearch.matches||!('IntersectionObserver' in window))return;
  const fullHeight=form.getBoundingClientRect().height;
  const compactHeight=parseFloat(getComputedStyle(form).getPropertyValue('--compact-search-height'));
  if(!Number.isFinite(compactHeight))return;
  const reservedHeight=Math.max(0,fullHeight-compactHeight);
  form.classList.add('search-sticky-ready');
  let compactState=false;
  searchObserver=new IntersectionObserver(entries=>{
    const compact=!entries[0].isIntersecting&&entries[0].boundingClientRect.top<0;
    if(compact===compactState)return;
    compactState=compact;
    // Update both heights together, without forcing layout between the writes.
    // A layout read after shrinking can trigger scroll anchoring and re-cross
    // this sentinel repeatedly, producing flashing and a stuck scroll position.
    space.style.height=compact?reservedHeight+'px':'0px';
    form.classList.toggle('is-compact',compact);
  },{threshold:0});
  searchObserver.observe(sentinel);
}
desktopSearch.addEventListener('change',initializeStickySearch);
initializeStickySearch();
