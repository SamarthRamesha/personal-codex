// Only the app-owned, already-bound loopback socket can be used for preview listening.
'use strict';
const net = require('node:net');
const listen = net.Server.prototype.listen;
let claimed = false;
const fd = Number(process.env.PERSONAL_CODEX_LISTEN_FD);
if (!Number.isSafeInteger(fd) || fd < 3) throw new Error('Missing owned preview listener');
Object.defineProperty(net.Server.prototype, 'listen', {configurable:false, writable:false, value:function(...args) {
  if (claimed) throw new Error('Only one approved preview listener is available');
  claimed = true;
  const callback = typeof args[args.length-1] === 'function' ? args[args.length-1] : undefined;
  return listen.call(this, {fd, exclusive:true}, callback);
}});
