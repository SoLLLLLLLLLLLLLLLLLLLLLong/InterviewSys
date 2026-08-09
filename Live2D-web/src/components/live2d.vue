<template>
  <div class="live2d-container">
    <canvas ref="canvasRef" id="live2d-canvas"></canvas>
    <SettingsMenu
      :availableModels="availableModels"
      :availableExpressions="availableExpressions"
      :availableMotionGroups="availableMotionGroups"
      :availableMotions="availableMotions"
      @backgroundChange="handleBackgroundChange"
      @modelPositionChange="handleModelPositionChange"
      @modelChange="handleModelChange"
      @expressionChange="handleExpressionChange"
      @randomExpression="handleRandomExpression"
      @playAudio="handlePlayAudio"
      @playMotion="handlePlayMotion"
      @randomMotion="handleRandomMotion"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { LAppDelegate } from "../live2d/src/lappdelegate";
import { LAppGlManager } from "../live2d/src/lappglmanager";
import * as LAppDefine from "../live2d/src/lappdefine";
import SettingsMenu from './SettingsMenu.vue';
import type { BackgroundMode } from '../live2d/src/lappbackgroundmanager';

// Background settings interface
interface BackgroundSettings {
  mode: BackgroundMode;
  color?: string;
  rgbSpeed?: number;
}

// Model position interface
interface ModelPosition {
  x: number;
  y: number;
  scale: number;
}

// Canvas reference
const canvasRef = ref<HTMLCanvasElement | null>(null);

// Available models from LAppDefine
const availableModels = LAppDefine.ModelDir;

// Available expressions (updated when model loads)
const availableExpressions = ref<string[]>([]);

// Available motion groups (updated when model loads)
const availableMotionGroups = ref<string[]>([]);

// Available motions with details (updated when model loads)
const availableMotions = ref<Array<{ group: string; index: number; name: string }>>([]);

// Live2D instances
let glManager: LAppGlManager | null = null;
let appDelegate: LAppDelegate | null = null;

// Initialize Live2D when component is mounted
onMounted(() => {
  if (!canvasRef.value) {
    console.error('Canvas element not found');
    return;
  }

  // Create GL Manager instance and initialize with canvas
  glManager = new LAppGlManager();

  if (!glManager.initialize(canvasRef.value)) {
    console.error('Failed to initialize WebGL');
    return;
  }

  // Initialize App Delegate
  appDelegate = LAppDelegate.getInstance();
  if (!appDelegate.initialize()) {
    console.error('Failed to initialize LAppDelegate');
    return;
  }

  // Run the application
  appDelegate.run();

  // Load expressions after model is initialized
  setTimeout(() => {
    const subdelegate = (appDelegate as any)._subdelegates?.at(0);
    if (subdelegate) {
      availableExpressions.value = subdelegate.getExpressionNames();
      availableMotionGroups.value = subdelegate.getMotionGroupNames();
      availableMotions.value = subdelegate.getAllMotions();
    }
  }, 1000);
});

// Handle background settings change from SettingsMenu
const handleBackgroundChange = (settings: BackgroundSettings) => {
  if (!appDelegate) {
    console.warn('AppDelegate not initialized yet');
    return;
  }

  // Get the first subdelegate (we only have one canvas)
  const subdelegate = (appDelegate as any)._subdelegates?.at(0);

  if (!subdelegate) {
    console.error('Failed to get subdelegate instance');
    return;
  }

  // Apply background settings
  subdelegate.setBackgroundMode(settings.mode);

  if (settings.mode === 'solid' && settings.color) {
    subdelegate.setBackgroundColor(settings.color);
  }

  if (settings.mode === 'rgb' && settings.rgbSpeed !== undefined) {
    subdelegate.setRgbSpeed(settings.rgbSpeed);
  }

  console.log('Background settings applied:', settings);
};

// Handle model position change from SettingsMenu
const handleModelPositionChange = (position: ModelPosition) => {
  if (!appDelegate) {
    console.warn('AppDelegate not initialized yet');
    return;
  }

  // Get the first subdelegate (we only have one canvas)
  const subdelegate = (appDelegate as any)._subdelegates?.at(0);

  if (!subdelegate) {
    console.error('Failed to get subdelegate instance');
    return;
  }

  // Apply model position and scale
  subdelegate.setModelPosition(position.x, position.y);
  subdelegate.setModelScale(position.scale);

  console.log('Model transform applied:', position);
};

// Handle model change from SettingsMenu
const handleModelChange = (modelIndex: number) => {
  if (!appDelegate) {
    console.warn('AppDelegate not initialized yet');
    return;
  }

  // Get the first subdelegate (we only have one canvas)
  const subdelegate = (appDelegate as any)._subdelegates?.at(0);

  if (!subdelegate) {
    console.error('Failed to get subdelegate instance');
    return;
  }

  // Change the model
  subdelegate.changeModel(modelIndex);

  console.log('Model changed to index:', modelIndex);

  // Reload expressions after model change
  setTimeout(() => {
    availableExpressions.value = subdelegate.getExpressionNames();
    availableMotionGroups.value = subdelegate.getMotionGroupNames();
    availableMotions.value = subdelegate.getAllMotions();
  }, 1000);
};

// Handle expression change from SettingsMenu
const handleExpressionChange = (expressionName: string) => {
  if (!appDelegate) {
    console.warn('AppDelegate not initialized yet');
    return;
  }

  // Get the first subdelegate (we only have one canvas)
  const subdelegate = (appDelegate as any)._subdelegates?.at(0);

  if (!subdelegate) {
    console.error('Failed to get subdelegate instance');
    return;
  }

  // Set expression
  subdelegate.setExpression(expressionName);

  console.log('Expression changed to:', expressionName);
};

// Handle random expression from SettingsMenu
const handleRandomExpression = () => {
  if (!appDelegate) {
    console.warn('AppDelegate not initialized yet');
    return;
  }

  // Get the first subdelegate (we only have one canvas)
  const subdelegate = (appDelegate as any)._subdelegates?.at(0);

  if (!subdelegate) {
    console.error('Failed to get subdelegate instance');
    return;
  }

  // Set random expression
  subdelegate.setRandomExpression();

  console.log('Random expression triggered');
};

// Handle audio playback with lip sync from SettingsMenu
const handlePlayAudio = () => {
  if (!appDelegate) {
    console.warn('AppDelegate not initialized yet');
    return;
  }

  // Get the first subdelegate (we only have one canvas)
  const subdelegate = (appDelegate as any)._subdelegates?.at(0);

  if (!subdelegate) {
    console.error('Failed to get subdelegate instance');
    return;
  }

  // Play audio with lip sync
  subdelegate.playAudioWithLipSync();

  console.log('Audio playback triggered from settings menu');
};

// Handle motion playback from SettingsMenu
const handlePlayMotion = (group: string, index: number) => {
  if (!appDelegate) {
    console.warn('AppDelegate not initialized yet');
    return;
  }

  const subdelegate = (appDelegate as any)._subdelegates?.at(0);
  if (!subdelegate) {
    console.error('Failed to get subdelegate instance');
    return;
  }

  // Get the Live2D manager from subdelegate
  const live2dManager = subdelegate.getLive2DManager();
  if (!live2dManager) {
    console.error('Failed to get Live2D manager');
    return;
  }

  // Get the model
  const model = live2dManager._models?.at(0);
  if (!model) {
    console.error('No model loaded');
    return;
  }

  // Start the motion with normal priority
  model.startMotion(group, index, 2); // Priority 2 = PriorityNormal

  console.log(`Motion started: ${group}[${index}]`);
};

// Handle random motion from SettingsMenu
const handleRandomMotion = (group: string) => {
  if (!appDelegate) {
    console.warn('AppDelegate not initialized yet');
    return;
  }

  const subdelegate = (appDelegate as any)._subdelegates?.at(0);
  if (!subdelegate) {
    console.error('Failed to get subdelegate instance');
    return;
  }

  const live2dManager = subdelegate.getLive2DManager();
  if (!live2dManager) {
    console.error('Failed to get Live2D manager');
    return;
  }

  const model = live2dManager._models?.at(0);
  if (!model) {
    console.error('No model loaded');
    return;
  }

  // Start random motion from the group with normal priority
  model.startRandomMotion(group, 2); // Priority 2 = PriorityNormal

  console.log(`Random motion started from group: ${group}`);
};

// Cleanup before component unmounts
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

// Handle window resize
const handleResize = () => {
  if (LAppDefine.CanvasSize === "auto" && appDelegate) {
    appDelegate.onResize();
  }
};

// Add resize listener on mount
onMounted(() => {
  window.addEventListener('resize', handleResize);
});

// Remove resize listener on unmount
onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize);
});
</script>

<style scoped>
.live2d-container {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  position: fixed;
  top: 0;
  left: 0;
  margin: 0;
  padding: 0;
}

#live2d-canvas {
  width: 100%;
  height: 100%;
  display: block;
  margin: 0;
  padding: 0;
}
</style>
