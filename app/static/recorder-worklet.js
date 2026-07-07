// Runs on the browser's realtime audio thread: forwards every block of raw
// microphone samples (float32, at the AudioContext's sample rate) to the page.
class PCMForwarder extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (channel && channel.length) {
      this.port.postMessage(channel.slice(0));
    }
    return true; // keep processing
  }
}
registerProcessor('pcm-forwarder', PCMForwarder);
