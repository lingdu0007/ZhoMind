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
  async listDocuments(params) {
    const { data } = await http.get('/documents', { params });
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
  },

  // Document async jobs (admin)
  async listDocumentJobs(params) {
    const { data } = await http.get('/documents/jobs', { params });
    return data;
  },
  async getDocumentJob(jobId) {
    const { data } = await http.get(`/documents/jobs/${encodeURIComponent(jobId)}`);
    return data;
  },
  async cancelDocumentJob(jobId) {
    const { data } = await http.post(`/documents/jobs/${encodeURIComponent(jobId)}/cancel`);
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
  let eventBuffer = [];

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

  const flushEventBuffer = () => {
    if (!eventBuffer.length) return;
    const payload = eventBuffer.join('\n');
    const event = parseSSEPayload(payload);
    dispatch(event);
    eventBuffer = [];
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      const trimmed = line.trim();

      if (!trimmed) {
        flushEventBuffer();
        continue;
      }

      if (trimmed.startsWith('data:')) {
        if (eventBuffer.length) {
          flushEventBuffer();
        }
        eventBuffer.push(trimmed.slice(5).trim());
        continue;
      }

      // 兼容后端直接推送纯 JSON/文本的情况
      const event = parseSSEPayload(trimmed);
      dispatch(event);
      if (event?.type === 'done') return;
    }
  }

  flushEventBuffer();
  handlers.onDone?.();
};
