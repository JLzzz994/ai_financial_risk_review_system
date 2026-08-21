<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppNavBar from '@/components/AppNavBar.vue'
import AppToasts from '@/components/AppToasts.vue'

const route = useRoute()
const isPlainLayout = computed(() => route.meta.public === true)
</script>

<template>
  <AppToasts />
  <template v-if="isPlainLayout">
    <RouterView />
  </template>
  <template v-else>
    <AppNavBar />
    <main class="app-main">
      <RouterView />
    </main>
  </template>
</template>

<style scoped>
.app-main {
  min-height: calc(100vh - var(--nav-height));
}
</style>
