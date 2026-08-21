import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface ToastItem {
  id: number
  type: 'success' | 'error' | 'info' | 'warning'
  message: string
  duration: number
}

let nextToastId = 1

export const useAppStore = defineStore('app', () => {
  const toasts = ref<ToastItem[]>([])

  function push(type: ToastItem['type'], message: string, duration = 3600): void {
    const id = nextToastId++
    toasts.value.push({ id, type, message, duration })
    if (duration > 0) {
      window.setTimeout(() => remove(id), duration)
    }
  }

  function remove(id: number): void {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }

  return {
    toasts,
    push,
    remove,
  }
})
