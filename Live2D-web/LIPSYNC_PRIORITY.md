# 🎤 Lip Sync Priority Implementation

## Overview

Lip sync now has **absolute priority** over all other animations (expressions, motions, pose, etc.). This ensures the character's mouth always responds to audio, regardless of what other animations are playing.

---

## Changes Made

### 1. **Changed Parameter Update Method** (`lappmodel.ts`)

**Before:**
```typescript
this._model.addParameterValueById(this._lipSyncIds.at(i), value, 1.0);
```

**After:**
```typescript
this._model.setParameterValueById(this._lipSyncIds.at(i), value);
```

**Why?**
- `addParameterValueById` **adds** to the current parameter value (relative change)
- `setParameterValueById` **overwrites** the parameter value completely (absolute value)
- Using `setParameterValueById` ensures lip sync replaces any mouth positions set by expressions/motions

---

### 2. **Reordered Update Sequence** (`lappmodel.ts`)

Lip sync is now the **last** parameter update before `model.update()`:

```typescript
public update(): void {
  // 1. Load previous state
  this._model.loadParameters();
  
  // 2. Update motions
  this._motionManager.updateMotion(this._model, deltaTimeSeconds);
  
  // 3. Save motion state
  this._model.saveParameters();
  
  // 4. Eye blink
  this._eyeBlink.updateParameters(this._model, deltaTimeSeconds);
  
  // 5. Expressions
  this._expressionManager.updateMotion(this._model, deltaTimeSeconds);
  
  // 6. Drag (mouse interaction)
  this._model.addParameterValueById(this._idParamAngleX, this._dragX * 30);
  // ... other drag parameters
  
  // 7. Breath
  this._breath.updateParameters(this._model, deltaTimeSeconds);
  
  // 8. Physics
  this._physics.evaluate(this._model, deltaTimeSeconds);
  
  // 9. Pose
  this._pose.updateParameters(this._model, deltaTimeSeconds);
  
  // 10. LIP SYNC - HIGHEST PRIORITY (LAST)
  if (this._lipsync) {
    this._genericAudioFileHandler.update();
    const value = this._genericAudioFileHandler.getNormalizedAverageFrequency();
    
    // Override all previous mouth parameter updates
    for (let i = 0; i < this._lipSyncIds.getSize(); ++i) {
      this._model.setParameterValueById(this._lipSyncIds.at(i), value);
    }
  }
  
  // 11. Final render
  this._model.update();
}
```

---

## Priority Hierarchy

From **lowest** to **highest** priority:

1. **Motions** - Base animations (idle, tap)
2. **Eye Blink** - Automatic eye blinking
3. **Expressions** - Facial expressions (smile, angry, etc.)
4. **Drag** - Mouse/touch interaction
5. **Breath** - Breathing movement
6. **Physics** - Hair/clothing physics
7. **Pose** - Body pose adjustments
8. **🎤 Lip Sync** - **HIGHEST PRIORITY** - Audio-driven mouth movement

---

## Result

✅ **Expressions cannot override lip sync** - Even if an expression sets the mouth closed, audio will open it

✅ **Motions cannot override lip sync** - Mouth animations in motion files are replaced by audio analysis

✅ **Poses cannot override lip sync** - Pose constraints don't affect mouth during speech

✅ **Real-time audio responsiveness** - Mouth immediately reflects audio input

---

## Testing

1. Play an audio file with the "Play Audio" button in settings
2. Trigger an expression (e.g., "smile") while audio is playing
3. The mouth should still move with the audio, even if the expression normally closes the mouth
4. Start a motion animation while audio is playing
5. The mouth should ignore the motion's mouth animation and follow the audio

---

## Reverting Changes

If you want expressions/motions to control the mouth instead of lip sync:

### Option 1: Lower Priority (Blend Mode)
Change back to `addParameterValueById`:
```typescript
this._model.addParameterValueById(this._lipSyncIds.at(i), value, 0.5); // 50% blend
```

### Option 2: Move Lip Sync Earlier
Place the lip sync code before expressions in the update sequence.

### Option 3: Disable Lip Sync Override
Add a flag to toggle between override and blend modes:
```typescript
if (this._lipSyncOverride) {
  this._model.setParameterValueById(this._lipSyncIds.at(i), value); // Override
} else {
  this._model.addParameterValueById(this._lipSyncIds.at(i), value, 1.0); // Blend
}
```

---

## Documentation Updates

Updated `src/live2d/LipSync.md` with:
- Explanation of `setParameterValueById` vs `addParameterValueById`
- Complete update sequence diagram
- Priority system explanation
- How to adjust priority if needed

---

## Technical Notes

- **Parameter IDs**: Lip sync typically controls `ParamMouthOpenY` and sometimes `ParamMouthForm`
- **Value Range**: 0.0 (closed) to 1.0 (fully open)
- **Audio Analysis**: Uses Three.js AudioAnalyser with FFT for frequency analysis
- **Smoothing**: Applied in `GenericAudioFileHandler` to prevent jittery movement
