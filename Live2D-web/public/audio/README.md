# Audio Files Directory (Public Folder)

## ⚠️ Important: This is the CORRECT location for audio files!

All audio files for Live2D lip sync must be placed in this `/public/audio/` directory.

---

## Current Files

✅ **sample.wav** - Default audio file (currently configured)

---

## Quick Setup

### 1. Add Your Audio File
```bash
# Place your audio file here
cp /path/to/your/audio.mp3 public/audio/sample.mp3
```

### 2. Update Code (if using different filename)
Edit `src/live2d/src/lapplive2dmanager.ts` line 57:
```typescript
let filePath = "/audio/YOUR_FILENAME.mp3";  // Must start with /
```

### 3. Restart Dev Server
```bash
npm run dev
```

---

## Supported Formats

✅ **MP3** (.mp3) - Recommended (small size, wide support)
✅ **WAV** (.wav) - Currently using (uncompressed, large)
✅ **OGG** (.ogg) - Good alternative (open format)
✅ **M4A** (.m4a) - Apple format
✅ Any browser-compatible audio format

---

## File Requirements

### General
- **Location**: Must be in `/public/audio/`
- **Path in Code**: Must use `/audio/filename.ext` (starts with `/`)
- **Naming**: Use lowercase, no spaces, simple names

### Format Specifics
- **MP3**: 128-320 kbps, 44.1kHz or 48kHz
- **WAV**: 16-bit or 24-bit PCM, 44.1kHz or 48kHz
- **OGG**: Any bitrate, Vorbis codec

### Audio Quality Tips
1. **Volume**: Louder audio = more pronounced mouth movement
2. **Clarity**: Clear speech works better than background noise
3. **Compression**: Normalize/compress for consistent levels
4. **Tools**: Use Audacity, Garageband, or Adobe Audition

---

## Why Public Folder?

### Vite Build System
- Files in `/public/` are served **as-is** from the server root
- No bundling or processing required
- Perfect for large media files (audio, video, images)

### Path Resolution
```
Physical location:  /public/audio/sample.mp3
Served from:        http://localhost:5173/audio/sample.mp3
Code path:          /audio/sample.mp3
                    ↑ Leading slash = root of server
```

### What Works vs What Doesn't
```
✅ "/audio/sample.mp3"           → Correct! (public folder)
❌ "./src/audio/sample.mp3"      → Won't work (not in build)
❌ "../audio/sample.mp3"         → Unreliable (relative paths)
❌ "audio/sample.mp3"            → Missing leading /
```

---

## File Organization

### Recommended Structure
```
public/audio/
├── sample.mp3          # Default audio file
├── greeting.mp3        # Custom greeting
├── speech_01.mp3       # First speech
├── speech_02.mp3       # Second speech
└── test.wav           # Testing audio
```

### Bad Examples (Don't Do This)
```
❌ My Audio File.mp3    → Spaces in filename
❌ Áudio.mp3           → Special characters
❌ SAMPLE.MP3          → All caps
❌ sample              → Missing extension
```

---

## Testing Your Audio

### 1. Verify File Exists
```bash
ls -la public/audio/
# Should show your audio file
```

### 2. Test Direct Access
Open in browser:
```
http://localhost:5173/audio/sample.wav
```
Should download or play the file directly.

### 3. Test in App
1. Start dev server: `npm run dev`
2. Open browser to dev server URL
3. Click/tap on the Live2D model
4. Audio should play with lip sync!

---

## Format Conversion

### Convert to MP3 (Recommended)

**Using Audacity**:
1. Open audio file
2. File → Export → Export as MP3
3. Quality: 192 kbps or higher
4. Save to `public/audio/sample.mp3`

**Using FFmpeg (Command Line)**:
```bash
# WAV to MP3
ffmpeg -i input.wav -b:a 192k public/audio/sample.mp3

# OGG to MP3
ffmpeg -i input.ogg -b:a 192k public/audio/sample.mp3

# Any format to MP3
ffmpeg -i input.* -b:a 192k public/audio/sample.mp3
```

**Online Converters**:
- CloudConvert (https://cloudconvert.com/)
- Online-Convert (https://www.online-convert.com/)
- FreeConvert (https://www.freeconvert.com/)

---

## Troubleshooting

### Audio File Not Found (404)
**Symptoms**: Browser console shows 404 error
**Solution**:
1. Verify file is in `/public/audio/` (not `/src/audio/`)
2. Check filename matches exactly (case-sensitive)
3. Restart dev server

### Audio Won't Play
**Symptoms**: No sound, no lip sync
**Solution**:
1. Check browser console for errors
2. Try different audio format (MP3 → WAV → OGG)
3. Verify file isn't corrupted (open in media player)
4. Check browser audio/autoplay permissions

### Wrong Audio Plays
**Symptoms**: Different audio plays than expected
**Solution**:
1. Check path in code matches filename
2. Clear browser cache (Ctrl+Shift+Delete)
3. Hard refresh (Ctrl+Shift+R)
4. Restart dev server

### Path Issues
**Symptoms**: "No supported source" error
**Solution**:
1. Path must start with `/` → `/audio/sample.mp3` ✅
2. Don't use `./` or `../` → `./audio/sample.mp3` ❌
3. Don't use `src/` → `src/audio/sample.mp3` ❌

---

## Performance Tips

### File Size Optimization
```
WAV:  5-10 MB/minute  → Large, uncompressed
MP3:  1-2 MB/minute   → Small, good quality (recommended)
OGG:  1-2 MB/minute   → Similar to MP3
```

**Recommendation**: Use MP3 at 192 kbps for best size/quality ratio

### Loading Performance
- Smaller files load faster
- MP3/OGG recommended over WAV
- Consider preloading for instant playback

---

## Quick Reference

### Current Setup
```
File:     /public/audio/sample.wav
Path:     /audio/sample.wav
Code:     lapplive2dmanager.ts:57
```

### To Add New Audio
```bash
# 1. Add file
cp myaudio.mp3 public/audio/myaudio.mp3

# 2. Update code (lapplive2dmanager.ts:57)
let filePath = "/audio/myaudio.mp3";

# 3. Restart
npm run dev
```

### To Use Multiple Files
```typescript
// Example: Random audio selection
const audioFiles = [
  "/audio/greeting.mp3",
  "/audio/speech_01.mp3",
  "/audio/speech_02.mp3"
];
const randomFile = audioFiles[Math.floor(Math.random() * audioFiles.length)];
this._models.at(i)._genericAudioFileHandler.start(randomFile);
```

---

## Additional Resources

- **Method 2 Documentation**: `METHOD2_README.md`
- **Audio Fix Guide**: `AUDIO_SETUP_FIX.md`
- **Testing Guide**: `TESTING_GUIDE.md`
- **Changes Summary**: `METHOD2_CHANGES.md`

---

**Ready to Use!** ✅

Just add your audio file to this directory and update the path in the code if needed.
