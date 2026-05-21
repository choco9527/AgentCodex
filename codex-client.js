const net = require('net');

class CodexClient {
  constructor(port = 3760) {
    this.port = port;
    this.client = null;
    this.requestId = 1;
    this.pendingRequests = new Map();
    this.buffer = '';
  }

  connect() {
    return new Promise((resolve, reject) => {
      if (this.client && !this.client.destroyed) {
        resolve();
        return;
      }

      console.log(`[CodexBridge] 正在连接本地 Codex app-server (tcp://127.0.0.1:${this.port})...`);
      
      this.client = net.createConnection(this.port, '127.0.0.1', () => {
        console.log('[CodexBridge] ✅ TCP 连接成功！');
        resolve();
      });

      this.client.on('data', (data) => {
        this.buffer += data.toString();
        this._processBuffer();
      });

      this.client.on('error', (err) => {
        console.error('[CodexBridge] ❌ 连接错误:', err.message);
        reject(err);
      });

      this.client.on('close', () => {
        console.log('[CodexBridge] 连接已关闭');
      });
    });
  }

  _processBuffer() {
    const lines = this.buffer.split('\n');
    this.buffer = lines.pop() || ''; // 保留最后一行（可能不完整）

    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const message = JSON.parse(line);
        this._handleMessage(message);
      } catch (e) {
        console.warn('[CodexBridge] 解析消息失败:', e.message, '内容:', line.substring(0, 50));
      }
    }
  }

  _handleMessage(message) {
    if (message.id && this.pendingRequests.has(message.id)) {
      const { resolve, reject, timeout } = this.pendingRequests.get(message.id);
      clearTimeout(timeout);
      this.pendingRequests.delete(message.id);
      if (message.error) {
        reject(new Error(message.error.message || JSON.stringify(message.error)));
      } else {
        resolve(message.result);
      }
    }
  }

  _sendRequest(method, params = {}) {
    return new Promise((resolve, reject) => {
      if (!this.client || this.client.destroyed) {
        reject(new Error('Codex app-server 未连接'));
        return;
      }

      const id = this.requestId++;
      const payload = JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n';
      
      const timeout = setTimeout(() => {
        if (this.pendingRequests.has(id)) {
          this.pendingRequests.delete(id);
          reject(new Error(`Request ${method} timed out`));
        }
      }, 10000);

      this.pendingRequests.set(id, { resolve, reject, timeout });
      this.client.write(payload);
    });
  }

  async listSessions() {
    return await this._sendRequest('thread/list', {});
  }

  async getSession(threadId) {
    return await this._sendRequest('thread/read', { thread_id: threadId, threadId });
  }

  async sendMessage(threadId, text) {
    return await this._sendRequest('turn:start', {
      thread_id: threadId,
      threadId,
      input: [{ role: 'user', content: [{ type: 'text', text }] }]
    });
  }

  close() {
    if (this.client) this.client.end();
  }
}

module.exports = CodexClient;
