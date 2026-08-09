# Live2D Background Customization Guide

You can control the scene behind your Cubism model in three different layers:

1. **WebGL clear color** (solid/transparent background inside the canvas)
2. **Background sprite** (textured quad rendered behind the model)
3. **Vue container styles** (CSS around the canvas element)

Mix and match these options to build green-screen setups, custom stills, or fully transparent overlays.

---

## 1. WebGL Clear Color (Green Screen & Solid Colors)

The WebGL clear color fills every pixel before sprites or the model are drawn. Update `gl.clearColor(...)` in `src/live2d/src/lappsubdelegate.ts` to choose any RGBA value between `0` and `1`.

```ts
// src/live2d/src/lappsubdelegate.ts
// ...existing code...

// Fill the canvas before drawing sprites/models
const greenKey = [0.0, 1.0, 0.0, 1.0]; // pure green
// gl.clearColor(R, G, B, A)
gl.clearColor(greenKey[0], greenKey[1], greenKey[2], greenKey[3]);

// Optional: enable transparent alpha channel for compositing
// gl.clearColor(0.0, 0.0, 0.0, 0.0);

// ...existing code...
```

**Tips**

- Use `[0, 1, 0, 1]` for a chroma-green key.
- Use `[0, 0, 0, 0]` for full transparency (make sure the consumer supports alpha).
- Call `gl.clearColor` before `gl.clear` in the render loop so the change applies every frame.

---

## 2. Background Sprite (Images & Gradients)

`src/live2d/src/lappview.ts` loads a textured quad behind the model. The file name comes from `LAppDefine.BackImageName`.

```ts
// src/live2d/src/lappdefine.ts
export const BackImageName = 'back_class_normal.png';
```

Place replacement images under `src/live2d/Resources/` and update `BackImageName` to point at them (relative to `ResourcesPath`). PNGs with transparency work well.

To disable the sprite entirely (useful for green screen), skip the texture creation inside `initializeSprite()`:

```ts
// src/live2d/src/lappview.ts
public initializeSprite(): void {
  // Comment/remove this block to stop loading the background image
  // textureManager.createTextureFromPngFile(
  //   resourcesPath + LAppDefine.BackImageName,
  //   false,
  //   initBackGroundTexture
  // );

  // Still create the shader so models render correctly
  if (this._programId == null) {
    this._programId = this._subdelegate.createShader();
  }
}
```

Remove or replace the gear sprite (`GearImageName`) the same way to keep the canvas clean for compositing.

---

## 3. Vue Container Styling (Canvas Frame)

Outside the WebGL context, `src/components/live2d.vue` controls the wrapper styles. For example:

```css
/* src/components/live2d.vue */
.live2d-container {
  background: radial-gradient(circle, #0f0 0%, #033 100%);
}
```

This layer won’t appear if your canvas is fully opaque, but it’s handy when `gl.clearColor` has an alpha < 1.

---

## Recommended Configurations

| Scenario | WebGL Clear Color | Sprite | Container CSS |
| --- | --- | --- | --- |
| Chroma key | `[0, 1, 0, 1]` | Disabled | Optional solid green frame |
| Full transparency | `[0, 0, 0, 0]` | Disabled | Invisible | 
| Custom static image | `[0, 0, 0, 0]` or brand color | Replacement PNG | Optional border/shadow |
| Gradient canvas | Desired RGBA | Disabled | Gradient via CSS |

---

## Testing Checklist

1. Run the dev server with `npm run dev`.
2. Apply background changes and refresh the page.
3. Capture a screenshot or video to verify chroma key edges.
4. If using transparency, confirm the downstream compositor respects the alpha channel.

With these knobs you can quickly swap between studio backgrounds, green screens, or transparent overlays tailored to your streaming setup.
