<template>
  <div ref="listRef" class="message-list panel">
    <div v-if="messages.length === 0" class="empty">开始提问，系统会基于知识库回复。</div>
    <div v-for="(msg, idx) in messages" :key="idx" class="msg" :class="msg.role">
      <div class="role">{{ msg.role === 'user' ? '你' : '助手' }}</div>
      <div class="content">{{ msg.content }}</div>

      <div v-if="msg.isThinking" class="stream-status">思考中...</div>
      <div v-else-if="msg.streaming || msg.status" class="stream-status">{{ msg.status || '生成中...' }}</div>

      <div v-if="msg.rag_steps?.length" class="steps">
        <div class="ref-title">检索步骤：</div>
        <ul>
          <li v-for="(step, i) in msg.rag_steps" :key="i">{{ step }}</li>
        </ul>
      </div>

      <div v-if="msg.rag_trace" class="trace">
        <el-collapse>
          <el-collapse-item title="RAG Trace" name="trace">
            <pre>{{ formatTrace(msg.rag_trace) }}</pre>
          </el-collapse-item>
        </el-collapse>
      </div>
    </div>
  </div>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue';

const listRef = ref(null);

const formatTrace = (trace) => {
  if (typeof trace === 'string') return trace;
  try {
    return JSON.stringify(trace, null, 2);
  } catch {
    return String(trace);
  }
};

const props = defineProps({
  messages: {
    type: Array,
    default: () => []
  }
});

const scrollToBottom = async () => {
  await nextTick();
  if (!listRef.value) return;
  listRef.value.scrollTop = listRef.value.scrollHeight;
};

watch(
  () => props.messages.map((m) => `${m.role}|${m.content?.length || 0}|${m.status || ''}`).join(';'),
  () => {
    scrollToBottom();
  }
);
</script>

<style scoped>
.message-list {
  min-height: 480px;
  max-height: 68vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.empty {
  color: var(--color-muted);
}

.msg {
  padding: 12px;
  border-radius: 10px;
  border: 1px solid var(--color-border);
}

.msg.user {
  background: #eef4ff;
}

.role {
  font-size: 12px;
  color: var(--color-muted);
  margin-bottom: 4px;
}

.content {
  white-space: pre-wrap;
  line-height: 1.6;
}

.stream-status {
  margin-top: 8px;
  font-size: 12px;
  color: #2563eb;
}

.steps {
  margin-top: 8px;
  font-size: 13px;
  color: #374151;
}

.ref-title {
  font-weight: 600;
  margin-bottom: 4px;
}

.trace {
  margin-top: 8px;
}

pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.5;
}
</style>
