import { defineStore } from 'pinia';
import { apiAdapter, streamChat } from '../api/adapters';

const toText = (value) => {
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
};

export const useChatStore = defineStore('chat', {
  state: () => ({
    messages: [],
    loading: false,
    sessions: [],
    activeSessionId: '',
    streamController: null,
    streamTick: 0
  }),
  actions: {
    async loadSessions() {
      const data = await apiAdapter.listSessions();
      this.sessions = data?.sessions || data?.items || data?.data || [];
      if (!this.activeSessionId && this.sessions.length > 0) {
        this.activeSessionId = this.sessions[0].session_id || this.sessions[0].id || '';
      }
    },
    async loadSessionMessages(sessionId) {
      if (!sessionId) return;
      const data = await apiAdapter.getSessionMessages(sessionId);
      this.activeSessionId = sessionId;
      const rawMessages = data?.messages || data?.items || data?.data || [];
      this.messages = rawMessages.map((item) => ({
        role: item?.type === 'user' ? 'user' : 'assistant',
        content: item?.content || '',
        timestamp: item?.timestamp,
        rag_trace: item?.rag_trace || null,
        rag_steps: [],
        streaming: false,
        isThinking: false,
        status: ''
      }));
    },
    async deleteSession(sessionId) {
      await apiAdapter.deleteSession(sessionId);
      if (this.activeSessionId === sessionId) {
        this.activeSessionId = '';
        this.messages = [];
      }
      await this.loadSessions();
    },
    stopStreaming() {
      if (this.streamController) {
        this.streamController.abort();
      }
    },
    async sendMessage(question) {
      if (!question?.trim() || this.loading) return;

      this.messages.push({ role: 'user', content: question });
      const assistantMsg = {
        role: 'assistant',
        content: '',
        rag_trace: null,
        rag_steps: [],
        streaming: true,
        isThinking: true,
        status: '思考中...'
      };
      this.messages.push(assistantMsg);

      this.loading = true;
      this.streamController = new AbortController();

      try {
        await streamChat(
          {
            message: question,
            session_id: this.activeSessionId || undefined,
            signal: this.streamController.signal
          },
          {
            onContent: (chunk) => {
              assistantMsg.isThinking = false;
              assistantMsg.streaming = true;
              assistantMsg.status = '生成中...';
              assistantMsg.content += chunk || '';
              this.streamTick += 1;
            },
            onRagStep: (step) => {
              assistantMsg.rag_steps.push(toText(step));
              this.streamTick += 1;
            },
            onTrace: (trace) => {
              assistantMsg.rag_trace = trace;
            },
            onError: (err) => {
              assistantMsg.streaming = false;
              assistantMsg.isThinking = false;
              assistantMsg.status = '生成失败';
              if (!assistantMsg.content) {
                assistantMsg.content = `请求失败：${toText(err)}`;
              }
              this.streamTick += 1;
            },
            onDone: () => {
              assistantMsg.streaming = false;
              assistantMsg.isThinking = false;
              assistantMsg.status = '';
              this.streamTick += 1;
            }
          }
        );
      } catch (error) {
        assistantMsg.streaming = false;
        assistantMsg.isThinking = false;
        if (error?.name === 'AbortError') {
          assistantMsg.status = '已停止';
          assistantMsg.content = assistantMsg.content
            ? `${assistantMsg.content}(回答已被终止)`
            : '(已终止回答)';
        } else {
          assistantMsg.status = '生成失败';
          if (!assistantMsg.content) {
            assistantMsg.content = `请求失败：${error.message}`;
          }
        }
        this.streamTick += 1;
      } finally {
        this.streamController = null;
        this.loading = false;

        // 保持轻量同步：只刷新会话列表，不覆盖当前正在展示的流式文本
        await this.loadSessions();
      }
    }
  }
});
