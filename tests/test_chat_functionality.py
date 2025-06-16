"""
聊天功能测试
测试聊天接口、会话创建、消息搜索等功能
"""

import asyncio
import aiohttp
import json
from typing import Optional, List, Dict

from test_config import (
    TestConfig,
    create_auth_headers,
    create_json_headers,
    print_test_section,
    print_test_result,
    format_response_data
)


class ChatTester:
    """聊天功能测试类"""
    
    def __init__(self):
        self.config = TestConfig()
        self.session = None
        self.token = None
        self.chat_session_id = None
    
    async def setup(self):
        """设置测试环境"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.REQUEST_TIMEOUT)
        )
    
    async def teardown(self):
        """清理测试环境"""
        if self.session:
            await self.session.close()
    
    async def login_and_get_token(self) -> bool:
        """登录获取token"""
        login_data = {
            "username": self.config.TEST_USER["username"],
            "password": self.config.TEST_USER["password"]
        }
        
        async with self.session.post(
            f"{self.config.BASE_URL}{self.config.API_PATHS['user_login']}",
            headers={"Content-Type": "application/json"},
            data=json.dumps(login_data)
        ) as resp:
            if resp.status == 200:
                result = await resp.json()
                self.token = result.get("access_token")
                print(f"   登录成功，获取token")
                return True
            else:
                print(f"   登录失败: {resp.status}")
                return False
    
    async def test_create_chat_session(self):
        """测试创建聊天会话"""
        if not self.token:
            print("⚠️  跳过创建会话测试 - 无有效token")
            return
        
        print_test_section("测试创建聊天会话")
        
        create_session_data = {
            "window_id": f"test_window_{asyncio.get_event_loop().time()}"
        }
        
        headers = create_json_headers(self.token)
        async with self.session.post(
            f"{self.config.BASE_URL}{self.config.API_PATHS['chat_sessions']}",
            headers=headers,
            data=json.dumps(create_session_data)
        ) as resp:
            print_test_result("POST /agent_backend/chat/sessions", resp.status, 200)
            
            if resp.status == 200:
                result = await resp.json()
                self.chat_session_id = result.get('session_id')
                user_id = result.get('user_id')
                window_id = result.get('window_id')
                
                print(f"   创建成功:")
                print(f"   会话ID: {self.chat_session_id}")
                print(f"   用户ID: {user_id}")
                print(f"   窗口ID: {window_id}")
                return True
            else:
                try:
                    result = await resp.json()
                    print(f"   创建失败: {result.get('detail', 'Unknown error')}")
                except:
                    print(f"   创建失败: HTTP {resp.status}")
                return False
    
    async def test_get_chat_sessions(self):
        """测试获取聊天会话列表"""
        if not self.token:
            print("⚠️  跳过获取会话列表测试 - 无有效token")
            return
        
        print_test_section("测试获取聊天会话列表")
        
        headers = create_auth_headers(self.token)
        async with self.session.get(f"{self.config.BASE_URL}{self.config.API_PATHS['chat_sessions']}", headers=headers) as resp:
            print_test_result("GET /agent_backend/chat/sessions", resp.status, 200)
            
            if resp.status == 200:
                result = await resp.json()
                session_count = len(result) if isinstance(result, list) else 0
                print(f"   当前聊天会话数: {session_count}")
                
                if session_count > 0:
                    # 显示最新的会话信息
                    latest_session = result[0] if isinstance(result, list) else result
                    if isinstance(latest_session, dict):
                        session_id = latest_session.get('session_id', 'Unknown')[:8]
                        window_id = latest_session.get('window_id', 'Unknown')
                        print(f"   最新会话: {session_id}... (窗口: {window_id})")
    
    async def test_chat_message(self):
        """测试发送聊天消息"""
        if not self.token or not self.chat_session_id:
            print("⚠️  跳过聊天消息测试 - 无有效token或会话")
            return
        
        print_test_section("测试发送聊天消息")
        
        chat_data = {
            "session_id": self.chat_session_id,
            "message": "这是一条测试消息，用于验证聊天功能是否正常工作。"
        }
        
        headers = create_json_headers(self.token)
        
        # 注意：这里测试的是流式响应，我们只检查连接是否成功建立
        try:
            async with self.session.post(
                f"{self.config.BASE_URL}/agent_backend/chat/chat",
                headers=headers,
                data=json.dumps(chat_data)
            ) as resp:
                print_test_result("POST /agent_backend/chat/chat", resp.status)
                
                if resp.status == 200:
                    print("   聊天接口连接成功")
                    # 由于是流式响应，我们只读取一部分内容来验证
                    try:
                        content = await resp.content.read(1024)  # 读取前1KB
                        if content:
                            print("   收到流式响应数据")
                            # 尝试解析第一行JSON
                            lines = content.decode('utf-8').split('\n')
                            for line in lines:
                                if line.strip():
                                    try:
                                        data = json.loads(line)
                                        msg_type = data.get('type', 'unknown')
                                        print(f"   响应类型: {msg_type}")
                                        break
                                    except:
                                        continue
                        else:
                            print("   警告: 未收到响应数据")
                    except Exception as e:
                        print(f"   警告: 读取响应时出错 - {e}")
                else:
                    try:
                        result = await resp.json()
                        print(f"   聊天失败: {result.get('detail', 'Unknown error')}")
                    except:
                        print(f"   聊天失败: HTTP {resp.status}")
        except Exception as e:
            print(f"   聊天请求异常: {e}")
    
    async def test_chat_history(self):
        """测试获取聊天历史"""
        if not self.token:
            print("⚠️  跳过聊天历史测试 - 无有效token")
            return
        
        print_test_section("测试获取聊天历史")
        
        headers = create_auth_headers(self.token)
        async with self.session.get(f"{self.config.BASE_URL}{self.config.API_PATHS['chat_history']}", headers=headers) as resp:
            print_test_result("GET /agent_backend/chat/chat-history", resp.status, 200)
            
            if resp.status == 200:
                result = await resp.json()
                user_id = result.get('user_id', 'Unknown')
                sessions = result.get('sessions', [])
                print(f"   用户ID: {user_id}")
                print(f"   历史会话数: {len(sessions)}")
    
    async def test_chat_search(self):
        """测试聊天搜索"""
        if not self.token:
            print("⚠️  跳过聊天搜索测试 - 无有效token")
            return
        
        print_test_section("测试聊天搜索")
        
        search_data = {
            "query": "测试",
            "limit": 10
        }
        
        headers = create_json_headers(self.token)
        async with self.session.post(
            f"{self.config.BASE_URL}{self.config.API_PATHS['chat_search']}",
            headers=headers,
            data=json.dumps(search_data)
        ) as resp:
            print_test_result("POST /agent_backend/chat/search", resp.status, 200)
            
            if resp.status == 200:
                result = await resp.json()
                query = result.get('query', 'Unknown')
                total_count = result.get('total_count', 0)
                results = result.get('results', [])
                
                print(f"   搜索关键词: {query}")
                print(f"   结果数量: {total_count}")
                print(f"   返回结果: {len(results)}")
                
                if results:
                    # 显示第一个搜索结果
                    first_result = results[0]
                    content = first_result.get('content', '')[:50]
                    print(f"   示例结果: {content}...")
    
    async def test_chat_stats(self):
        """测试聊天统计"""
        if not self.token:
            print("⚠️  跳过聊天统计测试 - 无有效token")
            return
        
        print_test_section("测试聊天统计")
        
        headers = create_auth_headers(self.token)
        async with self.session.get(f"{self.config.BASE_URL}{self.config.API_PATHS['chat_stats']}", headers=headers) as resp:
            print_test_result("GET /agent_backend/chat/stats", resp.status, 200)
            
            if resp.status == 200:
                result = await resp.json()
                print(f"   统计数据: {format_response_data(result, 200)}")
    
    async def test_delete_chat_session(self):
        """测试删除聊天会话"""
        if not self.token or not self.chat_session_id:
            print("⚠️  跳过删除会话测试 - 无有效token或会话")
            return
        
        print_test_section("测试删除聊天会话")
        
        headers = create_auth_headers(self.token)
        async with self.session.delete(
            f"{self.config.BASE_URL}/agent_backend/chat/sessions/{self.chat_session_id}",
            headers=headers
        ) as resp:
            print_test_result(f"DELETE /chat/sessions/{self.chat_session_id[:8]}...", resp.status, 200)
            
            if resp.status == 200:
                result = await resp.json()
                print(f"   {result.get('message', 'Session deleted successfully')}")
    
    async def run_all_tests(self):
        """运行所有聊天功能测试"""
        print("💬 开始聊天功能测试...")
        print(f"📡 服务器地址: {self.config.BASE_URL}")
        print("=" * 60)
        
        try:
            await self.setup()
            
            # 确保用户存在并登录
            await self.ensure_user_exists()
            login_success = await self.login_and_get_token()
            
            if login_success:
                # 运行聊天测试套件
                await self.test_create_chat_session()
                await self.test_get_chat_sessions()
                await self.test_chat_message()
                await self.test_chat_history()
                await self.test_chat_search()
                await self.test_chat_stats()
                await self.test_delete_chat_session()
            else:
                print("❌ 登录失败，跳过聊天功能测试")
                
        except Exception as e:
            print(f"❌ 测试过程中出现错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.teardown()
        
        print("=" * 60)
        print("✅ 聊天功能测试完成")
    
    async def ensure_user_exists(self):
        """确保测试用户存在"""
        # 尝试注册用户
        async with self.session.post(
            f"{self.config.BASE_URL}{self.config.API_PATHS['user_register']}",
            headers={"Content-Type": "application/json"},
            data=json.dumps(self.config.TEST_USER)
        ) as resp:
            if resp.status in [200, 201]:
                print("   测试用户创建成功")
            elif resp.status == 400:
                print("   测试用户已存在")


async def main():
    """主函数"""
    tester = ChatTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
