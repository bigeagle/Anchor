<script setup lang="ts">
import { RouterView } from 'vue-router';
</script>

<template>
  <div class="flex h-full flex-col bg-gray-50">
    <header class="shrink-0 border-b border-gray-200 bg-white shadow-sm">
      <div class="flex items-center gap-3 px-6 py-3">
        <router-link to="/" class="flex items-center gap-2 text-gray-900">
          <span class="text-xl">⚓</span>
          <span class="text-lg font-bold">Anchor 资料库</span>
        </router-link>
        <span class="text-xs text-gray-400">个人参考文献管理</span>
      </div>
    </header>

    <main class="min-h-0 flex-1">
      <RouterView />
    </main>
  </div>
</template>
