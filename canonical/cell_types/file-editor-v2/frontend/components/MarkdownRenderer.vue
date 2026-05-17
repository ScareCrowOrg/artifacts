<template>
  <div
    ref="rendererContainer"
    class="markdown-renderer"
    v-html="renderedHtml"
  ></div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'

const props = defineProps({
  content: {
    type: String,
    required: true,
    default: '',
  },
})

const rendererContainer = ref(null)

const md = new MarkdownIt({
  html: false,
  xhtmlOut: true,
  breaks: true,
  linkify: true,
  typographer: true,
  highlight: (str, lang) => {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(str, { language: lang, ignoreIllegals: true }).value
      } catch (_) { /* fallback */ }
    }
    try {
      return hljs.highlightAuto(str).value
    } catch (_) {
      return ''
    }
  },
})

const renderedHtml = computed(() => {
  if (!props.content) return ''
  return md.render(props.content)
})
</script>

<style scoped>
.markdown-renderer {
  color: var(--color-text-primary);
  line-height: 1.7;
  font-size: 0.9375rem;
}
.markdown-renderer h1,
.markdown-renderer h2,
.markdown-renderer h3,
.markdown-renderer h4,
.markdown-renderer h5,
.markdown-renderer h6 {
  margin-top: 1.5rem;
  margin-bottom: 0.75rem;
  font-weight: 700;
  color: var(--color-text-primary);
  line-height: 1.3;
}
.markdown-renderer h1 { font-size: 1.5rem; border-bottom: 2px solid var(--color-border); padding-bottom: 0.25rem; }
.markdown-renderer h2 { font-size: 1.25rem; border-bottom: 1px solid var(--color-border); padding-bottom: 0.25rem; }
.markdown-renderer h3 { font-size: 1.125rem; }
.markdown-renderer p { margin: 0 0 0.75rem; }
.markdown-renderer strong { font-weight: 700; }
.markdown-renderer em { font-style: italic; }
.markdown-renderer a {
  color: var(--color-primary);
  text-decoration: none;
}
.markdown-renderer a:hover {
  text-decoration: underline;
}
.markdown-renderer ul,
.markdown-renderer ol {
  margin: 0 0 0.75rem;
  padding-left: 1.5rem;
}
.markdown-renderer li { margin-bottom: 0.25rem; }
.markdown-renderer code {
  background: var(--color-surface-hover);
  border: 1px solid var(--color-border);
  border-radius: 3px;
  padding: 2px 6px;
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.875em;
  color: var(--color-code-text);
}
.markdown-renderer pre {
  margin: 0.75rem 0;
  padding: 1rem;
  overflow-x: auto;
  background: var(--color-code-bg);
  border: 1px solid var(--color-border);
  border-radius: 6px;
}
.markdown-renderer pre code {
  background: transparent;
  border: none;
  padding: 0;
  font-size: 0.8125rem;
  line-height: 1.6;
}
.markdown-renderer blockquote {
  margin: 0.75rem 0;
  padding-left: 1rem;
  border-left: 4px solid var(--color-border);
  color: var(--color-text-secondary);
  font-style: italic;
}
.markdown-renderer hr {
  border: none;
  border-top: 2px solid var(--color-border);
  margin: 1.5rem 0;
}
.markdown-renderer table {
  width: 100%;
  border-collapse: collapse;
  margin: 0.75rem 0;
}
.markdown-renderer th,
.markdown-renderer td {
  padding: 0.5rem;
  border: 1px solid var(--color-border);
  text-align: left;
}
.markdown-renderer th {
  background: var(--color-surface-hover);
  font-weight: 600;
}
.markdown-renderer tr:nth-child(even) { background: var(--color-surface-hover); }
.markdown-renderer img {
  max-width: 100%;
  height: auto;
  border-radius: 6px;
  margin: 0.75rem 0;
}
</style>
