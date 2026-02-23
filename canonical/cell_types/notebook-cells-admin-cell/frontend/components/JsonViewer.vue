/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-12",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-12",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0
 * }
 */
<template>
  <div class="json-viewer">
    <div v-if="isObject(data)" class="json-object">
      <div
        v-for="(value, key) in data"
        :key="key"
        class="json-item"
      >
        <div class="json-key-row">
          <button
            v-if="isExpandable(value)"
            class="expand-btn"
            :aria-label="`${isExpanded(key) ? t('admin.jsonViewer.collapse') : t('admin.jsonViewer.expand')} ${key}`"
            @click="toggleExpand(key)"
          >
            <span class="expand-icon">
              {{ isExpanded(key) ? '▼' : '▶' }}
            </span>
          </button>
          <span v-else class="expand-placeholder"></span>

          <span class="json-key">{{ key }}</span>
          <span class="json-separator">:</span>

          <span v-if="!isExpandable(value)" class="json-value" :class="getValueClass(value)">
            {{ formatValue(value) }}
          </span>
          <span v-else class="json-type-indicator">
            {{ getTypeIndicator(value) }}
          </span>
        </div>

        <div
          v-if="isExpandable(value) && isExpanded(key)"
          class="json-nested"
        >
          <JsonViewer
            :data="value"
            :depth="depth + 1"
            :max-depth="maxDepth"
          />
        </div>
      </div>
    </div>

    <div v-else-if="isArray(data)" class="json-array">
      <div
        v-for="(item, index) in data"
        :key="index"
        class="json-item"
      >
        <div class="json-key-row">
          <button
            v-if="isExpandable(item)"
            class="expand-btn"
            :aria-label="`${isExpanded(index) ? t('admin.jsonViewer.collapse') : t('admin.jsonViewer.expand')} ${t('admin.jsonViewer.item')} ${index}`"
            @click="toggleExpand(index)"
          >
            <span class="expand-icon">
              {{ isExpanded(index) ? '▼' : '▶' }}
            </span>
          </button>
          <span v-else class="expand-placeholder"></span>

          <span class="json-index">[{{ index }}]</span>

          <span v-if="!isExpandable(item)" class="json-value" :class="getValueClass(item)">
            {{ formatValue(item) }}
          </span>
          <span v-else class="json-type-indicator">
            {{ getTypeIndicator(item) }}
          </span>
        </div>

        <div
          v-if="isExpandable(item) && isExpanded(index)"
          class="json-nested"
        >
          <JsonViewer
            :data="item"
            :depth="depth + 1"
            :max-depth="maxDepth"
          />
        </div>
      </div>
    </div>

    <div v-else class="json-primitive">
      <span class="json-value" :class="getValueClass(data)">
        {{ formatValue(data) }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref, defineProps } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps({
  data: {
    type: [Object, Array, String, Number, Boolean, null],
    required: true,
  },
  depth: {
    type: Number,
    default: 0,
  },
  maxDepth: {
    type: Number,
    default: 10,
  },
})

// Track expanded state for each key/index
const expandedKeys = ref(new Set())

// Check if value is an object
function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

// Check if value is an array
function isArray(value) {
  return Array.isArray(value)
}

// Check if value can be expanded
function isExpandable(value) {
  return (isObject(value) || isArray(value)) && props.depth < props.maxDepth
}

// Check if key/index is expanded
function isExpanded(key) {
  return expandedKeys.value.has(String(key))
}

// Toggle expand/collapse
function toggleExpand(key) {
  const keyStr = String(key)
  if (expandedKeys.value.has(keyStr)) {
    expandedKeys.value.delete(keyStr)
  } else {
    expandedKeys.value.add(keyStr)
  }
}

// Get CSS class for value type
function getValueClass(value) {
  if (value === null) return 'json-null'
  if (typeof value === 'boolean') return 'json-boolean'
  if (typeof value === 'number') return 'json-number'
  if (typeof value === 'string') return 'json-string'
  return ''
}

// Format value for display
function formatValue(value) {
  if (value === null) return 'null'
  if (value === undefined) return 'undefined'
  if (typeof value === 'string') return `"${value}"`
  if (typeof value === 'boolean') return value.toString()
  if (typeof value === 'number') return value.toString()
  return String(value)
}

// Get type indicator for expandable items
function getTypeIndicator(value) {
  if (isArray(value)) {
    return t('admin.jsonViewer.arrayType', { count: value.length })
  }
  if (isObject(value)) {
    const keys = Object.keys(value)
    return t('admin.jsonViewer.objectType', { count: keys.length })
  }
  return ''
}
</script>

<style scoped>
.json-viewer {
  font-family: 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.6;
}

.json-object,
.json-array {
  margin-left: 0;
}

.json-item {
  margin: 2px 0;
}

.json-key-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.expand-btn {
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  color: var(--color-text-secondary);
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color var(--transition-fast);
}

.expand-btn:hover {
  color: var(--color-text-primary);
}

.expand-icon {
  font-size: 10px;
}

.expand-placeholder {
  width: 16px;
  height: 16px;
  display: inline-block;
}

.json-key {
  color: var(--color-primary);
  font-weight: 600;
}

.json-index {
  color: var(--color-primary);
  font-weight: 600;
}

.json-separator {
  color: var(--color-text-secondary);
}

.json-value {
  word-break: break-all;
}

.json-string {
  color: var(--color-success);
}

.json-number {
  color: var(--color-error);
}

.json-boolean {
  color: var(--color-info);
  font-weight: 600;
}

.json-null {
  color: var(--color-text-tertiary);
  font-style: italic;
}

.json-type-indicator {
  color: var(--color-text-secondary);
  font-size: 12px;
  font-style: italic;
}

.json-nested {
  margin-left: 24px;
  padding-left: 12px;
  border-left: 1px solid var(--color-border);
}

.json-primitive {
  padding: 4px 0;
}
</style>
