// The microphone test of the first run (spec 7.1; 15.13, the details of run
// 9b). The browser is asked for the microphone exactly as the live page
// asks: one channel, echo cancellation, noise suppression and automatic
// gain all off, at 48,000 samples a second. The level is read here, in the
// page, and shown on the meter with its figure in words. The test is done
// when the level has been seen to move: when it has risen clearly above
// its own quiet floor. Nothing of the sound is stored and nothing is sent:
// this script opens no connection of any kind; the form it unlocks carries
// one word.
(function () {
  const box = document.getElementById('mic-test');
  const form = document.getElementById('mic-form');
  if (!box || !form) return;
  const meter = document.getElementById('mic-level');
  const figure = document.getElementById('mic-figure');
  const said = document.getElementById('mic-said');
  const ASKED_RATE = 48000;
  const RISE_DB = 15;       // the level has moved when it stands this far above the quietest it has been
  const LEAST_DBFS = -50;   // and is at least this loud: a floor of digital silence proves nothing by itself

  function say(text) { said.textContent = text; }

  function passed() {
    document.getElementById('mic-moved').value = 'yes';
    document.getElementById('continue').disabled = false;
    say(box.dataset.moved);
  }

  async function start() {
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({audio: {
        channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false}});
    } catch (error) {
      say(box.dataset.refused.replace('{reason}', error && error.message ? error.message : String(error)));
      return;
    }
    let context;
    try {
      context = new AudioContext({sampleRate: ASKED_RATE});
    } catch (error) {
      say(box.dataset.rate.replace('{found}', error && error.message ? error.message : String(error)));
      return;
    }
    if (context.sampleRate !== ASKED_RATE) say(box.dataset.rate.replace('{found}', String(context.sampleRate)));
    if (context.state === 'suspended') await context.resume();
    const analyser = context.createAnalyser();
    analyser.fftSize = 2048;
    context.createMediaStreamSource(stream).connect(analyser);
    const samples = new Float32Array(analyser.fftSize);
    let floor = null;
    let done = false;
    window.micTest = {readings: 0, floor: null, level: null, moved: false};   // read by a look in a browser; holds no sound
    setInterval(function () {
      analyser.getFloatTimeDomainData(samples);
      let sum = 0;
      for (let i = 0; i < samples.length; i++) sum += samples[i] * samples[i];
      const rms = Math.sqrt(sum / samples.length);
      const dbfs = rms > 0 ? 20 * Math.log10(rms) : -100;
      const level = Math.max(0, Math.min(100, Math.round(dbfs + 100)));
      meter.value = level;
      figure.textContent = String(level);
      floor = floor === null ? dbfs : Math.min(floor, dbfs);
      window.micTest.readings += 1;
      window.micTest.floor = floor;
      window.micTest.level = dbfs;
      if (!done && dbfs > LEAST_DBFS && dbfs - floor >= RISE_DB) {
        done = true;
        window.micTest.moved = true;
        passed();
      }
    }, 100);
  }

  start();
})();
