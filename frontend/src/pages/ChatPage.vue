<template>
  <section ref="chatSectionRef">
    <div class="top-row">
      <h1 class="page-title">聊天</h1>
      <div class="auth-actions">
        <el-button v-if="!authStore.isLoggedIn" type="primary" @click="authDialogVisible = true">登录 / 注册</el-button>
        <template v-else>
          <span class="user-tag">{{ authStore.username }} ({{ authStore.role }})</span>
          <el-button @click="logout">退出</el-button>
        </template>
      </div>
    </div>

    <div class="chat-layout">
      <aside class="panel session-panel">
        <div class="session-header">
          <h3>会话</h3>
          <el-button size="small" @click="loadSessions">刷新</el-button>
        </div>
        <div class="session-list">
          <div
            v-for="item in chatStore.sessions"
            :key="item.session_id || item.id"
            class="session-item"
            :class="{ active: (item.session_id || item.id) === chatStore.activeSessionId }"
            @click="openSession(item.session_id || item.id)"
          >
            <div class="session-meta">
              <span class="session-title">{{ item.session_id || item.id }}</span>
              <span class="session-sub">{{ item.updated_at || '' }} · {{ item.message_count ?? 0 }}条</span>
            </div>
            <el-button link type="danger" @click.stop="removeSession(item.session_id || item.id)">删除</el-button>
          </div>
        </div>
      </aside>

      <div class="chat-main">
        <ChatMessageList :messages="chatStore.messages" />

        <div class="panel composer">
          <el-input
            v-model="input"
            type="textarea"
            :rows="3"
            placeholder="请输入问题，系统将走 Agentic RAG 检索与回答"
          />
          <div class="actions">
            <el-button
              v-if="chatStore.loading"
              type="danger"
              plain
              @click="chatStore.stopStreaming"
            >
              停止生成
            </el-button>
            <el-button type="primary" :loading="chatStore.loading" :disabled="!authStore.isLoggedIn || chatStore.loading" @click="onSend">
              发送
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <el-dialog v-model="authDialogVisible" title="登录 / 注册" width="480px">
      <el-form label-width="100px">
        <el-form-item label="模式">
          <el-radio-group v-model="authMode">
            <el-radio-button label="login">登录</el-radio-button>
            <el-radio-button label="register">注册</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="authForm.username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="authForm.password" type="password" show-password />
        </el-form-item>
        <el-form-item v-if="authMode === 'register'" label="角色">
          <el-select v-model="authForm.role" placeholder="可选">
            <el-option label="user" value="user" />
            <el-option label="admin" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="authMode === 'register' && authForm.role === 'admin'" label="管理员码">
          <el-input v-model="authForm.admin_code" placeholder="仅注册管理员账号时需要" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="authDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="authStore.loading" @click="submitAuth">
          {{ authMode === 'login' ? '登录' : '注册' }}
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { nextTick, onMounted, reactive, ref, watch } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import ChatMessageList from '../components/ChatMessageList.vue';
import { useChatStore } from '../store/chat';
import { useAuthStore } from '../store/auth';

const chatStore = useChatStore();
const authStore = useAuthStore();
const input = ref('');
const chatSectionRef = ref(null);

const scrollToBottom = async () => {
  await nextTick();
  if (!chatSectionRef.value) return;
  chatSectionRef.value.scrollIntoView({ behavior: 'smooth', block: 'end' });
};

const authDialogVisible = ref(false);
const authMode = ref('login');
const authForm = reactive({
  username: '',
  password: '',
  role: 'user',
  admin_code: ''
});

const loadSessions = async () => {
  if (!authStore.isLoggedIn) return;
  try {
    await chatStore.loadSessions();
  } catch (error) {
    ElMessage.error(error.message || '加载会话失败');
  }
};

const openSession = async (sessionId) => {
  try {
    await chatStore.loadSessionMessages(sessionId);
  } catch (error) {
    ElMessage.error(error.message || '加载会话消息失败');
  }
};

const removeSession = async (sessionId) => {
  try {
    await ElMessageBox.confirm('确认删除该会话？', '提示', { type: 'warning' });
    await chatStore.deleteSession(sessionId);
    ElMessage.success('会话已删除');
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(error.message || '删除会话失败');
  }
};

const submitAuth = async () => {
  try {
    if (authMode.value === 'login') {
      await authStore.login({ username: authForm.username, password: authForm.password });
      ElMessage.success('登录成功');
    } else {
      const payload = {
        username: authForm.username,
        password: authForm.password,
        role: authForm.role
      };
      if (authForm.role === 'admin' && authForm.admin_code) {
        payload.admin_code = authForm.admin_code;
      }
      await authStore.register(payload);
      ElMessage.success('注册成功');
    }
    authDialogVisible.value = false;
    await loadSessions();
  } catch (error) {
    ElMessage.error(error.message || '认证失败');
  }
};

const logout = () => {
  authStore.clearAuth();
  chatStore.messages = [];
  chatStore.sessions = [];
  chatStore.activeSessionId = '';
};

const onSend = async () => {
  if (!authStore.isLoggedIn) {
    ElMessage.warning('请先登录');
    return;
  }
  const question = input.value;
  input.value = '';
  await chatStore.sendMessage(question);
};

watch(
  () => chatStore.streamTick,
  () => {
    scrollToBottom();
  }
);

onMounted(async () => {
  try {
    await authStore.refreshMe();
    await loadSessions();
  } catch {
    authStore.clearAuth();
  }
});
</script>

<style scoped>
.top-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.user-tag {
  margin-right: 8px;
  color: var(--color-muted);
}

.chat-layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 16px;
}

.session-panel {
  min-height: 620px;
}

.session-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.session-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.session-item {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
}

.session-item.active {
  border-color: var(--color-primary);
  background: #eef4ff;
}

.session-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.session-title {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 165px;
}

.session-sub {
  margin-top: 2px;
  font-size: 12px;
  color: var(--color-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 165px;
}

.composer {
  margin-top: 16px;
}

.actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
</style>
