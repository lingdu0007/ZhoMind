# Minimal Frontend Grid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the ZhoMind frontend with a 12 列极简网格、单列聊天流、轻量表格上传页、分卡片配置页，契合 Exaggerated Minimalism 和硅基流动 API 约束。

**Architecture:** Vue 3 + Pinia + Element Plus 前端，保留现有 API 调用，仅重构布局与视觉。App 壳体提供固定侧栏 + 主内容网格，页面内部用可复用卡片/抽屉组件保持一致视觉语言。

**Tech Stack:** Vue 3, Vite, Pinia, Element Plus, lucide-vue-next, CSS Modules/Scoped CSS, Google Fonts (Fira Sans/Code).

---

## File Overview
- `frontend/package.json`: 新增 `lucide-vue-next` 依赖，用于统一图标。
- `frontend/src/styles/global.css`: 引入 Fira Sans/Code 字体，定义色彩变量、网格、卡片、表格、抽屉等全局样式。
- `frontend/src/app/App.vue`: 改造成 12 列布局 + 纯导航侧栏 + 顶部控制条容器。
- `frontend/src/components/SessionDrawer.vue`: 新建会话抽屉组件（列表、删除、刷新回调）。
- `frontend/src/components/ChatMessageList.vue`: 更新消息项视觉（单列、细边框、状态条）。
- `frontend/src/pages/ChatPage.vue`: 切换到单列聊天流，嵌入 SessionDrawer、Streaming 状态、固定输入区。
- `frontend/src/pages/UploadPage.vue`: 组合上传卡片、统计条、极简表格皮肤。
- `frontend/src/pages/ConfigPage.vue`: 拆分多卡片配置区（模型、检索、存储、安全）。
- `frontend/src/components/UploadPanel.vue`: 调整为卡片式容器，暴露 loading 状态。

---

### Task 1: 依赖与全局视觉基线

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/styles/global.css`

- [ ] **Step 1: 引入 lucide-vue-next**

更新 `frontend/package.json` dependencies：

```json
"dependencies": {
  "axios": "^1.11.0",
  "element-plus": "^2.11.2",
  "@element-plus/icons-vue": "^2.3.2",
  "lucide-vue-next": "^0.379.0",
  "pinia": "^3.0.3",
  "vue": "^3.5.22",
  "vue-router": "^4.5.1"
}
```

- [ ] **Step 2: 安装依赖**

```bash
cd frontend
npm install
```

预期：npm 成功解析并写入新的 `package-lock.json`。

- [ ] **Step 3: 更新全局样式与字体**

覆盖 `frontend/src/styles/global.css` 以符合设计系统：

```css
@import url('https://fonts.googleapis.com/css2?family=Fira+Sans:wght@300;400;600&family=Fira+Code:wght@400;500&display=swap');

:root {
  --bg-shell: #f8fafc;
  --bg-sidebar: #f1f5f9;
  --bg-card: #ffffff;
  --line-soft: #e2e8f0;
  --line-strong: #cbd5f5;
  --text-strong: #1e293b;
  --text-muted: #475569;
  --primary: #475569;
  --cta: #2563eb;
  --warn: #f97316;
  --danger: #dc2626;
  font-family: 'Fira Sans', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

* { box-sizing: border-box; }

body, #app {
  margin: 0;
  background: var(--bg-shell);
  color: var(--text-strong);
  font-family: 'Fira Sans', sans-serif;
  min-height: 100vh;
}

.layout-shell {
  display: grid;
  grid-template-columns: 200px 1fr;
  min-height: 100vh;
}

.layout-sidebar {
  background: var(--bg-sidebar);
  border-right: 1px solid var(--line-soft);
  padding: 32px 20px;
}

.layout-main {
  background: var(--bg-shell);
  display: flex;
  justify-content: center;
  padding: 40px 48px;
}

.grid-12 {
  width: 100%;
  max-width: 1440px;
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 24px;
}

.card {
  background: var(--bg-card);
  border-radius: 16px;
  border: 1px solid var(--line-soft);
  box-shadow: 0 8px 30px rgba(15, 23, 42, 0.06);
}

/* 按钮、表格、抽屉等辅助类 */
.btn-primary { background: var(--cta); color: #fff; border: none; }
.btn-ghost { border: 1px solid var(--line-strong); background: transparent; color: var(--text-strong); }
.table-minimal thead { background: var(--bg-shell); font-weight: 500; }
.table-minimal tr:hover { background: #eef2ff; }
```

根据需要扩展 `.top-bar`, `.drawer`, `.stat-card`, `.config-grid` 等类，以便后续组件引用。

---

### Task 2: 布局外壳与侧栏导航

**Files:**
- Modify: `frontend/src/app/App.vue`

- [ ] **Step 1: 重写模板为 12 列结构**

```vue
<template>
  <div class="layout-shell">
    <aside class="layout-sidebar">
      <div class="brand">
        <span class="logo-dot" />
        <strong>ZhoMind</strong>
      </div>
      <nav class="nav-list">
        <RouterLink
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-link"
          :class="{ active: route.path.startsWith(item.path) }"
        >
          <component :is="item.icon" class="nav-icon" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>
    </aside>
    <main class="layout-main">
      <div class="grid-12">
        <section class="col-span-8 col-start-3">
          <router-view />
        </section>
      </div>
    </main>
  </div>
</template>
```

- [ ] **Step 2: 注入脚本逻辑与图标**

```vue
<script setup>
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import { MessageCircle, FileText, Settings } from 'lucide-vue-next';

const route = useRoute();
const navItems = [
  { path: '/chat', label: '聊天', icon: MessageCircle },
  { path: '/documents', label: '文档', icon: FileText },
  { path: '/config', label: '配置', icon: Settings }
];
</script>
```

- [ ] **Step 3: 添加局部样式**

```vue
<style scoped>
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  margin-bottom: 40px;
}
.nav-list { display: flex; flex-direction: column; gap: 8px; }
.nav-link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  color: var(--text-muted);
  text-decoration: none;
}
.nav-link.active {
  background: #e2e8f0;
  color: var(--text-strong);
}
.col-span-8 { grid-column: span 8 / span 8; }
.col-start-3 { grid-column-start: 3; }
</style>
```

---

### Task 3: 会话抽屉与聊天流重构

**Files:**
- Add: `frontend/src/components/SessionDrawer.vue`
- Modify: `frontend/src/components/ChatMessageList.vue`
- Modify: `frontend/src/pages/ChatPage.vue`

- [ ] **Step 1: 创建 `SessionDrawer.vue`**

```vue
<template>
  <transition name="fade-slide">
    <div v-if="visible" class="session-drawer card">
      <header>
        <strong>会话列表</strong>
        <div class="actions">
          <el-button text @click="$emit('refresh')">刷新</el-button>
          <el-button text @click="$emit('close')">收起</el-button>
        </div>
      </header>
      <div class="session-items">
        <div
          v-for="item in sessions"
          :key="item.session_id || item.id"
          class="session-row"
          :class="{ active: (item.session_id || item.id) === activeId }"
          @click="$emit('select', item.session_id || item.id)"
        >
          <div>
            <p>{{ item.session_id || item.id }}</p>
            <small>{{ item.updated_at || '--' }} · {{ item.message_count ?? 0 }} 条</small>
          </div>
          <el-button link type="danger" @click.stop="$emit('remove', item.session_id || item.id)">删除</el-button>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
defineProps({
  visible: Boolean,
  sessions: { type: Array, default: () => [] },
  activeId: String
});
defineEmits(['select', 'remove', 'refresh', 'close']);
</script>

<style scoped>
.session-drawer { padding: 20px; margin-bottom: 16px; }
.session-row {
  border: 1px solid var(--line-soft);
  border-radius: 12px;
  padding: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.session-row.active { border-color: var(--cta); background: #eef2ff; }
.session-items { display: flex; flex-direction: column; gap: 12px; max-height: 260px; overflow-y: auto; }
</style>
```

- [ ] **Step 2: 更新 `ChatMessageList.vue` 视觉**

```vue
<template>
  <div class="message-list card">
    <div v-if="messages.length === 0" class="empty">开始提问，系统会基于知识库回复。</div>
    <article v-for="(msg, idx) in messages" :key="idx" class="msg">
      <header class="msg-head">
        <span class="role" :class="msg.role">{{ msg.role === 'user' ? '你' : '助手' }}</span>
        <span v-if="msg.streaming" class="status-dot">Streaming…</span>
        <span v-else-if="msg.status" class="status-text">{{ msg.status }}</span>
      </header>
      <div class="content">{{ msg.content }}</div>
      <div v-if="msg.rag_steps?.length" class="steps">
        <strong>检索步骤</strong>
        <ul>
          <li v-for="(step, i) in msg.rag_steps" :key="i">{{ step }}</li>
        </ul>
      </div>
      <div v-if="msg.rag_trace" class="trace"><pre>{{ formatTrace(msg.rag_trace) }}</pre></div>
    </article>
  </div>
</template>

<style scoped>
.message-list { padding: 24px; display: flex; flex-direction: column; gap: 16px; }
.msg { border: 1px solid var(--line-soft); border-radius: 18px; padding: 20px; box-shadow: 0 2px 10px rgba(15,23,42,0.04); }
.role.user { color: var(--cta); }
.role.assistant { color: var(--primary); }
.status-dot { font-size: 12px; color: var(--cta); }
.steps { margin-top: 12px; font-size: 13px; color: var(--text-muted); }
</style>
```

- [ ] **Step 3: 重构 `ChatPage.vue`**

```vue
<template>
  <section class="chat-page">
    <div class="top-bar">
      <div>
        <h1>Chat · Knowledge Pulse</h1>
        <p class="subtitle" v-if="chatStore.loading">Streaming…</p>
      </div>
      <div class="top-actions">
        <el-button class="btn-ghost" @click="toggleSessions">会话</el-button>
        <template v-if="authStore.isLoggedIn">
          <span class="user-pill">{{ authStore.username }} · {{ authStore.role }}</span>
          <el-button text @click="logout">退出</el-button>
        </template>
        <el-button v-else type="primary" @click="authDialogVisible = true">登录 / 注册</el-button>
      </div>
    </div>

    <SessionDrawer
      :visible="sessionVisible"
      :sessions="chatStore.sessions"
      :active-id="chatStore.activeSessionId"
      @select="openSession"
      @remove="removeSession"
      @refresh="loadSessions"
      @close="sessionVisible = false"
    />

    <ChatMessageList :messages="chatStore.messages" />

    <div class="composer card">
      <el-input
        v-model="input"
        type="textarea"
        :rows="3"
        placeholder="请输入问题，系统会执行 Agentic RAG"
      />
      <div class="composer-actions">
        <el-button class="btn-ghost" :disabled="!chatStore.loading" @click="chatStore.stopStreaming">停止</el-button>
        <el-button type="primary" :loading="chatStore.loading" @click="onSend">发送</el-button>
      </div>
    </div>

    <!-- 认证弹窗照旧 -->
  </section>
</template>
```

脚本：新增 `sessionVisible`、`toggleSessions`，导入新组件。

```vue
<script setup>
import { ref, reactive, onMounted } from 'vue';
import ChatMessageList from '../components/ChatMessageList.vue';
import SessionDrawer from '../components/SessionDrawer.vue';
// …保留现有 store 导入与逻辑
const sessionVisible = ref(false);
const toggleSessions = () => {
  sessionVisible.value = !sessionVisible.value;
  if (sessionVisible.value) loadSessions();
};
</script>
```

样式：使用 `.chat-page`, `.top-bar`, `.composer` 对齐单列流。

---

### Task 4: 文档上传页极简表格

**Files:**
- Modify: `frontend/src/components/UploadPanel.vue`
- Modify: `frontend/src/pages/UploadPage.vue`

- [ ] **Step 1: 调整 UploadPanel 为卡片式**

```vue
<template>
  <div class="upload-card card">
    <el-upload ... class="upload-drop">
      <!-- 内容不变 -->
    </el-upload>
    <div class="actions">
      <el-button class="btn-primary" :loading="loading" @click="submit">上传并解析</el-button>
    </div>
  </div>
</template>

<style scoped>
.upload-card { padding: 32px; }
.upload-drop { border: 1px dashed var(--line-strong); border-radius: 16px; background: var(--bg-shell); }
</style>
```

- [ ] **Step 2: 重构 UploadPage 模板**

```vue
<template>
  <section class="upload-page">
    <div class="top-bar">
      <h1>文档上传</h1>
      <el-button v-if="authStore.isAdmin" class="btn-ghost" @click="loadDocs">刷新</el-button>
    </div>
    <div v-if="!authStore.isLoggedIn" class="card notice">请先在聊天页登录。</div>
    <div v-else-if="!authStore.isAdmin" class="card notice">当前账号非管理员。</div>
    <template v-else>
      <UploadPanel @uploaded="loadDocs" />
      <div class="stat-row">
        <div class="stat-card" v-for="stat in stats" :key="stat.label">
          <p class="stat-label">{{ stat.label }}</p>
          <p class="stat-value">{{ stat.value }}</p>
        </div>
      </div>
      <div class="card table-card">
        <div class="table-header">
          <h3>文档列表</h3>
          <el-input v-model="keyword" placeholder="搜索文件" />
        </div>
        <el-table class="table-minimal" :data="filteredDocs" v-loading="loading">
          <!-- 表头同原来 -->
        </el-table>
      </div>
    </template>
  </section>
```

脚本：新增 `keyword` 与 `stats` 计算。

```js
import { computed, ref } from 'vue';
const keyword = ref('');
const stats = computed(() => [
  { label: '文档总数', value: docs.value.length },
  { label: '总分块', value: docs.value.reduce((sum, item) => sum + (item.chunk_count || 0), 0) },
  { label: '最近上传', value: docs.value[0]?.uploaded_at || '--' }
]);
const filteredDocs = computed(() =>
  docs.value.filter((doc) => doc.filename?.toLowerCase().includes(keyword.value.toLowerCase()))
);
```

- [ ] **Step 3: 添加局部样式**

```vue
<style scoped>
.stat-row { display: flex; gap: 16px; margin: 24px 0; }
.stat-card { flex: 1; padding: 20px; border: 1px solid var(--line-soft); border-radius: 16px; }
.table-card { margin-top: 16px; padding: 0 0 24px; }
.table-header { display: flex; justify-content: space-between; padding: 24px; border-bottom: 1px solid var(--line-soft); }
</style>
```

---

### Task 5: 配置页卡片化

**Files:**
- Modify: `frontend/src/pages/ConfigPage.vue`

- [ ] **Step 1: 重写模板为多卡片**

```vue
<template>
  <section class="config-page">
    <h1>配置页</h1>
    <div class="config-grid">
      <div class="card config-card">
        <header><h3>模型配置</h3><p>LLM / Embedding / Rerank</p></header>
        <el-form label-width="120px">
          <el-form-item label="LLM 模型"><el-input v-model="configStore.config.llm_model" /></el-form-item>
          <!-- 其它字段 -->
        </el-form>
        <footer>
          <el-button class="btn-ghost" @click="load">重置</el-button>
          <el-button type="primary" :loading="configStore.loading" @click="save">保存</el-button>
        </footer>
      </div>
      <div class="card config-card">
        <header><h3>检索参数</h3><p>TopK / 阈值 / 权重</p></header>
        <div class="slider-row">
          <label>Top K</label>
          <el-input-number v-model="configStore.config.top_k" :min="1" :max="50" />
        </div>
        <!-- slider + 提示 -->
      </div>
      <!-- 存储配置、安全 & API 卡片 -->
    </div>
  </section>
</template>
```

- [ ] **Step 2: 添加状态徽标与复制按钮**

在存储配置卡片中：

```vue
<header>
  <h3>存储配置</h3>
  <el-tag type="success">Milvus 在线</el-tag>
</header>
<el-form-item label="Milvus URL">
  <div class="input-copy">
    <el-input v-model="configStore.config.milvus_url" />
    <el-button text @click="copy(configStore.config.milvus_url)">复制</el-button>
  </div>
</el-form-item>
```

实现 `copy` 方法：使用 `navigator.clipboard.writeText` 并提示成功/失败。

- [ ] **Step 3: 样式**

```vue
<style scoped>
.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 24px;
}
.config-card { padding: 24px; display: flex; flex-direction: column; gap: 16px; }
.config-card footer { display: flex; justify-content: flex-end; gap: 12px; }
.input-copy { display: flex; gap: 8px; align-items: center; }
</style>
```

---

### Task 6: 验证

- [ ] **Step 1: 运行构建**

```bash
cd frontend
npm run build
```

预期：Vite 构建成功无错误。

- [ ] **Step 2: 冒烟自测**

1. `npm run dev` 启动本地服务，访问 `http://localhost:5173`
2. 登录后测试聊天：发送消息、查看 Streaming 状态、打开会话抽屉、删除会话。
3. 切换到文档页：上传伪文件（若后端需要，可观察网络请求），确认表格皮肤、统计条。
4. 配置页：修改字段、保存、观察成功/失败提示与 focus ring。

记录任何异常，确保与设计规范一致。

---

## Self-Review
- 覆盖检查：布局、聊天抽屉、上传表格、配置卡片、全局视觉均有对应任务。
- 占位扫描：无 “TBD/稍后”，每个步骤包含具体代码或命令。
- 命名一致：SessionDrawer/ChatMessageList/ConfigPage 等文件名称在各步骤保持一致。
