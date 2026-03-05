/**
 * @file DynamicFormGenerator.ts
 * @description Dynamic Form Generator for BaseCell
 * 
 * Converts JSON schema (from type.json properties_schema) into form field definitions
 * that can be rendered by Vue components. Supports validation and type coercion.
 * 
 * Part of BaseCell Phase 2: Dynamic Form Generation & Framework Integration
 */

/**
 * Form field component definition
 * Used by Vue components to render appropriate input controls
 */
export interface FormFieldComponent {
  /** Input type: text, number, checkbox, select, textarea */
  type: 'text' | 'number' | 'checkbox' | 'select' | 'textarea'
  
  /** Field name (property key) */
  name: string
  
  /** Human-readable label */
  label: string
  
  /** Placeholder text for inputs */
  placeholder?: string
  
  /** Field description/help text */
  description?: string
  
  /** Whether field is required */
  required: boolean
  
  /** Default value */
  default?: any
  
  /** Options for select dropdowns */
  options?: Array<{ label: string; value: any }>
  
  /** Minimum value for numbers */
  min?: number
  
  /** Maximum value for numbers */
  max?: number
  
  /** Step increment for numbers */
  step?: number
}

/**
 * Validation error
 */
export interface ValidationError {
  field: string
  message: string
}

/**
 * DynamicFormGenerator
 * 
 * Converts JSON schema definitions into form field components and provides
 * validation utilities. Main entry point for dynamic form generation in BaseCell.
 * 
 * @example
 * ```typescript
 * const schema = {
 *   prompt: {
 *     type: 'string',
 *     description: 'Enter your prompt',
 *     required: true
 *   },
 *   steps: {
 *     type: 'number',
 *     minimum: 1,
 *     maximum: 100,
 *     default: 20
 *   }
 * }
 * 
 * const fields = DynamicFormGenerator.generateFormFields(schema)
 * // Returns array of FormFieldComponent ready for rendering
 * ```
 */
export class DynamicFormGenerator {
  /**
   * Convert JSON schema properties to form field components
   * 
   * Takes a schema object (typically from type.json properties_schema)
   * and converts it into an array of FormFieldComponent definitions that
   * can be rendered by Vue form components.
   * 
   * @param schema - JSON schema object with property definitions
   * @returns Array of form field components ready for rendering
   */
  static generateFormFields(schema: Record<string, any>): FormFieldComponent[] {
    const fields: FormFieldComponent[] = []

    // Handle nested properties structure (JSON Schema format)
    const properties = schema.properties || schema
    
    for (const [fieldName, fieldSchema] of Object.entries(properties)) {
      const field = this.mapSchemaToFormField(fieldName, fieldSchema as any)
      if (field) {
        fields.push(field)
      }
    }

    return fields
  }

  /**
   * Map a single schema property to a form field component
   * 
   * @param name - Field name
   * @param schema - Field schema definition
   * @returns FormFieldComponent or null if field type not supported
   */
  private static mapSchemaToFormField(
    name: string,
    schema: any
  ): FormFieldComponent | null {
    if (!schema) {
      return null
    }

    const type = schema.type || 'string'
    const required = schema.required !== false // Default: true
    const description = schema.description || ''
    const defaultValue = schema.default || schema.defaultValue

    // Handle enum first (highest priority - overrides type)
    if (schema.enum && Array.isArray(schema.enum)) {
      return {
        type: 'select',
        name,
        label: this.humanize(name),
        description,
        required,
        default: defaultValue,
        options: schema.enum.map((value: any) => ({
          label: String(value),
          value
        }))
      }
    }

    // Handle by type
    switch (type) {
      case 'string':
        // Check if it's a long text (textarea)
        if (schema.maxLength && schema.maxLength > 100) {
          return {
            type: 'textarea',
            name,
            label: this.humanize(name),
            placeholder: defaultValue ? String(defaultValue) : 'Enter text...',
            description,
            required,
            default: defaultValue
          }
        }
        return {
          type: 'text',
          name,
          label: this.humanize(name),
          placeholder: defaultValue ? String(defaultValue) : '',
          description,
          required,
          default: defaultValue
        }

      case 'number':
      case 'integer':
        return {
          type: 'number',
          name,
          label: this.humanize(name),
          description,
          required,
          default: defaultValue,
          min: schema.minimum,
          max: schema.maximum,
          step: type === 'integer' ? 1 : 0.01
        }

      case 'boolean':
        return {
          type: 'checkbox',
          name,
          label: this.humanize(name),
          description,
          required,
          default: defaultValue !== undefined ? defaultValue : false
        }

      case 'array':
      case 'object':
        return {
          type: 'textarea',
          name,
          label: this.humanize(name),
          placeholder: type === 'array' ? 'Enter JSON array...' : 'Enter JSON object...',
          description,
          required,
          default: defaultValue ? JSON.stringify(defaultValue, null, 2) : ''
        }

      default:
        // Unsupported type - return text input as fallback
        return {
          type: 'text',
          name,
          label: this.humanize(name),
          placeholder: '',
          description: description || `Type: ${type}`,
          required,
          default: defaultValue
        }
    }
  }

  /**
   * Convert field name to human-readable label
   * 
   * Transforms snake_case and camelCase into Title Case with spaces.
   * 
   * @param str - Field name to humanize
   * @returns Human-readable label
   * 
   * @example
   * humanize('user_id') // 'User ID'
   * humanize('firstName') // 'First Name'
   * humanize('api_key') // 'Api Key'
   */
  private static humanize(str: string): string {
    return str
      .replace(/_/g, ' ')
      .replace(/([a-z])([A-Z])/g, '$1 $2')
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ')
  }

  /**
   * Validate form data against schema
   * 
   * Validates user input from a form against the original schema definition.
   * Checks required fields, type conformance, and range constraints.
   * 
   * @param data - Form data to validate (key-value pairs)
   * @param schema - JSON schema to validate against
   * @returns Array of validation errors (empty if valid)
   * 
   * @example
   * ```typescript
   * const data = { prompt: '', steps: 150 }
   * const schema = {
   *   prompt: { type: 'string', required: true },
   *   steps: { type: 'number', minimum: 1, maximum: 100 }
   * }
   * const errors = DynamicFormGenerator.validateFormData(data, schema)
   * // Returns: [
   * //   { field: 'prompt', message: 'Prompt is required' },
   * //   { field: 'steps', message: 'Steps must be between 1 and 100' }
   * // ]
   * ```
   */
  static validateFormData(
    data: Record<string, any>,
    schema: Record<string, any>
  ): ValidationError[] {
    const errors: ValidationError[] = []

    // Handle nested properties structure
    const properties = schema.properties || schema

    for (const [fieldName, fieldSchema] of Object.entries(properties)) {
      const schema = fieldSchema as any
      const value = data[fieldName]

      // Check required
      if (schema.required && (value === undefined || value === null || value === '')) {
        errors.push({
          field: fieldName,
          message: `${this.humanize(fieldName)} is required`
        })
        continue
      }

      // Skip validation if field is optional and not provided
      if (value === undefined || value === null || value === '') {
        continue
      }

      // Type validation
      const type = schema.type || 'string'
      switch (type) {
        case 'number':
        case 'integer':
          if (isNaN(Number(value))) {
            errors.push({
              field: fieldName,
              message: `${this.humanize(fieldName)} must be a number`
            })
          } else {
            const numValue = Number(value)
            // Check minimum
            if (schema.minimum !== undefined && numValue < schema.minimum) {
              errors.push({
                field: fieldName,
                message: `${this.humanize(fieldName)} must be at least ${schema.minimum}`
              })
            }
            // Check maximum
            if (schema.maximum !== undefined && numValue > schema.maximum) {
              errors.push({
                field: fieldName,
                message: `${this.humanize(fieldName)} must be at most ${schema.maximum}`
              })
            }
          }
          break

        case 'boolean':
          if (typeof value !== 'boolean') {
            errors.push({
              field: fieldName,
              message: `${this.humanize(fieldName)} must be true or false`
            })
          }
          break

        case 'string':
          // Check minLength
          if (schema.minLength !== undefined && String(value).length < schema.minLength) {
            errors.push({
              field: fieldName,
              message: `${this.humanize(fieldName)} must be at least ${schema.minLength} characters`
            })
          }
          // Check maxLength
          if (schema.maxLength !== undefined && String(value).length > schema.maxLength) {
            errors.push({
              field: fieldName,
              message: `${this.humanize(fieldName)} must be at most ${schema.maxLength} characters`
            })
          }
          // Check enum
          if (schema.enum && !schema.enum.includes(value)) {
            errors.push({
              field: fieldName,
              message: `${this.humanize(fieldName)} must be one of: ${schema.enum.join(', ')}`
            })
          }
          break

        case 'array':
          try {
            if (typeof value === 'string') {
              JSON.parse(value) // Validate JSON
            } else if (!Array.isArray(value)) {
              errors.push({
                field: fieldName,
                message: `${this.humanize(fieldName)} must be an array`
              })
            }
          } catch {
            errors.push({
              field: fieldName,
              message: `${this.humanize(fieldName)} must be valid JSON array`
            })
          }
          break

        case 'object':
          try {
            if (typeof value === 'string') {
              JSON.parse(value) // Validate JSON
            } else if (typeof value !== 'object' || Array.isArray(value)) {
              errors.push({
                field: fieldName,
                message: `${this.humanize(fieldName)} must be an object`
              })
            }
          } catch {
            errors.push({
              field: fieldName,
              message: `${this.humanize(fieldName)} must be valid JSON object`
            })
          }
          break
      }
    }

    return errors
  }
}
