/**
 * This is a simple class written with Three.js which will serve the same purpose as the
 * LAppWavFileHandler, except this one can handle any audio file.
 */
import * as THREE from "three";

export class GenericAudioFileHandler {
  private _threeAudioAnalyser: THREE.AudioAnalyser | null = null;
  private _lastNormalizedAverageFrequency: number | 0;

  /**
   * Get the normalized average frequency using a quintic easing function.
   * @returns {number} Normalized average frequency.
   */
  public getNormalizedAverageFrequency(): number {
    return this._lastNormalizedAverageFrequency;
  }

  /**
   * Load an audio file and play it with Three.js, enabling frequency analysis.
   * @param {string} audioPath - Path to the audio file.
   */
  public loadAudioFile(audioPath: string): void {
    console.log('📂 [LipSync] loadAudioFile() called');
    console.log(`   Path: ${audioPath}`);

    if (!audioPath) {
      console.error('❌ [LipSync] No audio path provided!');
      return;
    }

    const fftSize = 128;
    console.log(`🔧 [LipSync] FFT Size: ${fftSize}`);

    const listener = new THREE.AudioListener();
    const audio = new THREE.Audio(listener);

    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
    console.log(`📱 [LipSync] Device type: ${isIOS ? 'iOS' : 'Desktop'}`);

    if (isIOS) {
      console.log('🍎 [LipSync] Using AudioLoader for iOS');
      const loader = new THREE.AudioLoader();
      loader.load(
        audioPath,
        (buffer: THREE.AudioBuffer) => {
          console.log('✅ [LipSync] Audio buffer loaded successfully');
          console.log(`   Duration: ${buffer.duration.toFixed(2)}s`);
          console.log(`   Sample Rate: ${buffer.sampleRate}Hz`);
          audio.setBuffer(buffer);
          audio.play();
          console.log('▶️ [LipSync] Audio playback started (iOS)');
        },
        (progress) => {
          console.log(`⏳ [LipSync] Loading: ${((progress.loaded / progress.total) * 100).toFixed(0)}%`);
        },
        (error) => {
          console.error('❌ [LipSync] Failed to load audio:', error);
        }
      );
    } else {
      console.log('🖥️ [LipSync] Using MediaElement for Desktop');
      const mediaElement = new Audio(audioPath);

      mediaElement.addEventListener('loadeddata', () => {
        console.log('✅ [LipSync] Audio loaded successfully');
        console.log(`   Duration: ${mediaElement.duration.toFixed(2)}s`);
      });

      mediaElement.addEventListener('playing', () => {
        console.log('▶️ [LipSync] Audio playback started');
      });

      mediaElement.addEventListener('error', (e) => {
        console.error('❌ [LipSync] Audio error:', e);
        console.error('   Error code:', mediaElement.error?.code);
        console.error('   Error message:', mediaElement.error?.message);
      });

      mediaElement.play()
        .then(() => {
          console.log('✅ [LipSync] Audio play() promise resolved');
        })
        .catch((error) => {
          console.error('❌ [LipSync] Audio play() failed:', error);
        });

      audio.setMediaElementSource(mediaElement);
    }

    // Initialize the audio analyser.
    this._threeAudioAnalyser = new THREE.AudioAnalyser(audio, fftSize);
    console.log('🎚️ [LipSync] AudioAnalyser initialized');
  }

  public start(filePath: string): void {
    console.log('🚀 [LipSync] start() called');
    console.log(`   Resetting analyser and frequency values`);

    this._threeAudioAnalyser = null;
    this._lastNormalizedAverageFrequency = 0;

    console.log(`   Calling loadAudioFile()...`);
    this.loadAudioFile(filePath);
  }

  public update() {
    if (!this._threeAudioAnalyser) {
      // Only log occasionally to avoid spam
      if (Math.random() < 0.01) {
        console.warn('⚠️ [LipSync] update() called but analyser not initialized');
      }
      return 0;
    }

    // Linear normalization (no easing) for maximum lip sync response
    const normalize = (value: number, min = 0, max = 100): number => {
      return (value - min) / (max - min);
    };

    const rawFrequency = this._threeAudioAnalyser.getAverageFrequency();
    const currentAverageFreq = normalize(rawFrequency);

    this._lastNormalizedAverageFrequency = currentAverageFreq;

    return true;
  }

  constructor() {
    this._threeAudioAnalyser = null;
    this._lastNormalizedAverageFrequency = 0;
  }
}
