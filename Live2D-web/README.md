# Live2D Vue AI VTuber Demo

Interactive Live2D avatar built with Vue 3 and Vite. The project ships with Cubism SDK 5 for rendering, Three.js for FFT-based lip sync, and scaffolding to stream audio returned from an AI voice API—perfect for a lightweight VTuber overlay.

---

## ✨ Highlights

- **Live2D Cubism 5 rendering** with the official Web SDK
- **API-driven voice playback** – fetch audio blobs from any REST endpoint and animate the model’s mouth in sync
- **Hot-swappable models & backgrounds** – drag in new Cubism assets or switch to chroma-key green screen
- **Responsive Vue component** (`live2d.vue`) with resize handling and multi-canvas support
- **Developer-friendly docs** covering lip sync, background tweaks, and audio plumbing

---

## 🧱 Architecture at a Glance

```
Vue (Vite) UI
├── src/components/live2d.vue         # Mounts and runs the Cubism runtime
├── src/live2d/src/*                  # LApp* classes (delegate, view, model, manager)
│   ├── genericaudiofilehandler.ts    # Three.js AudioAnalyser glue
│   ├── lapplive2dmanager.ts          # Input handling + audio triggers
│   └── lappview.ts                   # Background sprite, render pipeline
├── src/live2d/Resources/*           # Cubism models, textures, motions
└── public/audio/*                   # Fallback audio clips
```

Supporting guides live alongside the code:

- `src/live2d/LipSync.md` – deep dive on mouth animation
- `src/live2d/Background.md` – green screen, custom textures, transparency
- `AUDIO_SETUP_FIX.md` – notes on static asset hosting
- `TESTING_GUIDE.md` – manual QA checklist

---

## 🚀 Quick Start

### Prerequisites

- Node.js `^20.19.0` or `>=22.12.0`
- npm

### Install dependencies

```powershell
npm install
```

### Launch the dev server

```powershell
npm run dev
```

The app defaults to <http://localhost:5174>. Update `vite.config.ts` if you need a different host/port.

### Production build

```powershell
npm run build
```

Outputs live under `dist/` ready for static hosting.

---

## 🔊 Hooking in Your AI Voice API

1. **Expose an endpoint** that returns audio data (WAV/MP3/OGG). REST or WebSocket both work—just ensure CORS allows your frontend.
2. **Fetch the audio** in `lapplive2dmanager.ts` before starting playback. Example:

```ts
// src/live2d/src/lapplive2dmanager.ts
async function requestSpeech(text: string) {
  const response = await fetch(`${import.meta.env.VITE_AUDIO_API_URL}/speak`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text })
  });

  const blob = await response.blob();
  return URL.createObjectURL(blob); // Pass this to GenericAudioFileHandler
}

public async onTap(x: number, y: number): Promise<void> {
  const model = this._models.at(0);
  if (!model) return;

  const src = await requestSpeech('Hello chat!');
  model.getGenericAudioHandler().start(src);
}
```

3. **Store the endpoint** in `.env` for local dev:

```
VITE_AUDIO_API_URL=http://localhost:8000
```

4. For short latencies, prefetch phrases or stream PCM via Web Audio. `LipSync.md` covers analyser settings and normalization tweaks.

---

## 🎨 Customising the Experience

### Adding New Models

1. **Prepare your model files**: Ensure you have a Cubism SDK model with the following structure:
   ```
   <ModelName>/
   ├── <ModelName>.model3.json    # Main model file
   ├── <ModelName>.moc3            # Model data
   ├── *.png                       # Textures
   ├── motions/                    # Motion files (optional)
   └── expressions/                # Expression files (optional)
   ```

2. **Add to Resources**: Place your model folder under `src/live2d/Resources/`:
   ```
   src/live2d/Resources/
   ├── Haru/
   ├── Hiyori/
   ├── Mark/
   ├── Natori/
   └── YourNewModel/    ← Add here
   ```

3. **Register in lappdefine.ts**: Open `src/live2d/src/lappdefine.ts` and add your model folder name to the `ModelDir` array:
   ```typescript
   export const ModelDir: string[] = [
     'Haru',
     'Hiyori',
     'Mark',
     'Natori',
     'YourNewModel'  // Add your model name here
   ];
   ```

4. **Restart dev server**: If running, restart the dev server to see your new model in the settings menu dropdown.

### Other Customizations

- **Backgrounds**: Use the settings menu (top-left) to switch between solid color, RGB effect, or transparent background. See `Background.md` for technical details.
- **Audio fallback**: Place sample clips in `public/audio/` for offline demos. Paths map 1:1 to `/audio/<file>` at runtime.
- **Controls**: Default gestures allow drag (head tracking) and tap (playback trigger). Extend `onTap`/`onDrag` in `lapplive2dmanager.ts` for richer interactions.

---

## 🧪 Testing & Troubleshooting

- `npm run build` – ensures the Vite bundle succeeds
- Manual QA checklist in `TESTING_GUIDE.md`
- If lip sync is silent, log analyser values in `genericaudiofilehandler.ts` to confirm audio is flowing.
- For transparency or keying issues, verify `gl.clearColor` alpha (`Background.md`) and disable the background sprite in `lappview.ts`.

---

## 📚 Reference Docs

- [Live2D Cubism SDK for Web Docs](https://docs.live2d.com/cubism-sdk-manual/top/) – official API reference
- [Three.js Audio Analyser](https://threejs.org/docs/#api/en/audio/AudioAnalyser)
- Guide that inspired this project: *Live2D on the Web: Integrating Lip Sync for Custom Audio Files in Vue.js*

---

## 📄 Licensing Notes

- **Live2D Cubism SDK** is distributed under the [Live2D Open Software License](https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html).
- All third-party assets (models, textures, audio) remain property of their respective creators—ensure you have redistribution rights.

Happy streaming! 🎥
