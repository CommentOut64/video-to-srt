<template>
  <div class="preset-selector">
    <div class="selector-header">
      <span class="header-label">转录方案</span>
      <button
        v-if="showAdvanced"
        class="toggle-btn"
        @click="expanded = !expanded"
      >
        {{ expanded ? '收起' : '高级' }}
      </button>
    </div>

    <!-- 预设卡片网格 -->
    <div class="preset-grid">
      <div
        v-for="preset in presets"
        :key="preset.id"
        class="preset-card"
        :class="{ active: modelValue === preset.id }"
        @click="selectPreset(preset.id)"
      >
        <div class="preset-icon">{{ preset.icon }}</div>
        <div class="preset-info">
          <div class="preset-name">{{ preset.name }}</div>
          <div class="preset-desc">{{ preset.desc }}</div>
        </div>
        <div v-if="modelValue === preset.id" class="check-mark">
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
          </svg>
        </div>
      </div>
    </div>

    <!-- 高级设置展开区 -->
    <div v-if="expanded && showAdvanced" class="advanced-section">
      <div class="advanced-row">
        <label>增强模式</label>
        <select v-model="localSettings.enhancement" @change="emitChange">
          <option value="off">关闭</option>
          <option value="smart_patch">智能补刀</option>
          <option value="deep_listen">深度聆听</option>
        </select>
      </div>
      <div class="advanced-row">
        <label>校对模式</label>
        <select v-model="localSettings.proofread" @change="emitChange">
          <option value="off">关闭</option>
          <option value="sparse">按需校对</option>
          <option value="full">全文精修</option>
        </select>
      </div>
      <div class="advanced-row">
        <label>翻译模式</label>
        <select v-model="localSettings.translate" @change="emitChange">
          <option value="off">关闭</option>
          <option value="partial">重点翻译</option>
          <option value="full">全文翻译</option>
        </select>
      </div>
      <div v-if="localSettings.translate !== 'off'" class="advanced-row">
        <label>目标语言</label>
        <select v-model="localSettings.target_language" @change="emitChange">
          <option value="en">英语</option>
          <option value="zh">中文</option>
          <option value="ja">日语</option>
          <option value="ko">韩语</option>
        </select>
      </div>
    </div>

    <!-- 当前方案说明 -->
    <div class="current-preset-info">
      <span class="info-label">当前方案:</span>
      <span class="info-value">{{ currentPresetInfo }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: String,
    default: 'default'
  },
  showAdvanced: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'change'])

// 预设配置
const presets = [
  {
    id: 'default',
    name: '极速',
    desc: '仅 SenseVoice',
    icon: 'S',
    enhancement: 'off',
    proofread: 'off',
    translate: 'off'
  },
  {
    id: 'preset1',
    name: '补刀',
    desc: 'SV + Whisper',
    icon: 'W',
    enhancement: 'smart_patch',
    proofread: 'off',
    translate: 'off'
  },
  {
    id: 'preset2',
    name: '轻校',
    desc: '补刀 + 按需校对',
    icon: 'L',
    enhancement: 'smart_patch',
    proofread: 'sparse',
    translate: 'off'
  },
  {
    id: 'preset3',
    name: '精校',
    desc: '补刀 + 全文精修',
    icon: 'P',
    enhancement: 'smart_patch',
    proofread: 'full',
    translate: 'off'
  },
  {
    id: 'preset4',
    name: '全译',
    desc: '精校 + 全文翻译',
    icon: 'T',
    enhancement: 'smart_patch',
    proofread: 'full',
    translate: 'full'
  },
  {
    id: 'preset5',
    name: '重译',
    desc: '精校 + 重点翻译',
    icon: 'R',
    enhancement: 'smart_patch',
    proofread: 'full',
    translate: 'partial'
  }
]

const expanded = ref(false)
const localSettings = ref({
  enhancement: 'off',
  proofread: 'off',
  translate: 'off',
  target_language: 'en'
})

// 当前预设信息
const currentPresetInfo = computed(() => {
  const preset = presets.find(p => p.id === props.modelValue)
  return preset ? `${preset.name} - ${preset.desc}` : '自定义'
})

// 选择预设
function selectPreset(presetId) {
  emit('update:modelValue', presetId)

  // 更新本地设置以匹配预设
  const preset = presets.find(p => p.id === presetId)
  if (preset) {
    localSettings.value = {
      enhancement: preset.enhancement,
      proofread: preset.proofread,
      translate: preset.translate,
      target_language: localSettings.value.target_language
    }
  }

  emit('change', {
    preset_id: presetId,
    ...localSettings.value
  })
}

// 高级设置变更
function emitChange() {
  // 当高级设置改变时，检查是否匹配某个预设
  const matchingPreset = presets.find(p =>
    p.enhancement === localSettings.value.enhancement &&
    p.proofread === localSettings.value.proofread &&
    p.translate === localSettings.value.translate
  )

  if (matchingPreset && matchingPreset.id !== props.modelValue) {
    emit('update:modelValue', matchingPreset.id)
  } else if (!matchingPreset) {
    emit('update:modelValue', 'custom')
  }

  emit('change', {
    preset_id: matchingPreset?.id || 'custom',
    ...localSettings.value
  })
}

// 监听外部预设变化
watch(() => props.modelValue, (newVal) => {
  const preset = presets.find(p => p.id === newVal)
  if (preset) {
    localSettings.value = {
      enhancement: preset.enhancement,
      proofread: preset.proofread,
      translate: preset.translate,
      target_language: localSettings.value.target_language
    }
  }
}, { immediate: true })
</script>

<style lang="scss" scoped>
.preset-selector {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.selector-header {
  display: flex;
  align-items: center;
  justify-content: space-between;

  .header-label {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-normal);
  }

  .toggle-btn {
    padding: 4px 8px;
    font-size: 11px;
    color: var(--text-muted);
    background: var(--bg-tertiary);
    border-radius: var(--radius-sm);
    transition: all var(--transition-fast);

    &:hover {
      color: var(--text-normal);
      background: var(--bg-quaternary);
    }
  }
}

.preset-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.preset-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  position: relative;

  &:hover {
    background: var(--bg-tertiary);
    border-color: var(--border-hover);
  }

  &.active {
    border-color: var(--primary);
    background: rgba(88, 166, 255, 0.08);

    .preset-icon {
      background: var(--primary);
      color: white;
    }
  }

  .preset-icon {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg-tertiary);
    border-radius: var(--radius-sm);
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 6px;
  }

  .preset-info {
    text-align: center;

    .preset-name {
      font-size: 12px;
      font-weight: 500;
      color: var(--text-normal);
      margin-bottom: 2px;
    }

    .preset-desc {
      font-size: 10px;
      color: var(--text-muted);
      line-height: 1.3;
    }
  }

  .check-mark {
    position: absolute;
    top: 4px;
    right: 4px;
    width: 14px;
    height: 14px;
    color: var(--primary);

    svg {
      width: 100%;
      height: 100%;
    }
  }
}

.advanced-section {
  padding: 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.advanced-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;

  label {
    font-size: 12px;
    color: var(--text-secondary);
    flex-shrink: 0;
  }

  select {
    flex: 1;
    max-width: 140px;
    padding: 5px 8px;
    font-size: 12px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-sm);
    color: var(--text-normal);

    &:focus {
      border-color: var(--primary);
      outline: none;
    }
  }
}

.current-preset-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
  font-size: 11px;

  .info-label {
    color: var(--text-muted);
  }

  .info-value {
    color: var(--text-normal);
    font-weight: 500;
  }
}
</style>
