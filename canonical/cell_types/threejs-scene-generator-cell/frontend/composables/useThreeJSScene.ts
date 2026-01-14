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
   * 
   * IMPORTANT: Container must be visible and have dimensions before script execution.
   * This is achieved by setting sceneInitialized=true first, then waiting for browser layout.
   */
  function executeThreeJSCode(script: string): void {
    console.log('[DEBUG] executeThreeJSCode called')
    console.log('[DEBUG] Script length:', script?.length)
    
    try {
      const container = canvasContainer.value
      if (!container) {
        console.error('[DEBUG] Container not available in executeThreeJSCode')
        throw new Error('Container not available')
      }

      // Log container state BEFORE making it visible
      console.log('[DEBUG] Container state BEFORE making visible:', {
        exists: !!container,
        tagName: container.tagName,
        clientWidth: container.clientWidth,
        clientHeight: container.clientHeight,
        offsetWidth: container.offsetWidth,
        offsetHeight: container.offsetHeight,
        display: window.getComputedStyle(container).display,
        visibility: window.getComputedStyle(container).visibility
      })

      // ✅ FIX: Make container visible FIRST
      // This triggers Vue reactivity → v-show becomes true → display:block
      sceneInitialized.value = true
      console.log('[DEBUG] Set sceneInitialized=true to make container visible')
      
      // Log dimensions immediately (will still be 0 - Vue hasn't updated DOM yet)
      console.log('[DEBUG] Container dimensions IMMEDIATELY after setting sceneInitialized:', {
        clientWidth: container.clientWidth,
        clientHeight: container.clientHeight,
        display: window.getComputedStyle(container).display
      })
      
      // ✅ FIX: Wait for browser layout calculation
      // requestAnimationFrame runs before next paint, after layout
      requestAnimationFrame(() => {
        console.log('[DEBUG] Inside first requestAnimationFrame')
        console.log('[DEBUG] Container dimensions after RAF:', {
          clientWidth: container.clientWidth,
          clientHeight: container.clientHeight,
          offsetWidth: container.offsetWidth,
          offsetHeight: container.offsetHeight,
          display: window.getComputedStyle(container).display,
          computedHeight: window.getComputedStyle(container).height,
          computedMinHeight: window.getComputedStyle(container).minHeight
        })
        
        // ✅ FIX: Validate dimensions
        if (container.clientWidth === 0 || container.clientHeight === 0) {
          console.warn('[DEBUG] Container STILL has zero dimensions after first RAF')
          console.warn('[DEBUG] Waiting for second requestAnimationFrame...')
          
          // ✅ FIX: Fallback - wait one more frame
          requestAnimationFrame(() => {
            console.log('[DEBUG] Inside SECOND requestAnimationFrame (fallback)')
            console.log('[DEBUG] Container dimensions after 2nd RAF:', {
              clientWidth: container.clientWidth,
              clientHeight: container.clientHeight,
              display: window.getComputedStyle(container).display
            })
            
            if (container.clientWidth === 0 || container.clientHeight === 0) {
              const error = `Container STILL has zero dimensions after 2 frames: ${container.clientWidth}x${container.clientHeight}`
              console.error('[DEBUG] ❌', error)
              throw new Error(error)
            }
            
            console.log('[DEBUG] ✅ Container has valid dimensions on 2nd frame, proceeding')
            executeActualScript(container, script)
          })
        } else {
          console.log('[DEBUG] ✅ Container has valid dimensions, proceeding with execution')
          executeActualScript(container, script)
        }
      })
    } catch (err) {
      sceneError.value = err instanceof Error ? err.message : 'Failed to execute scene code'
      sceneInitialized.value = false  // Rollback on error
      console.error('[DEBUG] ❌ Three.js execution error:', err)
      console.error('[DEBUG] Error type:', err instanceof Error ? err.constructor.name : typeof err)
      console.error('[DEBUG] Error message:', err instanceof Error ? err.message : String(err))
      console.error('[DEBUG] Error stack:', err instanceof Error ? err.stack : 'No stack trace')
      console.error('[DEBUG] Rolled back sceneInitialized to false')
    }
  }

  /**
   * Execute the actual Three.js script after container has dimensions.
   * Separated into its own function for clarity and testing.
   */
  function executeActualScript(container: HTMLElement, script: string): void {
    console.log('[DEBUG] ═══ EXECUTING SCRIPT ═══')
    console.log('[DEBUG] Final container dimensions before script execution:', {
      clientWidth: container.clientWidth,
      clientHeight: container.clientHeight,
      aspectRatio: (container.clientWidth / container.clientHeight).toFixed(2)
    })
    
    console.log('[DEBUG] Generated script preview (first 300 chars):')
    console.log(script.substring(0, 300) + '...')
    
    try {
      // Create and execute the scene function
      const executeScene = new Function('container', 'THREE', script)
      executeScene(container, (window as any).THREE)
      
      console.log('[DEBUG] ✅ Script execution completed successfully')
      
      // Verify canvas was added
      console.log('[DEBUG] Canvas element added to container:', container.children.length > 0)
      if (container.children.length > 0) {
        const canvas = container.querySelector('canvas')
        if (canvas) {
          console.log('[DEBUG] Canvas dimensions:', {
            width: canvas.width,
            height: canvas.height,
            styleWidth: canvas.style.width,
            styleHeight: canvas.style.height
          })
        }
      }
      
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
      // Re-throw to be caught by parent try-catch
      throw err
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
