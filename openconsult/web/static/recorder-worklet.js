// Runs on the browser's audio thread: forwards every block of raw
// microphone samples (float32, at the AudioContext's own rate) to the page.
// The page turns them into 16-bit PCM at that same rate: nothing is
// resampled on the page (spec 15.9, ruling 7).
class PCMForwarder extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (channel && channel.length) {
      this.port.postMessage(channel.slice(0));
    }
    return true;
  }
}
registerProcessor('pcm-forwarder', PCMForwarder);
