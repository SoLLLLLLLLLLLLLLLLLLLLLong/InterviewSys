# Audio Files Directory

## Purpose
This directory contains audio files for Live2D lip sync functionality.

## Required Files
Place your sample audio file here with the name: **sample.mp3** (or .ogg, .wav)

## File Requirements

### Format Specifications (Method 2 - GenericAudioFileHandler)
- **Supported Formats**: MP3, OGG, WAV, and most web-compatible audio formats
- **File Type**: MP3 (.mp3) recommended for best compatibility
- **Sample Rate**: 44.1kHz or 48kHz recommended
- **Bit Depth**: Any (MP3 handles compression automatically)
- **Channels**: Mono or Stereo

### Audio Tips
1. **Volume Enhancement**: Higher volume = more pronounced mouth movements
   - Use Garageband, Audacity, or similar tools to boost volume
   - Normalize audio to maximize dynamic range

2. **Audio Sources**:
   - Amazon Polly (Text-to-Speech)
   - Record your own voice with phone/microphone
   - Convert MP3 to WAV using online converters or Audacity

3. **Quality Considerations**:
   - Clear speech with good volume works best
   - Avoid background noise
   - Consistent volume levels produce better lip sync

## Current Usage (Method 2)
The file `sample.mp3` (or any supported format) is loaded by the Live2D application when you click/tap on the model.

## File Path Reference
In code: `./src/audio/sample.mp3`

## Changing Audio File
To use a different filename or format:
1. Place your audio file in this directory
2. Update the path in `/src/live2d/src/lapplive2dmanager.ts` (line 56)
   ```typescript
   let filePath = "./src/audio/YOUR_FILENAME.mp3";  // or .ogg, .wav, etc.
   ```

## Supported Formats
✅ **MP3** (.mp3) - Recommended
✅ **OGG** (.ogg) - Good alternative
✅ **WAV** (.wav) - Uncompressed
✅ **M4A** (.m4a) - Apple format
✅ Most web-compatible audio formats

## Format Conversion
If you need to convert formats:
- **To MP3**: Use Audacity (File → Export → Export as MP3)
- **Online Converters**: CloudConvert, Online-Convert
- **FFmpeg**:
  - `ffmpeg -i input.wav output.mp3`
  - `ffmpeg -i input.ogg output.mp3`

## Testing
1. Add `sample.mp3` (or your audio file) to this directory
2. Run `npm run dev`
3. Click on the Live2D model
4. Audio should play with lip sync

## Notes
- **Method 2 (Current)**: Supports MP3, OGG, WAV, and most web-compatible formats
- **Three.js Integration**: Uses Web Audio API for frequency analysis
- **Easing Function**: easeInQuint applied for natural mouth movements
- **No HTML Audio Element**: Audio playback managed by Three.js directly
