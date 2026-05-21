const CodexClient = require('./codex-client');

async function main() {
  const client = new CodexClient();

  try {
    // 1. 建立连接
    await client.connect();

    // 2. 获取会话列表
    const sessions = await client.listSessions();
    console.log(`\n📂 共找到 ${sessions.length} 个会话：`);
    
    if (sessions.length > 0) {
      // 打印前 3 个会话
      sessions.slice(0, 3).forEach((s, index) => {
        console.log(`   ${index + 1}. ${s.title || 'Untitled'} (ID: ${s.id.substring(0, 8)}...)`);
      });

      // 3. 尝试获取第一个会话的详情
      const firstSessionId = sessions[0].id;
      console.log(`\n正在加载第一个会话的详情...`);
      const detail = await client.getSession(firstSessionId);
      console.log(`   - 包含消息数: ${detail.turns ? detail.turns.length : 0}`);

      // 4. 发送一条测试消息（可选，取消注释即可运行）
      // console.log(`\n正在发送测试消息...`);
      // const response = await client.sendMessage(firstSessionId, "你好，这是一个自动化测试消息");
      // console.log("   - 发送成功！");
    }

  } catch (err) {
    console.error('❌ 执行出错:', err.message);
  } finally {
    client.close();
  }
}

main();
