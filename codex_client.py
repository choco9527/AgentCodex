# -*- coding: utf-8 -*-
import subprocess
import json
import threading
import time
import sys
import os

class CodexClient:
    def __init__(self):
        self.process = None
        self.request_id = 1
        self.pending_requests = {}
        self.buffer = ""
        self.lock = threading.Lock()

    def connect(self):
        print("[CodexBridge] 正在通过 Python subprocess 启动 Codex app-server...")
        self.process = subprocess.Popen(
            ["/Applications/Codex.app/Contents/Resources/codex", "app-server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0
        )
        
        # 启动日志线程
        threading.Thread(target=self._read_stderr, daemon=True).start()
        # 启动输出处理线程
        threading.Thread(target=self._read_stdout, daemon=True).start()
        
        # 等待初始化
        time.sleep(2)
        if self.process.poll() is not None:
            raise Exception("app-server 进程意外退出")
        
        # 发送初始化握手请求
        print("[CodexBridge] 正在发送初始化握手...")
        self._send_request('initialize', {
            "clientInfo": {
                "name": "codex-python-client",
                "title": "Python Client",
                "version": "0.0.1"
            },
            "capabilities": {
                "experimentalApi": True,
                "requestAttestation": False
            }
        })
        print("[CodexBridge] ✅ 连接成功！")

    def _read_stderr(self):
        for line in iter(self.process.stderr.readline, b''):
            print("[CodexServer Log]: {}".format(line.decode('utf-8').strip()))

    def _read_stdout(self):
        while True:
            char = self.process.stdout.read(1)
            if not char:
                break
            line = char + self.process.stdout.readline()
            try:
                message = json.loads(line.decode('utf-8'))
                self._handle_message(message)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

    def _handle_message(self, message):
        req_id = message.get('id')
        with self.lock:
            if req_id and req_id in self.pending_requests:
                entry = self.pending_requests.pop(req_id)
                if 'error' in message:
                    entry['error'] = message['error']
                else:
                    entry['result'] = message.get('result')
                entry['done'] = True

    def _send_request(self, method, params=None):
        req_id = self.request_id
        self.request_id += 1
        
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": req_id
        }
        
        entry = {'done': False, 'result': None, 'error': None}
        with self.lock:
            self.pending_requests[req_id] = entry
            
        json_str = json.dumps(request) + "\n"
        self.process.stdin.write(json_str.encode('utf-8'))
        self.process.stdin.flush()
        
        # 等待响应
        timeout = 10
        start_time = time.time()
        while time.time() - start_time < timeout:
            with self.lock:
                if entry['done']:
                    if entry['error']:
                        raise Exception(str(entry['error']))
                    return entry['result']
            time.sleep(0.1)
            
        raise Exception("Request {} timed out".format(method))

    def list_sessions(self):
        return self._send_request('thread/list')

    def get_session(self, thread_id):
        return self._send_request('thread/read', {'threadId': thread_id})

    def send_message(self, thread_id, text):
        return self._send_request('turn:start', {
            'thread_id': thread_id,
            'input': [{'role': 'user', 'content': [{'type': 'text', 'text': text}]}]
        })

    def close(self):
        if self.process:
            self.process.terminate()

if __name__ == "__main__":
    client = CodexClient()
    try:
        client.connect()
        
        # 1. 获取列表
        sessions = client.list_sessions()
        session_list = []
        if isinstance(sessions, dict):
            for key in ['threads', 'items', 'data', 'result']:
                if key in sessions and isinstance(sessions[key], list):
                    session_list = sessions[key]
                    break
        
        if not session_list:
            print("❌ 未找到任何会话")
        else:
            first_id = session_list[0].get('id')
            print(f"\n📂 正在读取第一个会话 (ID: {first_id})...")
            
            # 2. 读取详情
            detail = client.get_session(first_id)
            thread = detail.get('thread', {})
            
            print("\n--- 会话概览 ---")
            print("标题: {}".format(thread.get('name', 'Untitled')))
            print("分支: {}".format(thread.get('gitInfo', {}).get('branch', 'N/A')))
            print("预览: {}".format(thread.get('preview', '')[:100] + '...'))
            
            # 3. 尝试从磁盘文件读取最近的对话
            log_path = thread.get('path')
            if log_path and os.path.exists(log_path):
                print("\n--- 最近对话记录 ---")
                try:
                    with open(log_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        count = 0
                        for line in reversed(lines):
                            if count >= 5: break
                            try:
                                entry = json.loads(line)
                                payload = entry.get('payload', {})
                                
                                user_msg = payload.get('user_message')
                                agent_msg = payload.get('last_agent_message')
                                
                                if user_msg:
                                    print(f"User: {str(user_msg)[:120]}...")
                                    count += 1
                                elif agent_msg:
                                    preview = str(agent_msg).replace('\n', ' ')[:120] + "..."
                                    print(f"Codex: {preview}")
                                    count += 1
                            except:
                                continue
                except Exception as e:
                    print("读取日志文件失败: {}".format(e))
            else:
                print("\n(未找到本地日志文件)")
            
    except Exception as e:
        import traceback
        print(f"❌ 错误: {e}")
        traceback.print_exc()
    finally:
        client.close()
