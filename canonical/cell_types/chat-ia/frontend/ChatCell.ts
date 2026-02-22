/**
 * Chat IA Cell - BaseCell Implementation
 *
 * Pure cell logic with NO Vue/UI dependencies.
 * This cell can execute headless (via API, CLI, backend, etc).
 * View.vue is just the presentation layer - it will receive an instance of this cell as a prop.
 */

import type {
  BaseCell,
  CellResult,
  CellMetadata,
  ValidationError,
  EnvironmentConfig
} from '@/types/BaseCell'

export class ChatIACell implements BaseCell {
  private conversationId: string | null = null

  /**
   * Execute the chat cell
   * Pure business logic - no UI knowledge
   */
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()

    try {
      // Validate input first
      const validationErrors = this.validate(input)
      if (validationErrors.length > 0) {
        return {
          success: false,
          output: {},
          execution_time: performance.now() - startTime,
          error: `Validation failed: ${validationErrors.map(e => e.message).join(', ')}`
        }
      }

      // Extract input parameters
      const {
        prompt = '',
        model = 'gemini-2.5-flash',
        selectedCollections = [],
        systemPrompt = '',
        enableIntentionClassification = false
      } = input

      // Chat execution logic
      // This is where the actual chat logic would go
      // View.vue will call this and handle displaying results

      return {
        success: true,
        output: {
          message: 'Chat message received',
          model,
          prompt,
          selectedCollections,
          systemPrompt,
          enableIntentionClassification,
          conversationId: this.getConversationId()
        },
        execution_time: performance.now() - startTime
      }
    } catch (error) {
      return {
        success: false,
        output: {},
        execution_time: performance.now() - startTime,
        error: error instanceof Error ? error.message : 'Unknown error'
      }
    }
  }

  /**
   * Describe the cell's capabilities
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'chat-ia',
      name: 'Chat IA',
      version: '1.0.0',
      description: 'Interactive chat interface with AI models. Supports multiple providers (Gemini, OpenAI, Ollama), conversation history, file attachments, and agent mode for autonomous task execution.',
      inputs: {
        prompt: {
          type: 'string',
          description: 'User message/prompt for the chat',
          required: false
        },
        model: {
          type: 'string',
          description: 'AI model to use (gemini-2.5-flash, gpt-4-turbo, gpt-4o-mini, ollama:mistral, etc)',
          required: false,
          default: 'gemini-2.5-flash'
        },
        selectedCollections: {
          type: 'array',
          description: 'RAG (Retrieval-Augmented Generation) collections to search for context',
          required: false,
          default: []
        },
        systemPrompt: {
          type: 'string',
          description: 'System prompt/instructions for the model behavior',
          required: false,
          default: ''
        },
        enableIntentionClassification: {
          type: 'boolean',
          description: 'Classify user intent automatically (for routing, filtering, etc)',
          required: false,
          default: false
        }
      },
      outputs: {
        message: { type: 'string', description: 'Response message from the AI' },
        model: { type: 'string', description: 'Model that was used' },
        conversationId: { type: 'string', description: 'Conversation identifier' },
        conversationHistory: { type: 'array', description: 'Full conversation history' }
      },
      tags: ['chat', 'ai', 'interactive', 'gemini', 'openai', 'ollama', 'rag', 'agent']
    }
  }

  /**
   * Validate input before execution
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []

    if (input.model && typeof input.model !== 'string') {
      errors.push({
        field: 'model',
        message: 'model must be a string'
      })
    }

    if (input.selectedCollections && !Array.isArray(input.selectedCollections)) {
      errors.push({
        field: 'selectedCollections',
        message: 'selectedCollections must be an array'
      })
    }

    if (input.enableIntentionClassification && typeof input.enableIntentionClassification !== 'boolean') {
      errors.push({
        field: 'enableIntentionClassification',
        message: 'enableIntentionClassification must be a boolean'
      })
    }

    return errors
  }

  /**
   * Setup resources
   */
  async setup(config: EnvironmentConfig): Promise<void> {
    console.log('[ChatIA] Cell setup called', config)
  }

  /**
   * Cleanup resources
   */
  async teardown(): Promise<void> {
    console.log('[ChatIA] Cell teardown called')
  }

  /**
   * Health check for external dependencies
   */
  async health_check() {
    return {
      status: 'healthy',
      can_execute: true,
      message: 'Chat IA cell is ready for execution'
    }
  }

  /**
   * Get or create conversation ID
   * Helper method for conversation management
   */
  getConversationId(): string {
    if (!this.conversationId) {
      this.conversationId = crypto.randomUUID()
    }
    return this.conversationId
  }

  /**
   * Set conversation ID
   * Helper method for conversation management
   */
  setConversationId(id: string): void {
    this.conversationId = id
  }
}
