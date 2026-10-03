const terminal = new Terminal({cols:140, rows:40, fontSize:14, fontFamily:'Consolas, "Liberation Mono", monospace', cursorBlink:true, scrollback:3000, theme:{background:'#000000'}});
terminal.open(document.getElementById('terminal'));
const status = document.getElementById('status');
const socket = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws`);
socket.binaryType = 'arraybuffer';
socket.onopen = () => {status.textContent='Connected'; terminal.focus();};
socket.onmessage = event => terminal.write(new Uint8Array(event.data));
socket.onclose = () => {status.textContent='Disconnected — reload to reconnect';};
socket.onerror = () => {status.textContent='Connection failed';};
function send(value) {if(socket.readyState === WebSocket.OPEN) socket.send(value); terminal.focus();}
terminal.onData(send);
document.querySelectorAll('[data-key]').forEach(button => button.onclick = () => {
  if(button.dataset.confirm && !confirm(button.dataset.confirm)) return;
  send(JSON.parse('"' + button.dataset.key + '"'));
});
