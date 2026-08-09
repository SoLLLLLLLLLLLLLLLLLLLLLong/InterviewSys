# 🎤 Live2D Lip Sync Integration Guide

Bring the Live2D sample model to life by driving its mouth movement from an audio file. This doc walks through the pieces you need and explains how the snippets fit together.

---

## Prerequisites

- The demo already depends on `three`. If you copied these files into another project, install it first:

```powershell
npm install three
```

- Run the Vite dev server from the project root:

```powershell
npm install
npm run dev
```

---

## 1. Vue Entry Point (`src/components/live2d.vue`)

This component bridges Vue and the Cubism runtime. It grabs a canvas ref, initializes WebGL, and kicks off the main update loop—without it `LAppModel.update()` never fires.

```vue
<template>
  <div class="live2d-container">
    <canvas ref="canvasRef" id="live2d-canvas"></canvas>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { LAppDelegate } from '../live2d/src/lappdelegate';
import { LAppGlManager } from '../live2d/src/lappglmanager';

const canvasRef = ref<HTMLCanvasElement | null>(null);
let glManager: LAppGlManager | null = null;
let appDelegate: LAppDelegate | null = null;

onMounted(() => {
  if (!canvasRef.value) {
    console.error('Canvas element not found');
    return;
  }

  glManager = new LAppGlManager();
  if (!glManager.initialize(canvasRef.value)) {
    console.error('Failed to initialize WebGL');
    return;
  }

  appDelegate = LAppDelegate.getInstance();
  if (!appDelegate.initialize()) {
    console.error('Failed to initialize LAppDelegate');
    return;
  }

  appDelegate.run();
});

onBeforeUnmount(() => {
  if (appDelegate) {
    LAppDelegate.releaseInstance();
    appDelegate = null;
  }

  if (glManager) {
    glManager.release();
    glManager = null;
  }
});
</script>
```

---

## 2. Audio Analysis (`src/live2d/src/genericaudiofilehandler.ts`)

We wrap Three.js’ `AudioAnalyser` so we can sample amplitude every frame and keep a normalized value ready for the model.

```ts
import * as THREE from 'three';

export class GenericAudioFileHandler {
  private _threeAudioAnalyser: THREE.AudioAnalyser | null = null;
  private _normalizedAverageFrequency = 0;

  public start(audioPath: string): void {
    const listener = new THREE.AudioListener();
    const audio = new THREE.Audio(listener);
    const mediaElement = new Audio(audioPath);

    mediaElement.crossOrigin = 'anonymous';
    mediaElement.play();

    audio.setMediaElementSource(mediaElement);
    this._threeAudioAnalyser = new THREE.AudioAnalyser(audio, 128);
  }

  public update(): void {
    if (!this._threeAudioAnalyser) {
      this._normalizedAverageFrequency = 0;
      return;
    }

    const raw = this._threeAudioAnalyser.getAverageFrequency();
    this._normalizedAverageFrequency = Math.min(raw / 100, 1);
  }

  public getNormalizedAverageFrequency(): number {
    return this._normalizedAverageFrequency;
  }
}
```

**Highlights**

- `start()` spins up an `<audio>` element and pipes it through Three.js.
- `update()` should be called once per frame—preferably inside your model loop.
- `getNormalizedAverageFrequency()` keeps the latest 0–1 value ready for parameter injection.

---

## 3. Trigger Playback (`src/live2d/src/lapplive2dmanager.ts`)

Hook the tap handler so touching the model loads an audio clip and begins analysis. Always guard against missing models.

```ts
public onTap(x: number, y: number): void {
  const model = this._models.at(0);
  if (!model) {
    console.warn('No model loaded for lip sync');
    return;
  }

  const filePath = '/audio/sample.wav';
  model.getGenericAudioHandler().start(filePath);
}
```

Want multiple clips? Swap out `filePath` dynamically or add UI controls for custom selections.

---

## 4. Feed the Model (`src/live2d/src/lappmodel.ts`)

The render loop is where the magic happens: pull the analyser value, then distribute it across all lip-sync parameters exposed by the model.

```ts
public update(): void {
  this._genericAudioFileHandler.update();
  const value = this._genericAudioFileHandler.getNormalizedAverageFrequency();

  // Use setParameterValueById to override all other animations (highest priority)
  for (let i = 0; i < this._lipSyncIds.getSize(); ++i) {
    this._model.setParameterValueById(this._lipSyncIds.at(i), value);
  }

  this._model.update();
}
```

- `_lipSyncIds` is populated from your model JSON (e.g., `ParamMouthOpenY`).
- **`setParameterValueById` vs `addParameterValueById`**: We use `setParameterValueById` to **completely override** any mouth movements from expressions or motions, ensuring lip sync has the **highest priority**.
- The final `this._model.update()` keeps the base Cubism animations running.

### 🎯 Priority System Explained

The Live2D update order in `lappmodel.ts` determines which animations take precedence:

```
1. Motions (idle, tap animations)
2. Eye Blink
3. Expressions (facial animations)
4. Drag (mouse/touch interaction)
5. Breath
6. Physics
7. Pose
8. LIP SYNC ← Applied LAST = Highest Priority
9. model.update() ← Final render
```

**Why lip sync is last**: By placing lip sync as the final parameter update before `model.update()`, and using `setParameterValueById` (which overwrites values rather than adding to them), we ensure that:
- ✅ Expressions cannot close the mouth
- ✅ Motions cannot override mouth position
- ✅ Audio drives the mouth movement no matter what else is playing

If you want expressions/motions to control the mouth instead, move the lip sync code earlier in the update sequence or switch back to `addParameterValueById`.

---

## 5. Audio File Placement

Place audio files under `public/audio/` so Vite serves them at `/audio/...`:

```
public/
  audio/
    sample.wav
    victory-theme.mp3
```

Testing a change is as simple as replacing `sample.wav` with your own clip.

---

## 6. End-to-End Test

1. Start the dev server with `npm run dev`.
2. Open the app and click the model.
3. You should hear the audio and see the mouth respond.
4. Open DevTools if nothing happens—missing audio files or CORS issues show up there.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| **No audio plays** | Confirm the file path, verify it lives in `public/audio`, and check for browser autoplay restrictions. |
| **Mouth doesn’t move** | Log the analyser value. If it’s always `0`, the audio isn’t playing or the analyser isn’t initialised. If `_lipSyncIds` is empty, verify your model exports lip-sync parameters. |
| **Multiple models** | Replace `this._models.at(0)` with the appropriate model or iterate over all loaded models. |

Feel free to tweak analyser smoothing, add microphone input, or trigger playback from UI buttons to fit your project.
