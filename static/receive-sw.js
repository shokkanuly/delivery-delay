'use strict';
const CACHE='sitepulse-receiving-shell-v5';
const ASSETS=['/receive','/static/receiving.js','/static/receiving.css','/static/design/tokens.css','/static/design/mark.svg'];
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS))));
self.addEventListener('activate',event=>event.waitUntil(Promise.all([
  caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('sitepulse-receiving-shell-')&&k!==CACHE).map(k=>caches.delete(k)))),
  self.clients.claim()
])));
self.addEventListener('fetch',event=>{
  const url=new URL(event.request.url);
  // Never cache credentials, API data, private media, or other application pages.
  if(event.request.method!=='GET'||url.origin!==self.location.origin)return;
  if(url.pathname==='/receive'||(url.pathname==='/'&&event.request.mode==='navigate')){
    event.respondWith(fetch(event.request).catch(()=>caches.match('/receive')));return;
  }
  if(ASSETS.includes(url.pathname))event.respondWith(caches.match(url.pathname).then(cached=>cached||fetch(event.request)));
});
