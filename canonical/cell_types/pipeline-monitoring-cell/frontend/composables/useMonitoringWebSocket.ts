/**
 * useMonitoringWebSocket Composable
 * 
 * Manages WebSocket connection for real-time monitoring updates.
 * Subscribes to monitoring events and updates local state.
 * 
 * Sprint 3: WebSocket Streaming for Pipeline Monitoring Cell
 * 
 * @module composables/useMonitoringWebSocket
 */

import { ref, onUnmounted, type Ref } from 'vue'
import { createLogger } from '@/utils/logger'

const log = createLogger('composable:useMonitoringWebSocket')

/**
 * WebSocket connection state
 */
type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'error'

/**
 * Monitoring event types
 */
interface MonitoringEvent {
  trace_id: string
  source: string
  topic: string
  payload: any
  timestamp: string
}

/**
 * Event handlers for monitoring updates
 */
interface MonitoringEventHandlers {
  onHealthUpdate?: (payload: any) => void
  onMetricsUpdate?: (payload: any) => void
  onPrerequisiteUpdate?: (payload: any) => void
  onAlertTriggered?: (payload: any) => void
  onAlertResolved?: (payload: any) => void
}

// Shared state
const connectionState: Ref<ConnectionState> = ref('disconnected')
const lastError: Ref<string | null> = ref(null)
let websocket: WebSocket | null = null
let reconnectTimeout: NodeJS.Timeout | null = null
let eventHandlers: MonitoringEventHandlers = {}

/**
 * useMonitoringWebSocket composable
 * 
 * Provides WebSocket connection management for real-time monitoring updates
 */
export function useMonitoringWebSocket() {
  /**
   * Connect to monitoring WebSocket
   * 
   * @param handlers Event handlers for monitoring updates
   */
  function connect(handlers: MonitoringEventHandlers = {}) {
    if (websocket && connectionState.value === 'connected') {
      log.warn('WebSocket already connected')
      return
    }
    
    eventHandlers = handlers
    connectionState.value = 'connecting'
    lastError.value = null
    
    try {
      // Get auth token from localStorage (assuming it's stored there)
      const token = localStorage.getItem('auth_token')
      
      if (!token) {
        log.error('No auth token found')
        connectionState.value = 'error'
        lastError.value = 'Authentication token not found'
        return
      }
      
      // Build WebSocket URL
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = window.location.host
      const wsUrl = `${protocol}//${host}/api/v1/ws/event-bus?token=${encodeURIComponent(token)}`
      
      log.info('Connecting to WebSocket', { url: wsUrl.replace(/token=[^&]+/, 'token=***') })
      
      websocket = new WebSocket(wsUrl)
      
      websocket.onopen = handleOpen
      websocket.onmessage = handleMessage
      websocket.onerror = handleError
      websocket.onclose = handleClose
      
    } catch (error) {
      log.error('Failed to create WebSocket connection', { error })
      connectionState.value = 'error'
      lastError.value = error instanceof Error ? error.message : 'Unknown error'
    }
  }
  
  /**
   * Disconnect from WebSocket
   */
  function disconnect() {
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout)
      reconnectTimeout = null
    }
    
    if (websocket) {
      websocket.close()
      websocket = null
    }
    
    connectionState.value = 'disconnected'
    log.info('WebSocket disconnected')
  }
  
  /**
   * Handle WebSocket open event
   */
  function handleOpen() {
    connectionState.value = 'connected'
    lastError.value = null
    log.info('WebSocket connected successfully')
  }
  
  /**
   * Handle incoming WebSocket message
   */
  function handleMessage(event: MessageEvent) {
    try {
      const message: MonitoringEvent = JSON.parse(event.data)
      
      log.debug('Received WebSocket message', { topic: message.topic })
      
      // Route message to appropriate handler
      switch (message.topic) {
        case 'monitoring/health/update':
          if (eventHandlers.onHealthUpdate) {
            eventHandlers.onHealthUpdate(message.payload)
          }
          break
        
        case 'monitoring/metrics/update':
          if (eventHandlers.onMetricsUpdate) {
            eventHandlers.onMetricsUpdate(message.payload)
          }
          break
        
        case 'monitoring/prerequisite/update':
          if (eventHandlers.onPrerequisiteUpdate) {
            eventHandlers.onPrerequisiteUpdate(message.payload)
          }
          break
        
        case 'monitoring/alert/triggered':
          if (eventHandlers.onAlertTriggered) {
            eventHandlers.onAlertTriggered(message.payload)
          }
          break
        
        case 'monitoring/alert/resolved':
          if (eventHandlers.onAlertResolved) {
            eventHandlers.onAlertResolved(message.payload)
          }
          break
        
        case 'system/event/heartbeat':
          // Respond to heartbeat
          sendHeartbeat()
          break
        
        default:
          log.debug('Unhandled message topic', { topic: message.topic })
      }
      
    } catch (error) {
      log.error('Error parsing WebSocket message', { error })
    }
  }
  
  /**
   * Handle WebSocket error
   */
  function handleError(event: Event) {
    log.error('WebSocket error', { event })
    connectionState.value = 'error'
    lastError.value = 'WebSocket connection error'
  }
  
  /**
   * Handle WebSocket close event
   */
  function handleClose(event: CloseEvent) {
    log.info('WebSocket closed', { code: event.code, reason: event.reason })
    
    connectionState.value = 'disconnected'
    websocket = null
    
    // Attempt reconnection after delay (exponential backoff)
    if (event.code !== 1000) { // 1000 = normal closure
      const delay = 5000 // 5 seconds
      log.info(`Attempting reconnection in ${delay}ms`)
      
      reconnectTimeout = setTimeout(() => {
        connect(eventHandlers)
      }, delay)
    }
  }
  
  /**
   * Send heartbeat message to keep connection alive
   */
  function sendHeartbeat() {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      const heartbeat = {
        source: 'monitoring-dashboard',
        topic: 'system/event/heartbeat',
        payload: {
          status: 'alive',
          timestamp: Date.now()
        }
      }
      
      websocket.send(JSON.stringify(heartbeat))
      log.debug('Heartbeat sent')
    }
  }
  
  // Clean up on unmount
  onUnmounted(() => {
    disconnect()
  })
  
  return {
    connectionState,
    lastError,
    connect,
    disconnect
  }
}
