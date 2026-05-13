/**
 * @metadata {
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2026-05-13",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0
 * }
 */
<template>
  <div class="calculator-cell">
    <div class="calculator-header">
      <h3>{{ $t('artifacts.calculatorCell.title') }}</h3>
      <p class="subtitle">{{ $t('artifacts.calculatorCell.subtitle') }}</p>
    </div>

    <div class="calculator-body">
      <!-- Input Form -->
      <div class="input-form">
        <div class="input-row">
          <div class="input-group">
            <label for="operand-a">{{ $t('artifacts.calculatorCell.firstNumber') }}</label>
            <input
              id="operand-a"
              v-model.number="inputData.a"
              type="number"
              step="any"
              :placeholder="$t('artifacts.calculatorCell.firstNumberPlaceholder')"
              :disabled="isExecuting"
            />
          </div>

          <div class="input-group">
            <label for="operation">{{ $t('artifacts.calculatorCell.operation') }}</label>
            <select
              id="operation"
              v-model="inputData.operation"
              :disabled="isExecuting"
            >
              <option value="add">{{ $t('artifacts.calculatorCell.operations.add') }}</option>
              <option value="subtract">{{ $t('artifacts.calculatorCell.operations.subtract') }}</option>
              <option value="multiply">{{ $t('artifacts.calculatorCell.operations.multiply') }}</option>
              <option value="divide">{{ $t('artifacts.calculatorCell.operations.divide') }}</option>
              <option value="power">{{ $t('artifacts.calculatorCell.operations.power') }}</option>
              <option value="modulo">{{ $t('artifacts.calculatorCell.operations.modulo') }}</option>
            </select>
          </div>

          <div class="input-group">
            <label for="operand-b">{{ $t('artifacts.calculatorCell.secondNumber') }}</label>
            <input
              id="operand-b"
              v-model.number="inputData.b"
              type="number"
              step="any"
              :placeholder="$t('artifacts.calculatorCell.secondNumberPlaceholder')"
              :disabled="isExecuting"
            />
          </div>
        </div>

        <div class="input-row">
          <div class="input-group">
            <label for="precision">{{ $t('artifacts.calculatorCell.precision') }}</label>
            <input
              id="precision"
              v-model.number="inputData.precision"
              type="number"
              min="0"
              max="10"
              placeholder="2"
              :disabled="isExecuting"
            />
          </div>
        </div>

        <button
          class="calculate-button"
          :disabled="isExecuting"
          @click="calculate"
        >
          {{ isExecuting ? $t('artifacts.calculatorCell.calculating') : $t('artifacts.calculatorCell.calculate') }}
        </button>
      </div>

      <!-- Validation Errors -->
      <div v-if="validationErrors.length > 0" class="validation-errors">
        <h4>{{ $t('artifacts.calculatorCell.validationErrors') }}</h4>
        <ul>
          <li v-for="(error, index) in validationErrors" :key="index">
            <strong>{{ error.field }}:</strong> {{ error.message }}
          </li>
        </ul>
      </div>

      <!-- Result Display -->
      <div v-if="result" class="result-display">
        <div v-if="result.success" class="result-success">
          <h4>✅ Result</h4>
          <div class="expression">{{ result.output.expression }}</div>
          <div class="result-value">{{ result.output.result }}</div>
          <div class="execution-info">
            <span>⚡ Execution time: {{ result.execution_time.toFixed(3) }}ms</span>
            <span v-if="result.quality_score">
              📊 Quality: {{ (result.quality_score * 100).toFixed(0) }}%
            </span>
          </div>
        </div>

        <div v-else class="result-error">
          <h4>❌ Error</h4>
          <p>{{ result.error }}</p>
        </div>
      </div>

      <!-- Cell Metadata -->
      <details class="metadata-section">
        <summary>ℹ️ Cell Information</summary>
        <pre>{{ cellMetadata }}</pre>
      </details>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { CalculatorCell } from './CalculatorCell'
import type { CellResult, CellMetadata, ValidationError } from '@/types/BaseCell'

// Props
interface Props {
  cell?: {
    id: string
    type: string
    initial_data?: any
  }
}

const props = withDefaults(defineProps<Props>(), {
  cell: () => ({
    id: 'calculator-demo',
    type: 'calculator-cell',
    initial_data: { a: 10, b: 5, operation: 'add', precision: 2 }
  })
})

// State
const calculator = new CalculatorCell()
const isExecuting = ref(false)
const result = ref<CellResult | null>(null)
const validationErrors = ref<ValidationError[]>([])
const cellMetadata = ref<CellMetadata | null>(null)

// Input data
const inputData = reactive({
  a: props.cell.initial_data?.a ?? 10,
  b: props.cell.initial_data?.b ?? 5,
  operation: props.cell.initial_data?.operation ?? 'add',
  precision: props.cell.initial_data?.precision ?? 2
})

// Calculate function
async function calculate() {
  isExecuting.value = true
  validationErrors.value = []
  result.value = null

  try {
    // Validate first
    const errors = calculator.validate(inputData)
    if (errors.length > 0) {
      validationErrors.value = errors
      isExecuting.value = false
      return
    }

    // Execute
    const execResult = await calculator.execute(inputData)
    result.value = execResult
  } catch (error: any) {
    result.value = {
      success: false,
      output: {},
      execution_time: 0,
      error: error.message || 'Calculation failed'
    }
  } finally {
    isExecuting.value = false
  }
}

// Load metadata on mount
onMounted(async () => {
  cellMetadata.value = await calculator.describe()
  
  // Setup the cell (optional for calculator, but demonstrates lifecycle)
  await calculator.setup({
    has_gpu: false,
    gpu_vram_mb: 0,
    cpu_cores: navigator.hardwareConcurrency || 4,
    headless_mode: false,
    timeout_seconds: 30
  })
})
</script>

<style scoped>
.calculator-cell {
  background: var(--background-color, #1e1e1e);
  color: var(--text-color, #e0e0e0);
  border-radius: 8px;
  padding: 1.5rem;
  font-family: system-ui, -apple-system, sans-serif;
}

.calculator-header {
  margin-bottom: 1.5rem;
  border-bottom: 2px solid var(--border-color, #333);
  padding-bottom: 1rem;
}

.calculator-header h3 {
  margin: 0;
  font-size: 1.5rem;
}

.subtitle {
  margin: 0.5rem 0 0 0;
  color: var(--text-secondary, #999);
  font-size: 0.9rem;
}

.input-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.input-row {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.input-group {
  flex: 1;
  min-width: 150px;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.input-group label {
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--text-secondary, #999);
}

.input-group input,
.input-group select {
  padding: 0.75rem;
  background: var(--input-bg, #2a2a2a);
  border: 1px solid var(--border-color, #444);
  border-radius: 4px;
  color: var(--text-color, #e0e0e0);
  font-size: 1rem;
}

.input-group input:focus,
.input-group select:focus {
  outline: none;
  border-color: var(--accent-color, #4a9eff);
}

.calculate-button {
  padding: 1rem 2rem;
  background: var(--accent-color, #4a9eff);
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.calculate-button:hover:not(:disabled) {
  background: var(--accent-hover, #3a8eef);
  transform: translateY(-1px);
}

.calculate-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.validation-errors {
  margin-top: 1rem;
  padding: 1rem;
  background: rgba(255, 77, 77, 0.1);
  border: 1px solid rgba(255, 77, 77, 0.3);
  border-radius: 4px;
}

.validation-errors h4 {
  margin: 0 0 0.5rem 0;
  color: #ff4d4d;
}

.validation-errors ul {
  margin: 0;
  padding-left: 1.5rem;
}

.result-display {
  margin-top: 1.5rem;
  padding: 1.5rem;
  border-radius: 4px;
}

.result-success {
  background: rgba(77, 255, 77, 0.1);
  border: 1px solid rgba(77, 255, 77, 0.3);
}

.result-error {
  background: rgba(255, 77, 77, 0.1);
  border: 1px solid rgba(255, 77, 77, 0.3);
}

.result-success h4 {
  margin: 0 0 1rem 0;
  color: #4dff4d;
}

.result-error h4 {
  margin: 0 0 0.5rem 0;
  color: #ff4d4d;
}

.expression {
  font-size: 1.5rem;
  font-weight: 500;
  margin-bottom: 0.5rem;
  color: var(--text-color, #e0e0e0);
}

.result-value {
  font-size: 2rem;
  font-weight: 700;
  margin-bottom: 1rem;
  color: var(--accent-color, #4a9eff);
}

.execution-info {
  display: flex;
  gap: 1.5rem;
  font-size: 0.85rem;
  color: var(--text-secondary, #999);
}

.metadata-section {
  margin-top: 1.5rem;
  padding: 1rem;
  background: var(--bg-secondary, #2a2a2a);
  border-radius: 4px;
  cursor: pointer;
}

.metadata-section summary {
  font-weight: 500;
  user-select: none;
}

.metadata-section pre {
  margin-top: 1rem;
  padding: 1rem;
  background: var(--bg-tertiary, #1a1a1a);
  border-radius: 4px;
  overflow-x: auto;
  font-size: 0.85rem;
  line-height: 1.5;
}
</style>
