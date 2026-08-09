# Other Cool Live2D Tricks

A quick grab bag of interaction hooks you can wire into the Vue VTuber overlay.

---

## Motion choreography

### Using the Settings Menu (NEW!)
The built-in settings menu now includes motion controls:
- Select a motion group from the dropdown (e.g., `Idle`, `TapBody`)
- Click **▶️ Play Motion** to trigger the first motion in that group
- Click **🎲 Random Motion** to play a random motion from the selected group

### Programmatic Control
- Each Cubism motion group (e.g. `Idle`, `TapBody`) can be triggered manually.
- Use `startMotion(group, index, priority)` or `startRandomMotion(group, priority)` for emotes, greetings, or loops.
- Motion callbacks (`beganMotion`, `finishedMotion`) are exposed in `lapplive2dmanager.ts`; chain expressions, voice lines, or camera moves when a motion starts/ends.

**Priority levels:**
- `0` = None
- `1` = Idle (lowest)
- `2` = Normal
- `3` = Force (highest, interrupts everything)

## Expression palette
- `setExpression(expressionId)` blends facial expressions over the current body motion.
- Create quick reactions by mapping chat events or sentiment analysis to expression IDs.
- `setRandomExpression()` picks any loaded expression for variety.

## Hit areas & gestures
- Use `hitTest('Head' | 'Body', x, y)` to detect taps on specific model parts.
- Route tap hits to different voice lines, motions, or particle effects.
- Drag offsets (`_dragX`, `_dragY`) already power head and eye tracking—remap them for prop movement or background parallax.

## Audio-driven dynamics
- `GenericAudioFileHandler` provides a normalised 0–1 amplitude value each frame.
- Besides mouth animation, apply that value to idle motion weights, accessory sway, or shader uniforms for reactive VFX.
- Pair analyser spikes with motion triggers to kick off hype animations when the VO gets loud.

## Background & multi-avatar setups
- Mix chroma-key green screen, static textures, or video-style quads via `Background.md` instructions.
- Increase `CanvasNum` in `lappdefine.ts` to render multiple avatars simultaneously—each has its own subdelegate.
- Hide the default gear sprite to keep the canvas clean for compositing.

## Scene swapping
- `ModelDir` array controls available avatars; call `nextScene()` or build a custom selector to swap models mid-stream.
- Preload motions/expressions for all active models so transitions stay seamless.

Drop these ideas into your Vue components or API callbacks to build a lively, interactive VTuber experience.
