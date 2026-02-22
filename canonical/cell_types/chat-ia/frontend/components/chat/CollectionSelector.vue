/**
 * @metadata {
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-12",
 *   "i18n_coverage": 100,
 *   "i18n_keys_used": [
 *     "chat.collectionSelector.title",
 *     "chat.collectionSelector.selectAll",
 *     "chat.collectionSelector.deselectAll",
 *     "chat.collectionSelector.ragDisabled",
 *     "chat.collectionSelector.allCollectionsEnabled",
 *     "chat.collectionSelector.searchingInOne",
 *     "chat.collectionSelector.searchingInMultiple"
 *   ],
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-12",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full"
 * }
 */
<template>
  <div class="collection-selector" data-testid="collection-selector">
    <div class="selector-header">
      <label class="selector-label">{{ $t('chat.collectionSelector.title') }}</label>
      <button
        v-if="
          modelValue.length > 0 &&
          modelValue.length < availableCollections.length
        "
        class="selector-action-btn"
        type="button"
        @click="selectAll"
      >
        {{ $t('chat.collectionSelector.selectAll') }}
      </button>
      <button
        v-else-if="modelValue.length === availableCollections.length"
        class="selector-action-btn"
        type="button"
        @click="clearSelection"
      >
        {{ $t('chat.collectionSelector.deselectAll') }}
      </button>
    </div>

    <div class="collections-grid">
      <button
        v-for="collection in availableCollections"
        :key="collection.value"
        :class="[
          'collection-btn',
          isSelected(collection.value) ? 'collection-btn-selected' : 'collection-btn-default'
        ]"
        type="button"
        :data-testid="`collection-${collection.value}`"
        @click="toggleCollection(collection.value)"
      >
        <span>{{ collection.icon }}</span>
        <span>{{ collection.label }}</span>
      </button>
    </div>

    <p class="selection-description">
      {{ selectionDescription }}
    </p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const i18n = useI18n()

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => [],
  },
  availableCollections: {
    type: Array,
    required: true,
  },
})

const emit = defineEmits(['update:modelValue'])

const isSelected = (collectionValue) => {
  return props.modelValue.includes(collectionValue)
}

const toggleCollection = (collectionValue) => {
  const currentSelection = [...props.modelValue]
  const index = currentSelection.indexOf(collectionValue)

  if (index > -1) {
    // Remove if already selected
    currentSelection.splice(index, 1)
  } else {
    // Add if not selected
    currentSelection.push(collectionValue)
  }

  emit('update:modelValue', currentSelection)
}

const clearSelection = () => {
  emit('update:modelValue', [])
}

const selectAll = () => {
  const allCollectionValues = props.availableCollections.map((c) => c.value)
  emit('update:modelValue', allCollectionValues)
}

const selectionDescription = computed(() => {
  if (props.modelValue.length === 0) {
    return i18n.t('chat.collectionSelector.ragDisabled')
  } else if (props.modelValue.length === props.availableCollections.length) {
    return i18n.t('chat.collectionSelector.allCollectionsEnabled')
  } else if (props.modelValue.length === 1) {
    const collection = props.availableCollections.find(
      (c) => c.value === props.modelValue[0],
    )
    return i18n.t('chat.collectionSelector.searchingInOne', {
      collection: collection?.label || 'Seleção'
    })
  } else {
    return i18n.t('chat.collectionSelector.searchingInMultiple', {
      count: props.modelValue.length
    })
  }
})
</script>

<style scoped>
.collection-selector {
  background: var(--color-surface);
  border-radius: var(--radius-md);
  padding: var(--space-md);
  border: 1px solid var(--color-border);
}

.selector-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-sm);
}

.selector-label {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
}

.selector-action-btn {
  font-size: var(--font-size-xs);
  color: var(--color-primary);
  background: none;
  border: none;
  cursor: pointer;
  transition: color var(--transition-base);
}

.selector-action-btn:hover {
  color: var(--color-primary-hover);
}

.collections-grid {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-sm);
}

.collection-btn {
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  transition: all var(--transition-base);
  border: 2px solid;
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  cursor: pointer;
}

.collection-btn-selected {
  background: var(--color-primary-light);
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.collection-btn-default {
  background: var(--color-surface-hover);
  border-color: var(--color-border);
  color: var(--color-text-secondary);
}

.collection-btn-default:hover {
  background: var(--color-surface);
}

.selection-description {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-top: var(--space-sm);
}
</style>
