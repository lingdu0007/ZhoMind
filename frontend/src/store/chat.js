import { defineStore } from 'pinia';
import { apiAdapter, streamChat } from '../api/adapters';
import { extractRejectReason, formatStreamError, getDoneStatus } from './chat-state';

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
      this.sessions = data?.items || [];
      if (!this.activeSessionId && this.sessions.length > 0) {
        this.activeSessionId = this.sessions[0]?.session_id || '';
      }
    },
    async loadSessionMessages(sessionId) {
      if (!sessionId) return;
      const data = await apiAdapter.getSessionMessages(sessionId);
      this.activeSessionId = sessionId;
      const rawMessages = data?.messages || [];
      this.messages = rawMessages.map((item) => ({
        role: item?.role || 'assistant',
        content: item?.content || '',
        timestamp: item?.timestamp,
        rag_trace: item?.rag_trace || null,
        rag_steps: [],
        streaming: false,
        isThinking: false,
        rejected: false,
        reject_reason: '',
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
    async sendMessageSync(question) {
      if (!question?.trim() || this.loading) return;

      this.messages.push({ role: 'user', content: question });
      this.loading = true;

      try {
        const data = await apiAdapter.chat({
          message: question,
          session_id: this.activeSessionId || undefined
        });

        this.activeSessionId = data?.session_id || this.activeSessionId;
        const message = data?.message || {};
        const rejected = message?.rag_trace?.metrics?.gate_passed === false;
        this.messages.push({
          role: message.role || 'assistant',
          content: message.content || '',
          timestamp: message.timestamp,
          rag_trace: message.rag_trace || null,
          rag_steps: [],
          streaming: false,
          isThinking: false,
          rejected,
          reject_reason: rejected ? message?.rag_trace?.metrics?.gate_reason || '' : '',
          status: rejected ? getDoneStatus({ rejected: true }) : ''
        });
      } catch (error) {
        this.messages.push({
          role: 'assistant',
          content: `请求失败：${formatStreamError(error)}`,
          timestamp: undefined,
          rag_trace: null,
          rag_steps: [],
          streaming: false,
          isThinking: false,
          rejected: false,
          reject_reason: '',
          status: '生成失败'
        });
      } finally {
        this.loading = false;
        await this.loadSessions();
      }
    },
    async sendMessage(question) {
      if (!question?.trim() || this.loading) return;

      const requestSessionId = this.activeSessionId || undefined;

      this.messages.push({ role: 'user', content: question });
      const assistantIndex = this.messages.length;
      this.messages.push({
        role: 'assistant',
        content: '',
        rag_trace: null,
        rag_steps: [],
        streaming: true,
        isThinking: true,
        rejected: false,
        reject_reason: '',
        status: '思考中...'
      });

      const getAssistantMsg = () => this.messages[assistantIndex];
      const finalizeAssistantStatus = (assistantMsg) => {
        const finalStatus = getDoneStatus(assistantMsg);
        if (finalStatus) {
          assistantMsg.status = finalStatus;
          return;
        }

        if (['思考中...', '生成中...', '证据不足，进入拒答'].includes(assistantMsg.status)) {
          assistantMsg.status = '';
        }
      };

      this.loading = true;
      this.streamController = new AbortController();

      try {
        await streamChat(
          {
            message: question,
            session_id: requestSessionId,
            signal: this.streamController.signal
          },
          {
            onMeta: (meta) => {
              const sessionId = meta?.session_id || meta?.data?.session_id || '';
              if (sessionId) {
                this.activeSessionId = sessionId;
              }
            },
            onContent: (chunk) => {
              const assistantMsg = getAssistantMsg();
              if (!assistantMsg) return;
              assistantMsg.isThinking = false;
              assistantMsg.streaming = true;
              assistantMsg.status = '生成中...';
              assistantMsg.content += chunk || '';
              this.streamTick += 1;
            },
            onRagStep: (step) => {
              const assistantMsg = getAssistantMsg();
              if (!assistantMsg) return;
              assistantMsg.rag_steps.push(toText(step));
              const rejectReason = extractRejectReason(step);
              if (rejectReason) {
                assistantMsg.rejected = true;
                assistantMsg.reject_reason = rejectReason;
                assistantMsg.status = '证据不足，进入拒答';
              }
              this.streamTick += 1;
            },
            onTrace: (trace) => {
              const assistantMsg = getAssistantMsg();
              if (!assistantMsg) return;
              assistantMsg.rag_trace = trace;
            },
            onError: (err) => {
              const assistantMsg = getAssistantMsg();
              if (!assistantMsg) return;
              assistantMsg.streaming = false;
              assistantMsg.isThinking = false;
              assistantMsg.status = '生成失败';
              if (!assistantMsg.content) {
                assistantMsg.content = `请求失败：${formatStreamError(err)}`;
              }
              this.streamTick += 1;
            },
            onDone: () => {
              const assistantMsg = getAssistantMsg();
              if (!assistantMsg) return;
              assistantMsg.streaming = false;
              assistantMsg.isThinking = false;
              if (assistantMsg.rejected && !assistantMsg.content) {
                assistantMsg.content = '未检索到足够相关的知识片段，请补充更具体的问题或关键词。';
              }
              finalizeAssistantStatus(assistantMsg);
              this.streamTick += 1;
            }
          }
        );
      } catch (error) {
        const assistantMsg = getAssistantMsg();
        if (!assistantMsg) return;
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
            assistantMsg.content = `请求失败：${formatStreamError(error)}`;
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
