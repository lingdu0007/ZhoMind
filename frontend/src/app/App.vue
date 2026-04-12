<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">ZhoMind</div>
      <el-menu :default-active="activePath" router class="menu">
        <el-menu-item index="/chat">聊天</el-menu-item>
        <el-menu-item index="/documents">文档上传</el-menu-item>
        <el-menu-item index="/config">配置页</el-menu-item>
      </el-menu>
    </aside>
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();
const activePath = computed(() => route.path);
</script>

<style scoped>
.app-shell {
  display: grid;
  grid-template-columns: 220px 1fr;
  min-height: 100vh;
  background: var(--color-bg);
}

.sidebar {
  border-right: 1px solid var(--color-border);
  background: #fff;
  padding: 20px 12px;
}

.brand {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-primary);
  margin-bottom: 24px;
  padding: 0 12px;
}

.menu {
  border-right: none;
}

.main-content {
  padding: 20px;
  overflow: auto;
}
</style>
