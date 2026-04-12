import http from './http';

export const apiAdapter = {
  // Auth
  async register(payload) {
    const { data } = await http.post('/auth/register', payload);
    return data;
  },
  async login(payload) {
    const { data } = await http.post('/auth/login', payload);
    return data;
  },
  async getCurrentUser() {
    const { data } = await http.get('/auth/me');
    return data;
  },

  // Chat & sessions
  async chat(payload) {
    const { data } = await http.post('/chat', payload);
    return data;
  },
  async listSessions() {
    const { data } = await http.get('/sessions');
    return data;
  },
  async getSessionMessages(sessionId) {
    const { data } = await http.get(`/sessions/${encodeURIComponent(sessionId)}`);
    return data;
  },
  async deleteSession(sessionId) {
    const { data } = await http.delete(`/sessions/${encodeURIComponent(sessionId)}`);
    return data;
  },

  // Documents (admin)
  async listDocuments() {
    const { data } = await http.get('/documents');
    return data;
  },
  async uploadDocument(formData) {
    const { data } = await http.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return data;
  },
  async deleteDocument(filename) {
    const { data } = await http.delete(`/documents/${encodeURIComponent(filename)}`);
    return data;
  }
};

const parseSSEPayload = (raw) => {
  if (!raw) return null;
  if (raw === '[DONE]') return { type: 'done' };

  try {
    return JSON.parse(raw);
  } catch {
    // 兼容后端仅返回文本的情况
    return { type: 'content', content: raw };
  }
};

export const streamChat = async ({ message, session_id, signal }, handlers = {}) => {
  const token = localStorage.getItem('access_token');
  const fallbackBaseURL = `${window.location.protocol}//${window.location.hostname}:8000`;
  const base = import.meta.env.VITE_API_BASE_URL || fallbackBaseURL;
  const response = await fetch(`${base}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify({ message, session_id }),
    signal
  });

  if (!response.ok || !response.body) {
    throw new Error(`流式请求失败: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  const dispatch = (event) => {
    if (!event) return;

    if (event.type === 'done') {
      handlers.onDone?.();
      return;
    }

    if (event.type === 'content') {
      handlers.onContent?.(event.content || event.delta || '');
      return;
    }

    if (event.type === 'rag_step') {
      handlers.onRagStep?.(event.step ?? event.data ?? event);
      return;
    }

    if (event.type === 'trace') {
      handlers.onTrace?.(event.trace ?? event.data ?? event);
      return;
    }

    if (event.type === 'error') {
      handlers.onError?.(event.error || event.detail || '流式响应错误');
      return;
    }

    handlers.onUnknown?.(event);
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const normalized = buffer.replace(/\r\n/g, '\n');
    const chunks = normalized.split('\n\n');

    if (!normalized.endsWith('\n\n')) {
      buffer = chunks.pop() || '';
    } else {
      buffer = '';
    }

    for (const chunk of chunks) {
      const lines = chunk.split('\n');
      const dataLines = [];

      for (const line of lines) {
        if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).trim());
        }
      }

      const payload = dataLines.join('\n');
      const event = parseSSEPayload(payload);
      dispatch(event);
      if (event?.type === 'done') return;
    }
  }

  handlers.onDone?.();
};
