/**
 * Tailwind CSS Configuration for ScareVerse Artifacts & Shared Components
 *
 * This configuration maps Tailwind color utilities to CSS variables defined in src/styles/variables.css.
 * Scans both artifacts/shared (mounted volume) and cell viewers for Tailwind classes.
 *
 * Dark Mode Strategy:
 * - The project uses [data-theme='dark'] attribute for dark mode switching
 * - CSS variables (e.g., --color-surface) automatically change values when [data-theme='dark'] is set
 * - Therefore, -dark suffixed Tailwind classes (e.g., surface-dark) reference the SAME CSS variables
 * - This ensures colors automatically adapt to the active theme without duplicate variable definitions
 */
module.exports = {
  content: [
    './index.html',
    // With root=/app/artifacts, content paths are relative to vite.config root
    // Scans specific artifact types, not all files (performance optimization)
    './canonical/cell_types/**/*.{vue,jsx,tsx}',
    './canonical/viewers/**/*.{vue,jsx,tsx}',
    './canonical/book_types/**/*.{vue,jsx,tsx}',
    './sandbox/cell_types/**/*.{vue,jsx,tsx}',
    './sandbox/viewers/**/*.{vue,jsx,tsx}',
    './runtime/**/*.{vue,jsx,tsx}',
    './shared/**/*.{vue,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Primary colors (with opacity support using rgb() format)
        primary: {
          DEFAULT: 'rgb(var(--color-primary-rgb) / <alpha-value>)',
          hover: 'rgb(var(--color-primary-hover-rgb) / <alpha-value>)',
          light: 'rgb(var(--color-primary-light-rgb) / <alpha-value>)',
          dark: 'rgb(var(--color-primary-dark-rgb) / <alpha-value>)',
        },
        // Secondary colors
        secondary: {
          DEFAULT: 'rgb(var(--color-secondary-rgb) / <alpha-value>)',
          hover: 'rgb(var(--color-secondary-hover-rgb) / <alpha-value>)',
        },
        // Surface colors
        surface: {
          DEFAULT: 'rgb(var(--color-surface-rgb) / <alpha-value>)',
          hover: 'rgb(var(--color-surface-hover-rgb) / <alpha-value>)',
          dark: 'rgb(var(--color-surface-rgb) / <alpha-value>)',
        },
        // Background colors
        background: {
          DEFAULT: 'rgb(var(--color-background-rgb) / <alpha-value>)',
          dark: 'rgb(var(--color-background-rgb) / <alpha-value>)',
        },
        // Text colors
        text: {
          primary: 'rgb(var(--color-text-primary-rgb) / <alpha-value>)',
          secondary: 'rgb(var(--color-text-secondary-rgb) / <alpha-value>)',
          tertiary: 'rgb(var(--color-text-tertiary-rgb) / <alpha-value>)',
          'on-primary': 'rgb(var(--color-text-on-primary-rgb) / <alpha-value>)',
          'primary-dark': 'rgb(var(--color-text-primary-rgb) / <alpha-value>)',
          'secondary-dark': 'rgb(var(--color-text-secondary-rgb) / <alpha-value>)',
          'tertiary-dark': 'rgb(var(--color-text-tertiary-rgb) / <alpha-value>)',
        },
        // Semantic text colors (aliases for pipeline-monitoring-cell compatibility)
        foreground: 'rgb(var(--color-text-primary-rgb) / <alpha-value>)',
        'muted-foreground': 'rgb(var(--color-text-secondary-rgb) / <alpha-value>)',
        // Border colors
        border: {
          DEFAULT: 'rgb(var(--color-border-rgb) / <alpha-value>)',
          light: 'rgb(var(--color-border-light-rgb) / <alpha-value>)',
          dark: 'rgb(var(--color-border-rgb) / <alpha-value>)',
        },
        divider: 'rgb(var(--color-divider-rgb) / <alpha-value>)',
        // Status colors
        success: {
          DEFAULT: 'rgb(var(--color-success-rgb) / <alpha-value>)',
          light: 'rgb(var(--color-success-light-rgb) / <alpha-value>)',
          dark: 'rgb(var(--color-success-dark-rgb) / <alpha-value>)',
        },
        error: {
          DEFAULT: 'rgb(var(--color-error-rgb) / <alpha-value>)',
          light: 'rgb(var(--color-error-light-rgb) / <alpha-value>)',
          dark: 'rgb(var(--color-error-dark-rgb) / <alpha-value>)',
        },
        warning: {
          DEFAULT: 'rgb(var(--color-warning-rgb) / <alpha-value>)',
          light: 'rgb(var(--color-warning-light-rgb) / <alpha-value>)',
        },
        info: {
          DEFAULT: 'rgb(var(--color-info-rgb) / <alpha-value>)',
          light: 'rgb(var(--color-info-light-rgb) / <alpha-value>)',
        },
      },
      spacing: {
        xs: '0.25rem',
        sm: '0.5rem',
        md: '1rem',
        lg: '1.5rem',
        xl: '2rem',
        '2xl': '3rem',
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'sans-serif',
        ],
        mono: ['Fira Mono', 'Courier New', 'monospace'],
      },
    },
  },
  plugins: [require('@tailwindcss/forms'), require('@tailwindcss/typography')],
  darkMode: 'class',
}
