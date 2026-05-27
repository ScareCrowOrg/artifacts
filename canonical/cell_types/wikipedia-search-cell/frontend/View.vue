<template>
  <div class="wikipedia-search-cell bg-surface border border-border rounded-lg p-4">
    <!-- Header com ícone Wikipedia -->
    <div class="flex items-center gap-2 mb-4">
      <svg class="w-6 h-6 text-primary flex-shrink-0" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 15l-3-8h2l2 5.5L14 9h2l-3 8h-2z"/>
      </svg>
      <h3 class="text-lg font-semibold">{{ $t('wikipediaSearchCell.title') }}</h3>
    </div>

    <!-- Search Form -->
    <div class="flex flex-col sm:flex-row gap-2 mb-4">
      <div class="flex-1 relative">
        <svg class="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-secondary pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          v-model="localQuery"
          type="text"
          :placeholder="$t('wikipediaSearchCell.searchPlaceholder')"
          class="w-full pl-8 pr-3 py-2 text-sm border border-border rounded-md bg-surface-alt focus:outline-none focus:ring-2 focus:ring-primary"
          @keydown.enter="handleSearch"
        />
      </div>
      <div class="relative w-full sm:w-28">
        <svg class="absolute left-2 top-1/2 -translate-y-1/2 w-4 h-4 text-secondary pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <select
          v-model="localLanguage"
          class="w-full pl-8 pr-3 py-2 text-sm border border-border rounded-md bg-surface-alt focus:outline-none focus:ring-2 focus:ring-primary appearance-none"
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
        <svg class="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-secondary pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
        </svg>
      </div>
      <button
        @click="handleSearch"
        :disabled="isSearching || !localQuery.trim()"
        class="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary rounded-md hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
      >
        <svg v-if="!isSearching" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <svg v-else class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        {{ isSearching ? $t('wikipediaSearchCell.searching') : $t('wikipediaSearchCell.searchButton') }}
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="isSearching" class="flex items-center justify-center py-8">
      <div class="w-8 h-8 border-3 border-primary border-t-transparent rounded-full animate-spin" />
    </div>

    <!-- Error State -->
    <div v-else-if="errorMessage" class="flex items-start gap-2 p-3 mb-4 text-sm text-red-700 bg-red-100 border border-red-200 rounded-md">
      <svg class="w-4 h-4 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <span>{{ errorMessage }}</span>
    </div>

    <!-- Results -->
    <div v-else-if="results.length > 0">
      <div class="flex items-center gap-1.5 text-xs text-secondary mb-3">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
        </svg>
        <span>{{ $t('wikipediaSearchCell.resultsCount', { shown: results.length, total: totalResults }) }}</span>
      </div>
      <ul class="space-y-3">
        <li
          v-for="result in results"
          :key="result.pageId"
          class="flex items-start gap-3 p-3 border border-border rounded-md hover:bg-surface-alt hover:border-primary/30 transition-colors"
        >
          <!-- Book/article icon -->
          <svg class="w-5 h-5 text-primary/60 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
          </svg>
          <div class="flex-1 min-w-0">
            <a
              :href="result.url"
              target="_blank"
              rel="noopener noreferrer"
              class="text-primary font-medium hover:underline text-sm"
            >
              {{ result.title }}
            </a>
            <p class="text-xs text-secondary mt-1 leading-relaxed line-clamp-2" v-html="result.snippet" />
            <a
              :href="result.url"
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex items-center gap-1 mt-2 text-xs text-primary hover:underline"
            >
              <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
              {{ $t('wikipediaSearchCell.openArticle') }}
            </a>
          </div>
        </li>
      </ul>
      <a
        :href="wikipediaBaseUrl"
        target="_blank"
        rel="noopener noreferrer"
        class="inline-flex items-center gap-1.5 mt-4 text-xs text-secondary hover:text-primary transition-colors"
      >
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 15l-3-8h2l2 5.5L14 9h2l-3 8h-2z"/>
        </svg>
        {{ $t('wikipediaSearchCell.visitWikipedia') }}
        <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
        </svg>
      </a>
    </div>

    <!-- Empty / Idle State -->
    <div v-else class="flex flex-col items-center justify-center py-8 text-secondary">
      <svg class="w-12 h-12 mb-3 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
      </svg>
      <svg class="w-6 h-6 -mt-2 mb-2 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
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
