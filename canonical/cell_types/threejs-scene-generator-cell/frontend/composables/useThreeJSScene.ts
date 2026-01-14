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
    console.log('[DEBUG] loadThreeJS called')
    console.log('[DEBUG] Checking if THREE is already loaded:', typeof (window as any).THREE !== 'undefined')
    
    if (typeof (window as any).THREE !== 'undefined') {
      console.log('[DEBUG] Three.js already loaded, skipping')
      return // Already loaded
    }

    console.log('[DEBUG] Loading Three.js from CDN')
    const script = document.createElement('script')
    script.src = 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js'
    script.async = true
    script.onload = () => {
      console.log('[DEBUG] Three.js loaded successfully from CDN')
      console.log('[DEBUG] THREE namespace available:', typeof (window as any).THREE !== 'undefined')
    }
    script.onerror = () => {
      console.error('[DEBUG] Failed to load Three.js library from CDN')
      sceneError.value = 'Failed to load Three.js library'
    }
    document.head.appendChild(script)
    console.log('[DEBUG] Script tag added to document head')
  }

  /**
   * Initialize Three.js scene with generated code.
   */
  function initializeThreeJSScene(script: string): void {
    console.log('[DEBUG] initializeThreeJSScene called')
    console.log('[DEBUG] Script length:', script?.length)
    console.log('[DEBUG] Script preview (first 200 chars):', script?.substring(0, 200))
    console.log('[DEBUG] canvasContainer.value state:', canvasContainer.value ? 'EXISTS' : 'NULL')
    
    if (!canvasContainer.value) {
      console.error('[DEBUG] Canvas container not available - EARLY RETURN')
      sceneError.value = 'Canvas container not available'
      return
    }

    // Clear previous scene
    if (cleanupThreeJS) {
      console.log('[DEBUG] Calling cleanup function for previous scene')
      cleanupThreeJS()
    }
    
    console.log('[DEBUG] Clearing container innerHTML')
    canvasContainer.value.innerHTML = ''
    sceneError.value = null
    sceneInitialized.value = false

    try {
      console.log('[DEBUG] Starting Three.js availability check interval')
      const checkStartTime = Date.now()
      
      // Wait for Three.js to be available
      const checkThreeJS = setInterval(() => {
        const elapsed = Date.now() - checkStartTime
        const threeJSAvailable = typeof (window as any).THREE !== 'undefined'
        
        console.log(`[DEBUG] Checking Three.js availability at ${elapsed}ms: ${threeJSAvailable ? 'AVAILABLE' : 'NOT YET'}`)
        
        if (threeJSAvailable) {
          clearInterval(checkThreeJS)
          console.log('[DEBUG] Three.js is available, calling executeThreeJSCode')
          executeThreeJSCode(script)
        }
      }, 100)

      // Timeout after 5 seconds
      setTimeout(() => {
        clearInterval(checkThreeJS)
        if (!sceneInitialized.value) {
          console.error('[DEBUG] Timeout reached after 5 seconds - Three.js not initialized')
          sceneError.value = 'Timeout loading Three.js'
        }
      }, 5000)
    } catch (err) {
      sceneError.value = err instanceof Error ? err.message : 'Failed to initialize scene'
      console.error('[DEBUG] Three.js initialization error:', err)
      console.error('[DEBUG] Error stack:', err instanceof Error ? err.stack : 'No stack trace')
    }
  }

  /**
   * Execute Three.js code in a controlled manner.
   */
  function executeThreeJSCode(script: string): void {
    console.log('[DEBUG] executeThreeJSCode called')
    console.log('[DEBUG] Full generated script:')
    console.log('--- SCRIPT START ---')
    console.log(script)
    console.log('--- SCRIPT END ---')
    
    try {
      const container = canvasContainer.value
      console.log('[DEBUG] Container state in executeThreeJSCode:', container ? 'EXISTS' : 'NULL')
      console.log('[DEBUG] Container details:', {
        tagName: container?.tagName,
        clientWidth: container?.clientWidth,
        clientHeight: container?.clientHeight,
        childCount: container?.children.length
      })
      
      if (!container) {
        console.error('[DEBUG] Container not available in executeThreeJSCode')
        throw new Error('Container not available')
      }

      // Simplified approach: Create a function with named parameters
      // This avoids the complex IIFE wrapping and is more reliable
      console.log('[DEBUG] Creating function with named parameters')
      const executeScene = new Function('container', 'THREE', script)
      
      console.log('[DEBUG] Function created successfully')
      console.log('[DEBUG] Executing scene code with container and THREE as parameters')
      
      // Execute the function with container and THREE as arguments
      executeScene(container, (window as any).THREE)
      
      console.log('[DEBUG] Scene execution completed successfully')

      sceneInitialized.value = true
      console.log('[DEBUG] Scene initialized successfully, sceneInitialized set to true')

      // Store cleanup function
      cleanupThreeJS = () => {
        console.log('[DEBUG] Cleanup function called')
        if (container) {
          // Remove all children (canvas elements)
          while (container.firstChild) {
            container.removeChild(container.firstChild)
          }
          console.log('[DEBUG] Container cleaned, all children removed')
        }
      }
    } catch (err) {
      sceneError.value = err instanceof Error ? err.message : 'Failed to execute scene code'
      console.error('[DEBUG] Three.js execution error:', err)
      console.error('[DEBUG] Error type:', err instanceof Error ? err.constructor.name : typeof err)
      console.error('[DEBUG] Error message:', err instanceof Error ? err.message : String(err))
      console.error('[DEBUG] Error stack:', err instanceof Error ? err.stack : 'No stack trace')
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
