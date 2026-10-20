// The live page's connection and sound (spec 15.10, The live page, The
// recording; 15.9 ruling 7; 11.5 rule 3). The microphone is opened with
// echo cancellation, noise suppression and automatic gain all off; the
// values the browser applied and the session's rate go to the app first;
// then 16-bit PCM at that rate, in pieces of a quarter of a second, on
// the socket. The state the app sends is handed to the table of handlers
// in panels.js; no state is worked out here. Stop is a form post: the
// microphone is stopped first, and the post acts with or without the
// socket.
(function () {
  const page = document.getElementById('live');
  if (!page) return;
  const WORDS = JSON.parse(document.getElementById('words').textContent);
  const consultationId = Number(page.dataset.consultation);
  const pieceSeconds = Number(page.dataset.pieceSeconds);
  const render = window.panels ? window.panels.render : function () {};
  const note = document.getElementById('connection');
  let socket = null;
  let stopped = false;
  let queue = new Int16Array(0);
  let opened = false;

  function say(text) { if (note) note.textContent = text || ''; }

  function connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    socket = new WebSocket(proto + '://' + location.host + '/consultations/' + consultationId + '/sound');
    socket.binaryType = 'arraybuffer';
    socket.onopen = function () { say(opened ? WORDS.SOCKET_BACK : ''); opened = true; if (window.capture) sendCapture(window.capture); };
    socket.onmessage = function (event) {
      const message = JSON.parse(event.data);
      if (message.type !== 'state') return;
      if (message.state.state !== 'live') { window.location.reload(); return; }
      render(message.state, WORDS);
    };
    socket.onclose = function () { if (stopped) return; say(WORDS.SOCKET_LOST); setTimeout(connect, 1000); };
  }

  function sendCapture(capture) {
    if (socket && socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({type: 'capture', ...capture}));
  }

  function sendPiece(samples) {
    if (socket && socket.readyState === WebSocket.OPEN) socket.send(samples.buffer);
  }

  function toInt16(float32) {
    const out = new Int16Array(float32.length);
    for (let i = 0; i < float32.length; i++) {
      const s = Math.max(-1, Math.min(1, float32[i]));
      out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return out;
  }

  function enqueue(samples, pieceSamples) {
    const joined = new Int16Array(queue.length + samples.length);
    joined.set(queue); joined.set(samples, queue.length);
    queue = joined;
    while (queue.length >= pieceSamples) {
      sendPiece(queue.slice(0, pieceSamples));
      queue = queue.slice(pieceSamples);
    }
  }

  async function startMicrophone() {
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({audio: {
        channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false}});
    } catch (error) {
      say(WORDS.MIC_REFUSED.replace('{reason}', error && error.message ? error.message : String(error)));
      return;
    }
    const context = new AudioContext();
    if (context.state === 'suspended') await context.resume();
    const applied = stream.getAudioTracks()[0].getSettings();
    window.capture = {
      echo_cancellation: 'echoCancellation' in applied ? applied.echoCancellation : null,
      noise_suppression: 'noiseSuppression' in applied ? applied.noiseSuppression : null,
      auto_gain: 'autoGainControl' in applied ? applied.autoGainControl : null,
      rate: context.sampleRate,
    };
    sendCapture(window.capture);
    await context.audioWorklet.addModule('/static/recorder-worklet.js');
    const worklet = new AudioWorkletNode(context, 'pcm-forwarder');
    const pieceSamples = Math.round(context.sampleRate * pieceSeconds);
    worklet.port.onmessage = function (event) { if (!stopped) enqueue(toInt16(event.data), pieceSamples); };
    context.createMediaStreamSource(stream).connect(worklet);
    window.stopMicrophone = function () {
      stopped = true;
      worklet.disconnect();
      stream.getTracks().forEach(function (track) { track.stop(); });
    };
  }

  const stopForm = document.getElementById('stop-form');
  if (stopForm) stopForm.addEventListener('submit', function () {
    if (window.stopMicrophone) window.stopMicrophone();
    stopped = true;
    document.getElementById('stop').disabled = true;
    document.getElementById('stop').textContent = WORDS_STOPPING;
  });
  const WORDS_STOPPING = page.dataset.stopping;

  connect();
  startMicrophone();
  render(JSON.parse(document.getElementById('state').textContent), WORDS);
})();
