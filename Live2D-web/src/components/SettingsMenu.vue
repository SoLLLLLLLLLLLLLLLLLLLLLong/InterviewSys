<template>
  <div class="settings-container" @click.stop @mousedown.stop @touchstart.stop>
    <!-- Settings Icon (Top Left) -->
    <button
      class="settings-icon"
      @click.stop="toggleMenu"
      :class="{ active: isMenuOpen }"
      aria-label="Toggle settings menu"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="24"
        height="24"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.6"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path
          d="M19.14 12.94c.04-.31.06-.63.06-.94s-.02-.63-.06-.94l2.03-1.58a.5.5 0 0 0 .12-.64l-1.92-3.32a.5.5 0 0 0-.6-.22l-2.39.96a7.05 7.05 0 0 0-1.63-.94l-.36-2.54A.5.5 0 0 0 14.3 2h-3.6a.5.5 0 0 0-.49.42l-.36 2.54c-.6.24-1.16.55-1.68.94l-2.39-.96a.5.5 0 0 0-.6.22L2.26 8.48a.5.5 0 0 0 .12.64l2.03 1.58c-.04.31-.06.63-.06.94s.02.63.06.94l-2.03 1.58a.5.5 0 0 0-.12.64l1.92 3.32c.13.23.39.32.63.22l2.39-.96c.52.39 1.08.71 1.68.94l.36 2.54c.05.25.25.42.49.42h3.6c.24 0 .44-.17.49-.42l.36-2.54c.6-.24 1.16-.55 1.68-.94l2.39.96c.24.1.5.01.63-.22l1.92-3.32a.5.5 0 0 0-.12-.64l-2.03-1.58ZM12 15.5a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7Z"
        />
      </svg>
    </button>

    <!-- Settings Menu Dropdown -->
    <transition name="slide-down">
      <div v-if="isMenuOpen" class="settings-menu" @click.stop @mousedown.stop @touchstart.stop>
        <div class="menu-content">
          <h3>Background Settings</h3>

          <!-- Background Mode Selection -->
          <div class="setting-group">
            <label>Background Mode:</label>
            <select v-model="backgroundMode" @change="onBackgroundModeChange" class="select-input">
              <option value="solid">Solid Color</option>
              <option value="rgb">RGB Effect</option>
              <option value="transparent">Transparent</option>
            </select>
          </div>

          <!-- Solid Color Picker (shown when mode is 'solid') -->
          <div v-if="backgroundMode === 'solid'" class="setting-group">
            <label>Background Color:</label>
            <div class="color-picker-wrapper">
              <input
                type="color"
                v-model="backgroundColor"
                @input="onColorChange"
                class="color-input"
              />
              <input
                type="text"
                v-model="backgroundColor"
                @input="onColorChange"
                class="color-value-input"
                placeholder="#00ff00"
              />
            </div>
          </div>

          <!-- RGB Effect Speed (shown when mode is 'rgb') -->
          <div v-if="backgroundMode === 'rgb'" class="setting-group">
            <label>RGB Speed:</label>
            <div class="slider-wrapper">
              <input
                type="range"
                v-model.number="rgbSpeed"
                min="1"
                max="10"
                @input="onRgbSpeedChange"
                class="slider-input"
              />
              <span class="slider-value">{{ rgbSpeed }}</span>
            </div>
          </div>

          <!-- Model Selection -->
          <div class="setting-group">
            <h4 class="section-title">Model Settings</h4>

            <label>Select Model:</label>
            <select v-model.number="selectedModelIndex" @change="onModelChange" class="select-input">
              <option
                v-for="(model, index) in props.availableModels"
                :key="index"
                :value="index"
              >
                {{ model }}
              </option>
            </select>
          </div>

          <!-- Audio & Lip Sync Settings -->
          <div class="setting-group">
            <h4 class="section-title">Audio & Lip Sync</h4>

            <button @click="onPlayAudio" class="action-btn">
              ▶️ Play Audio with Lip Sync
            </button>
          </div>

          <!-- Model Expression Settings -->
          <div class="setting-group">
            <h4 class="section-title">Expressions</h4>

            <label>Select Expression:</label>
            <select v-model="selectedExpression" @change="onExpressionChange" class="select-input">
              <option value="">Default</option>
              <option
                v-for="expression in props.availableExpressions"
                :key="expression"
                :value="expression"
              >
                {{ expression }}
              </option>
            </select>

            <button @click="onRandomExpression" class="reset-btn">
              Random Expression
            </button>
          </div>

          <!-- Motion Settings -->
          <div class="setting-group">
            <h4 class="section-title">Motions</h4>

            <label>Select Motion:</label>
            <select v-model="selectedMotion" @change="onMotionSelectionChange" class="select-input">
              <option value="">Select Motion</option>
              <option
                v-for="motion in props.availableMotions"
                :key="`${motion.group}_${motion.index}`"
                :value="JSON.stringify(motion)"
              >
                {{ motion.name }}
              </option>
            </select>

            <button 
              @click="onPlaySelectedMotion" 
              :disabled="!selectedMotion"
              class="action-btn"
              :class="{ disabled: !selectedMotion }"
            >
              ▶️ Play Selected Motion
            </button>

            <div class="motion-group-controls">
              <label>Quick Actions by Group:</label>
              <select v-model="selectedMotionGroup" class="select-input">
                <option value="">Select Group</option>
                <option
                  v-for="group in props.availableMotionGroups"
                  :key="group"
                  :value="group"
                >
                  {{ group }}
                </option>
              </select>

              <button 
                @click="onRandomMotion" 
                :disabled="!selectedMotionGroup"
                class="reset-btn"
                :class="{ disabled: !selectedMotionGroup }"
              >
                🎲 Random from {{ selectedMotionGroup || 'Group' }}
              </button>
            </div>
          </div>

          <!-- Model Position Settings -->
          <div class="setting-group">
            <h4 class="section-title">Model Transform</h4>

            <!-- X Position -->
            <label>X Position:</label>
            <div class="slider-wrapper">
              <input
                type="range"
                v-model.number="modelX"
                min="-2"
                max="2"
                step="0.1"
                @input="onModelPositionChange"
                class="slider-input"
              />
              <span class="slider-value">{{ modelX.toFixed(1) }}</span>
            </div>

            <!-- Y Position -->
            <label>Y Position:</label>
            <div class="slider-wrapper">
              <input
                type="range"
                v-model.number="modelY"
                min="-2"
                max="2"
                step="0.1"
                @input="onModelPositionChange"
                class="slider-input"
              />
              <span class="slider-value">{{ modelY.toFixed(1) }}</span>
            </div>

            <!-- Scale -->
            <label>Scale:</label>
            <div class="slider-wrapper">
              <input
                type="range"
                v-model.number="modelScale"
                min="0.5"
                max="2"
                step="0.1"
                @input="onModelPositionChange"
                class="slider-input"
              />
              <span class="slider-value">{{ modelScale.toFixed(1) }}</span>
            </div>

            <!-- Reset Button -->
            <button @click="resetModelPosition" class="reset-btn">
              Reset Transform
            </button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';

// Emits for parent component communication
const emit = defineEmits<{
  (e: 'backgroundChange', settings: BackgroundSettings): void
  (e: 'modelPositionChange', position: ModelPosition): void
  (e: 'modelChange', modelIndex: number): void
  (e: 'expressionChange', expressionName: string): void
  (e: 'randomExpression'): void
  (e: 'playAudio'): void
  (e: 'playMotion', group: string, index: number): void
  (e: 'randomMotion', group: string): void
}>();

// Types
interface BackgroundSettings {
  mode: 'solid' | 'rgb' | 'transparent';
  color?: string;
  rgbSpeed?: number;
}

interface ModelPosition {
  x: number;
  y: number;
  scale: number;
}

// Props to receive available models and expressions
const props = defineProps<{
  availableModels?: string[];
  availableExpressions?: string[];
  availableMotionGroups?: string[];
  availableMotions?: Array<{ group: string; index: number; name: string }>;
}>();

// State
const isMenuOpen = ref(false);
const backgroundMode = ref<'solid' | 'rgb' | 'transparent'>('solid');
const backgroundColor = ref('#00ff00'); // Default green
const rgbSpeed = ref(5); // Default RGB speed

// Model position state
const modelX = ref(0.0);
const modelY = ref(0.0);
const modelScale = ref(1.0);

// Model selection state
const selectedModelIndex = ref(0);

// Expression state
const selectedExpression = ref('');

// Motion state
const selectedMotionGroup = ref('');
const selectedMotion = ref('');

// Methods
const toggleMenu = () => {
  isMenuOpen.value = !isMenuOpen.value;
};

const onBackgroundModeChange = () => {
  // Immediately emit when mode changes
  emitBackgroundChange();
};

const onColorChange = () => {
  if (backgroundMode.value === 'solid') {
    emitBackgroundChange();
  }
};

const onRgbSpeedChange = () => {
  if (backgroundMode.value === 'rgb') {
    emitBackgroundChange();
  }
};

const emitBackgroundChange = () => {
  const settings: BackgroundSettings = {
    mode: backgroundMode.value,
    color: backgroundMode.value === 'solid' ? backgroundColor.value : undefined,
    rgbSpeed: backgroundMode.value === 'rgb' ? rgbSpeed.value : undefined,
  };

  emit('backgroundChange', settings);
};

const onModelPositionChange = () => {
  const position: ModelPosition = {
    x: modelX.value,
    y: modelY.value,
    scale: modelScale.value,
  };

  emit('modelPositionChange', position);
};

const resetModelPosition = () => {
  modelX.value = 0.0;
  modelY.value = 0.0;
  modelScale.value = 1.0;
  onModelPositionChange();
};

const onModelChange = () => {
  emit('modelChange', selectedModelIndex.value);
};

const onExpressionChange = () => {
  if (selectedExpression.value) {
    emit('expressionChange', selectedExpression.value);
  }
};

const onRandomExpression = () => {
  emit('randomExpression');
  selectedExpression.value = ''; // Reset dropdown to default
};

const onPlayAudio = () => {
  emit('playAudio');
};

const onMotionSelectionChange = () => {
  // Just update the selection, no immediate action
};

const onPlaySelectedMotion = () => {
  if (selectedMotion.value) {
    const motion = JSON.parse(selectedMotion.value);
    emit('playMotion', motion.group, motion.index);
  }
};

const onRandomMotion = () => {
  if (selectedMotionGroup.value) {
    emit('randomMotion', selectedMotionGroup.value);
  }
};
</script>

<style scoped>
.settings-container {
  position: fixed;
  top: 20px;
  left: 20px;
  z-index: 1000;
}

.settings-icon {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.3s ease, border-color 0.3s ease;
  --gear-rotation: 0deg;
  --gear-scale: 1;
}

.settings-icon svg {
  transition: transform 0.3s ease;
  transform-origin: center;
  transform: rotate(var(--gear-rotation)) scale(var(--gear-scale));
}

.settings-icon:hover {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.25);
  --gear-scale: 1.05;
}

.settings-icon:not(.active):hover {
  --gear-rotation: 90deg;
}

.settings-icon.active {
  background: rgba(255, 255, 255, 0.3);
  border-color: rgba(255, 255, 255, 0.35);
  --gear-rotation: 180deg;
}

.settings-menu {
  position: absolute;
  top: 54px;
  left: 0;
  min-width: 320px;
  max-width: 400px;
  max-height: calc(100vh - 74px);
  background: rgba(30, 30, 30, 0.95);
  backdrop-filter: blur(20px);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  overflow-y: auto;
  overflow-x: hidden;
}

.settings-menu::-webkit-scrollbar {
  width: 8px;
}

.settings-menu::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
}

.settings-menu::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 4px;
}

.settings-menu::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}

.menu-content {
  padding: 20px;
}

.menu-content h3 {
  margin: 0 0 20px 0;
  color: white;
  font-size: 18px;
  font-weight: 600;
}

.setting-group {
  margin-bottom: 16px;
}

.setting-group label {
  display: block;
  color: rgba(255, 255, 255, 0.8);
  font-size: 14px;
  margin-bottom: 8px;
}

.select-input {
  width: 100%;
  padding: 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: white;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.select-input:hover,
.select-input:focus {
  background: rgba(255, 255, 255, 0.15);
  border-color: rgba(255, 255, 255, 0.3);
  outline: none;
}

.select-input option {
  background: #1e1e1e;
  color: #ffffff;
  padding: 8px;
}

.color-picker-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
}

.color-input {
  width: 60px;
  height: 40px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: transparent;
  cursor: pointer;
}

.color-input::-webkit-color-swatch-wrapper {
  padding: 4px;
}

.color-input::-webkit-color-swatch {
  border-radius: 4px;
  border: none;
}

.color-value-input {
  flex: 1;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: white;
  font-size: 14px;
  font-family: monospace;
  transition: all 0.2s ease;
}

.color-value-input:hover,
.color-value-input:focus {
  background: rgba(255, 255, 255, 0.15);
  border-color: rgba(255, 255, 255, 0.3);
  outline: none;
}

.slider-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
}

.slider-input {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.1);
  outline: none;
  -webkit-appearance: none;
}

.slider-input::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: white;
  cursor: pointer;
  transition: all 0.2s ease;
}

.slider-input::-webkit-slider-thumb:hover {
  transform: scale(1.2);
}

.slider-value {
  min-width: 30px;
  text-align: center;
  color: rgba(255, 255, 255, 0.9);
  font-size: 14px;
  font-weight: 600;
}

.section-title {
  margin: 20px 0 12px 0;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.9);
  font-size: 16px;
  font-weight: 600;
}

.section-title:first-child {
  margin-top: 0;
  padding-top: 0;
  border-top: none;
}

.reset-btn {
  width: 100%;
  padding: 10px;
  margin-top: 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: white;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.reset-btn:hover {
  background: rgba(255, 255, 255, 0.15);
  border-color: rgba(255, 255, 255, 0.3);
}

.action-btn {
  width: 100%;
  padding: 12px;
  border-radius: 8px;
  background: rgba(76, 175, 80, 0.2);
  border: 1px solid rgba(76, 175, 80, 0.4);
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-btn:hover {
  background: rgba(76, 175, 80, 0.3);
  border-color: rgba(76, 175, 80, 0.6);
  transform: translateY(-1px);
}

.action-btn.disabled,
.reset-btn.disabled {
  opacity: 0.5;
  cursor: not-allowed;
  pointer-events: none;
}

.motion-group-controls {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.motion-group-controls label {
  display: block;
  color: rgba(255, 255, 255, 0.7);
  font-size: 13px;
  margin-bottom: 8px;
}

/* Transition Animations */
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.slide-down-enter-from {
  opacity: 0;
  transform: translateY(-10px);
}

.slide-down-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
