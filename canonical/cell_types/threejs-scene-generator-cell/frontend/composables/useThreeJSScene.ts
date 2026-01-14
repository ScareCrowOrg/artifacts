/**
 * Composable for Three.js scene execution and management.
 * 
 * This composable handles the loading, initialization, and execution of Three.js scenes
 * from generated JavaScript code.
 */

import { ref, onBeforeUnmount, type Ref } from 'vue'

export interface UseThreeJSSceneReturn {
  sceneInitialized: Ref<boolean>
  sceneError: Ref<string | null>
  canvasContainer: Ref<HTMLElement | null>
  loadThreeJS: () => void
  initializeThreeJSScene: (script: string) => void
  cleanup: () => void
}

export function useThreeJSScene(): UseThreeJSSceneReturn {
  const sceneInitialized: Ref<boolean> = ref(false)
  const sceneError: Ref<string | null> = ref(null)
  const canvasContainer: Ref<HTMLElement | null> = ref(null)
  
  // Three.js cleanup function
  let cleanupThreeJS: (() => void) | null = null

  /**
   * Load Three.js library from CDN.
   */
  function loadThreeJS(): void {
    if (typeof (window as any).THREE !== 'undefined') {
      return // Already loaded
    }

    const script = document.createElement('script')
    script.src = 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js'
    script.async = true
    script.onload = () => {
      console.log('Three.js loaded successfully')
    }
    script.onerror = () => {
      sceneError.value = 'Failed to load Three.js library'
    }
    document.head.appendChild(script)
  }

  /**
   * Initialize Three.js scene with generated code.
   */
  function initializeThreeJSScene(script: string): void {
    if (!canvasContainer.value) {
      sceneError.value = 'Canvas container not available'
      return
    }

    // Clear previous scene
    if (cleanupThreeJS) {
      cleanupThreeJS()
    }
    canvasContainer.value.innerHTML = ''
    sceneError.value = null
    sceneInitialized.value = false

    try {
      // Wait for Three.js to be available
      const checkThreeJS = setInterval(() => {
        if (typeof (window as any).THREE !== 'undefined') {
          clearInterval(checkThreeJS)
          executeThreeJSCode(script)
        }
      }, 100)

      // Timeout after 5 seconds
      setTimeout(() => {
        clearInterval(checkThreeJS)
        if (!sceneInitialized.value) {
          sceneError.value = 'Timeout loading Three.js'
        }
      }, 5000)
    } catch (err) {
      sceneError.value = err instanceof Error ? err.message : 'Failed to initialize scene'
      console.error('Three.js initialization error:', err)
    }
  }

  /**
   * Execute Three.js code in a controlled manner.
   */
  function executeThreeJSCode(script: string): void {
    try {
      const container = canvasContainer.value
      if (!container) {
        throw new Error('Container not available')
      }

      // Create a wrapper function to execute the code with container context
      const wrappedCode = `
        (function() {
          const container = arguments[0];
          const THREE = window.THREE;
          ${script}
        })
      `

      // Execute the code
      const executeScene = new Function('return ' + wrappedCode)()
      executeScene(container)

      sceneInitialized.value = true

      // Store cleanup function (if the generated code provides one)
      cleanupThreeJS = () => {
        // Basic cleanup: remove all children from container
        if (container) {
          while (container.firstChild) {
            container.removeChild(container.firstChild)
          }
        }
      }
    } catch (err) {
      sceneError.value = err instanceof Error ? err.message : 'Failed to execute scene code'
      console.error('Three.js execution error:', err)
    }
  }

  /**
   * Cleanup function to be called on unmount.
   */
  function cleanup(): void {
    if (cleanupThreeJS) {
      cleanupThreeJS()
    }
  }

  // Cleanup on unmount
  onBeforeUnmount(() => {
    cleanup()
  })

  return {
    sceneInitialized,
    sceneError,
    canvasContainer,
    loadThreeJS,
    initializeThreeJSScene,
    cleanup
  }
}
