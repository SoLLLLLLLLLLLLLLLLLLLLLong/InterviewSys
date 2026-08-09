# Live2D Model Configuration Guide

This guide explains how to structure your `.model3.json` file to ensure expressions and motions work properly with the VTuber application.

---

## File Structure Overview

The `.model3.json` file is the main configuration file for your Live2D Cubism model. It defines all the assets and settings needed to render and animate your character.

---

## Essential Sections

### 1. Expressions

Expressions are facial animations that can be triggered to show emotions. They must be defined in the `FileReferences.Expressions` array.

```json
{
  "Version": 3,
  "FileReferences": {
    "Expressions": [
      {
        "Name": "F01",
        "File": "expressions/F01.exp3.json"
      },
      {
        "Name": "F02",
        "File": "expressions/F02.exp3.json"
      },
      {
        "Name": "Happy",
        "File": "expressions/happy.exp3.json"
      },
      {
        "Name": "Sad",
        "File": "expressions/sad.exp3.json"
      }
    ]
  }
}
```

**Requirements:**
- Each expression needs a unique `Name` (this appears in the settings menu)
- `File` path is relative to the model directory
- Expression files must be `.exp3.json` format created in Live2D Cubism Editor

**Naming Tips:**
- Use descriptive names like "Happy", "Sad", "Angry", "Surprised"
- Or use codes like "F01", "F02", etc. for organization
- Names appear as-is in the settings dropdown

---

### 2. Motions

Motions are body animations organized into groups. They are defined in the `FileReferences.Motions` object.

```json
{
  "FileReferences": {
    "Motions": {
      "Idle": [
        {
          "File": "motions/idle_01.motion3.json",
          "FadeInTime": 0.5,
          "FadeOutTime": 0.5
        },
        {
          "File": "motions/idle_02.motion3.json",
          "FadeInTime": 0.5,
          "FadeOutTime": 0.5
        }
      ],
      "TapBody": [
        {
          "File": "motions/tap_reaction_01.motion3.json",
          "FadeInTime": 0.5,
          "FadeOutTime": 0.5,
          "Sound": "sounds/voice_01.wav"
        },
        {
          "File": "motions/tap_reaction_02.motion3.json",
          "FadeInTime": 0.3,
          "FadeOutTime": 0.3,
          "Sound": "sounds/voice_02.wav"
        }
      ],
      "Wave": [
        {
          "File": "motions/wave_hello.motion3.json",
          "FadeInTime": 0.4,
          "FadeOutTime": 0.4
        }
      ],
      "Dance": [
        {
          "File": "motions/dance_01.motion3.json",
          "FadeInTime": 0.5,
          "FadeOutTime": 0.5
        }
      ]
    }
  }
}
```

**Motion Groups:**
- Group names (like "Idle", "TapBody") organize related animations
- Each group can contain multiple motion variations
- The app will show individual motions in the format: `[GroupName] filename`

**Motion Properties:**
- `File`: Path to the `.motion3.json` file (relative to model directory)
- `FadeInTime`: Seconds to blend into this motion (optional, default: 0.5)
- `FadeOutTime`: Seconds to blend out of this motion (optional, default: 0.5)
- `Sound`: Optional audio file to play with the motion

**Common Group Names:**
- `Idle`: Loop animations when character is not doing anything
- `TapBody`: Reactions when tapping the character's body
- `TapHead`: Reactions when tapping the character's head (if hit areas defined)
- Custom names: You can use any name like "Greeting", "Surprised", "Victory", etc.

---

### 3. Groups (Parameter Settings)

These define which model parameters are used for automatic features:

```json
{
  "Groups": [
    {
      "Target": "Parameter",
      "Name": "EyeBlink",
      "Ids": [
        "ParamEyeLOpen",
        "ParamEyeROpen"
      ]
    },
    {
      "Target": "Parameter",
      "Name": "LipSync",
      "Ids": [
        "ParamMouthOpenY"
      ]
    }
  ]
}
```

**EyeBlink Group:**
- Controls automatic eye blinking
- Usually includes left and right eye parameters

**LipSync Group:**
- Controls mouth movement for speech
- Essential for the audio-driven lip sync feature
- Typically uses `ParamMouthOpenY` or similar mouth parameters

---

## Complete Example

Here's a minimal but complete `.model3.json` example:

```json
{
  "Version": 3,
  "FileReferences": {
    "Moc": "MyModel.moc3",
    "Textures": [
      "textures/texture_00.png"
    ],
    "Physics": "MyModel.physics3.json",
    "Expressions": [
      {
        "Name": "Happy",
        "File": "expressions/happy.exp3.json"
      },
      {
        "Name": "Sad",
        "File": "expressions/sad.exp3.json"
      }
    ],
    "Motions": {
      "Idle": [
        {
          "File": "motions/idle.motion3.json",
          "FadeInTime": 0.5,
          "FadeOutTime": 0.5
        }
      ],
      "Greeting": [
        {
          "File": "motions/hello.motion3.json",
          "FadeInTime": 0.5,
          "FadeOutTime": 0.5
        }
      ]
    }
  },
  "Groups": [
    {
      "Target": "Parameter",
      "Name": "EyeBlink",
      "Ids": ["ParamEyeLOpen", "ParamEyeROpen"]
    },
    {
      "Target": "Parameter",
      "Name": "LipSync",
      "Ids": ["ParamMouthOpenY"]
    }
  ]
}
```

---

## Troubleshooting

### Expressions Not Showing
- Check that expression files exist in the specified paths
- Verify the `Name` field is unique for each expression
- Ensure `.exp3.json` files are valid Cubism expression files

### Motions Not Playing
- Confirm motion files exist at the specified paths
- Check that motion group names don't have typos
- Verify `.motion3.json` files are valid Cubism motion files
- Look at browser console for file loading errors

### Lip Sync Not Working
- Ensure the `LipSync` group is defined in `Groups`
- Check that the parameter IDs match your model's mouth parameters
- Verify audio files are accessible from `public/audio/` directory

---

## Directory Structure

Your model folder should look like this:

```
MyModel/
├── MyModel.model3.json       ← Main configuration
├── MyModel.moc3               ← Compiled model
├── MyModel.physics3.json      ← Physics settings
├── textures/
│   └── texture_00.png
├── expressions/
│   ├── happy.exp3.json
│   ├── sad.exp3.json
│   └── ...
├── motions/
│   ├── idle.motion3.json
│   ├── hello.motion3.json
│   └── ...
└── sounds/                    ← Optional
    ├── voice_01.wav
    └── ...
```

---

## Tips for Best Results

1. **Expression Names**: Use descriptive, user-friendly names - they appear directly in the UI
2. **Motion Groups**: Organize motions logically (Idle, Reactions, Emotes, etc.)
3. **Fade Times**: Keep between 0.3-0.5 seconds for smooth transitions
4. **File Paths**: Always use forward slashes `/` even on Windows
5. **Testing**: After updating the JSON, refresh the browser and check the settings menu
6. **File Names**: Motion filenames will appear in the UI, so use clear names like `wave_hello` instead of `m01`

---

## Adding Your Model to the App

1. **Place your model folder** in `src/live2d/Resources/`
   
   Your folder structure should look like:
   ```
   src/live2d/Resources/
   ├── Haru/
   ├── Hiyori/
   └── YourModelName/    ← Your new model folder here
       ├── YourModelName.model3.json
       ├── YourModelName.moc3
       ├── textures/
       ├── expressions/
       └── motions/
   ```

2. **Update the model directory list** in `src/live2d/src/lappdefine.ts`:
   
   Find the `ModelDir` array and add your model folder name:
   ```typescript
   // モデルを配置したディレクトリ名の配列
   // ディレクトリ名とmodel3.jsonの名前を一致させておくこと
   export const ModelDir: string[] = [
     'Haru',
     'Hiyori',
     'Mark',
     'Natori',
     'Rice',
     'Mao',
     'Wanko',
     'YourModelName'  // ← Add your model folder name here
   ];
   ```

   **Important:** 
   - The folder name **must match** your `.model3.json` filename (without the extension)
   - For example: if your folder is `ANIYA/`, your model file should be `ANIYA.model3.json`
   - The name is case-sensitive

3. **Restart the dev server** (if it's running):
   ```powershell
   # Stop the server (Ctrl+C), then:
   npm run dev
   ```

4. **Select your model** from the settings menu:
   - Click the settings gear icon (top-left)
   - Go to "Model Settings" section
   - Choose your model from the "Select Model" dropdown
   - Your model will load with all its expressions and motions automatically!

Your expressions and motions will automatically appear in the settings panel!
