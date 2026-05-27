<template>
  <div class="wikipedia-search-cell bg-surface border border-border rounded-lg p-4">
    <h3 class="text-lg font-semibold mb-4">{{ $t('wikipediaSearchCell.title') }}</h3>

    <!-- Search Form -->
    <div class="flex flex-col sm:flex-row gap-2 mb-4">
      <div class="flex-1">
        <input
          v-model="localQuery"
          type="text"
          :placeholder="$t('wikipediaSearchCell.searchPlaceholder')"
          class="w-full px-3 py-2 text-sm border border-border rounded-md bg-surface-alt focus:outline-none focus:ring-2 focus:ring-primary"
          @keydown.enter="handleSearch"
        />
      </div>
      <select
        v-model="localLanguage"
        class="px-3 py-2 text-sm border border-border rounded-md bg-surface-alt focus:outline-none focus:ring-2 focus:ring-primary w-full sm:w-24"
      >
        <option value="en">EN</option>
        <option value="pt">PT</option>
        <option value="es">ES</option>
        <option value="fr">FR</option>
        <option value="de">DE</option>
        <option value="it">IT</option>
        <option value="ja">JA</option>
        <option value="zh">ZH</option>
        <option value="ru">RU</option>
      </select>
      <button
        @click="handleSearch"
        :disabled="isSearching || !localQuery.trim()"
        class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-md hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
      >
        {{ isSearching ? $t('wikipediaSearchCell.searching') : $t('wikipediaSearchCell.searchButton') }}
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="isSearching" class="flex items-center justify-center py-8">
      <div class="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
    </div>

    <!-- Error State -->
    <div v-else-if="errorMessage" class="p-3 mb-4 text-sm text-red-700 bg-red-100 border border-red-200 rounded-md">
      {{ errorMessage }}
    </div>

    <!-- Results -->
    <div v-else-if="results.length > 0">
      <p class="text-xs text-secondary mb-3">
        {{ $t('wikipediaSearchCell.resultsCount', { shown: results.length, total: totalResults }) }}
      </p>
      <ul class="space-y-3">
        <li
          v-for="result in results"
          :key="result.pageId"
          class="p-3 border border-border rounded-md hover:bg-surface-alt transition-colors"
        >
          <a
            :href="result.url"
            target="_blank"
            rel="noopener noreferrer"
            class="text-primary font-medium hover:underline text-sm"
          >
            {{ result.title }}
          </a>
          <p class="text-xs text-secondary mt-1 leading-relaxed" v-html="result.snippet" />
          <a
            :href="result.url"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-block mt-2 text-xs text-primary hover:underline"
          >
            {{ $t('wikipediaSearchCell.openArticle') }} &rarr;
          </a>
        </li>
      </ul>
      <a
        :href="wikipediaBaseUrl"
        target="_blank"
        rel="noopener noreferrer"
        class="inline-block mt-4 text-xs text-secondary hover:text-primary transition-colors"
      >
        {{ $t('wikipediaSearchCell.visitWikipedia') }} &rarr;
      </a>
    </div>

    <!-- Empty / Idle State -->
    <div v-else class="flex flex-col items-center justify-center py-8 text-secondary">
      <svg class="w-10 h-10 mb-2 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
      <p class="text-sm">{{ $t('wikipediaSearchCell.emptyState') }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, type Ref } from 'vue'
import { WikipediaSearchCell } from './WikipediaSearchCell'
import type { CellResult } from '@/types/BaseCell'

interface Props {
  cell?: {
    id?: string
    initial_data?: {
      query?: string
      language?: string
      limit?: number
      results?: any[]
      totalResults?: number
    }
  }
}

const props = withDefaults(defineProps<Props>(), {
  cell: () => ({})
})

const emit = defineEmits<{
  'update:cell': [cell: Props['cell']]
  execute: []
}>()

// Buffer Local Pattern: flat refs, not cascading computeds from props
const localQuery: Ref<string> = ref('')
const localLanguage: Ref<string> = ref('en')
const results: Ref<WikipediaSearchResult[]> = ref([])
const totalResults: Ref<number> = ref(0)
const isSearching: Ref<boolean> = ref(false)
const errorMessage: Ref<string | null> = ref(null)
const cellInstance: Ref<WikipediaSearchCell | null> = ref(null)

const wikipediaSearchResult = ref<CellResult | null>(null)

interface WikipediaSearchResult {
  title: string
  pageId: number
  snippet: string
  url: string
}

const wikipediaBaseUrl = computed(() =>
  `https://${localLanguage.value}.wikipedia.org`
)

// Hydration: read from props only on mount
onMounted(() => {
  cellInstance.value = new WikipediaSearchCell()
  localQuery.value = props.cell?.initial_data?.query || ''
  localLanguage.value = props.cell?.initial_data?.language || 'en'

  if (props.cell?.initial_data?.results && props.cell.initial_data.results.length > 0) {
    results.value = props.cell.initial_data.results as WikipediaSearchResult[]
    totalResults.value = props.cell.initial_data.totalResults || 0
  }
})

// Watch external prop changes (sync only if user isn't typing)
watch(() => props.cell?.initial_data, (newData) => {
  if (newData && newData.query !== undefined && !localQuery.value) {
    localQuery.value = newData.query || ''
  }
}, { deep: true })

async function handleSearch(): Promise<void> {
  const query = localQuery.value.trim()
  if (!query || !cellInstance.value) return

  isSearching.value = true
  errorMessage.value = null
  results.value = []

  try {
    const result = await cellInstance.value.execute({
      query,
      language: localLanguage.value,
      limit: props.cell?.initial_data?.limit || 10
    })

    if (result.success && result.output) {
      const output = result.output as { results?: WikipediaSearchResult[]; totalResults?: number }
      results.value = output.results || []
      totalResults.value = output.totalResults || 0

      emit('update:cell', {
        ...props.cell,
        initial_data: {
          ...props.cell?.initial_data,
          query: localQuery.value,
          language: localLanguage.value,
          results: results.value,
          totalResults: totalResults.value
        }
      })
    } else {
      errorMessage.value = result.error || 'Search failed'
    }
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : 'Unknown error'
  } finally {
    isSearching.value = false
  }
}
</script>

<style scoped>
.bg-surface { background-color: var(--background-color, #fff); }
.bg-surface-alt { background-color: var(--surface-alt, #f5f5f5); }
.border-border { border-color: var(--border-color, #e0e0e0); }
.text-primary { color: var(--primary-color, #3366cc); }
.text-secondary { color: var(--secondary-color, #666); }
.bg-primary { background-color: var(--primary-color, #3366cc); }
.bg-primary-hover { background-color: var(--primary-hover, #2854a5); }
.ring-primary { --tw-ring-color: var(--primary-color, #3366cc); }
</style>
