"""
认证系统测试
测试用户注册、登录、会话管理等功能
"""

import asyncio
import aiohttp
import json
from typing import Optional, Tuple

from test_config import (
    TestConfig, 
    create_auth_headers, 
    create_json_headers,
    print_test_section,
    print_test_result,
    format_response_data
)


class AuthenticationTester:
    """认证系统测试类"""
    
    def __init__(self):
        self.config = TestConfig()
        self.session = None
        self.current_token = None
        self.current_session_id = None
    
    async def setup(self):
        """设置测试环境"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.REQUEST_TIMEOUT)
        )
    
    async def teardown(self):
        """清理测试环境"""
        if self.session:
            await self.session.close()
    
    async def test_public_endpoints(self):
        """测试公开端点"""
        print_test_section("测试公开接口")
        
        # 测试文档接口
        async with self.session.get(f"{self.config.BASE_URL}{self.config.API_PATHS['docs']}") as resp:
            print_test_result("GET /docs", resp.status, 200)
        
        # 测试OpenAPI接口
        async with self.session.get(f"{self.config.BASE_URL}{self.config.API_PATHS['openapi']}") as resp:
            print_test_result("GET /openapi.json", resp.status, 200)
        
        # 测试健康检查
        async with self.session.get(f"{self.config.BASE_URL}{self.config.API_PATHS['health']}") as resp:
            print_test_result("GET /agent_backend/user/health", resp.status, 200)
    
    async def test_protected_endpoints_without_auth(self):
        """测试受保护端点（无认证）"""
        print_test_section("测试未认证的保护接口")
        
        protected_endpoints = [
            ("GET", self.config.API_PATHS['chat_sessions']),
            ("GET", self.config.API_PATHS['user_me']),
            ("GET", self.config.API_PATHS['user_sessions']),
            ("GET", self.config.API_PATHS['chat_history']),
        ]
        
        for method, path in protected_endpoints:
            async with self.session.request(method, f"{self.config.BASE_URL}{path}") as resp:
                print_test_result(f"{method} {path}", resp.status, 401)
                if resp.status == 401:
                    try:
                        result = await resp.json()
                        print(f"   响应: {result.get('message', 'Unknown error')}")
                    except:
                        pass
    
    async def test_user_registration(self) -> bool:
        """测试用户注册"""
        print_test_section("测试用户注册")
        
        async with self.session.post(
            f"{self.config.BASE_URL}{self.config.API_PATHS['user_register']}",
            headers={"Content-Type": "application/json"},
            data=json.dumps(self.config.TEST_USER)
        ) as resp:
            print_test_result("POST /agent_backend/user/register", resp.status)
            
            if resp.status in [200, 201]:
                result = await resp.json()
                print(f"   注册成功: {result.get('message', 'Success')}")
                return True
            elif resp.status == 400:
                result = await resp.json()
                if "已存在" in result.get('detail', ''):
                    print(f"   用户已存在: {result.get('detail')}")
                    return True  # 用户已存在也算成功
                else:
                    print(f"   注册失败: {result.get('detail')}")
                    return False
            else:
                try:
                    result = await resp.json()
                    print(f"   注册失败: {result.get('detail', 'Unknown error')}")
                except:
                    print(f"   注册失败: HTTP {resp.status}")
                return False
    
    async def test_user_login(self) -> Tuple[Optional[str], Optional[str]]:
        """测试用户登录"""
        print_test_section("测试用户登录（Redis会话管理）")
        
        login_data = {
            "username": self.config.TEST_USER["username"],
            "password": self.config.TEST_USER["password"]
        }
        
        async with self.session.post(
            f"{self.config.BASE_URL}{self.config.API_PATHS['user_login']}",
            headers={"Content-Type": "application/json"},
            data=json.dumps(login_data)
        ) as resp:
            print_test_result("POST /agent_backend/user/login", resp.status, 200)
            
            if resp.status == 200:
                result = await resp.json()
                token = result.get("access_token")
                session_id = result.get("session_id")
                
                print(f"   登录成功")
                print(f"   Token: {token[:20] if token else 'None'}...")
                print(f"   Session ID: {session_id}")
                
                self.current_token = token
                self.current_session_id = session_id
                return token, session_id
            else:
                try:
                    result = await resp.json()
                    print(f"   登录失败: {result.get('detail', 'Unknown error')}")
                except:
                    print(f"   登录失败: HTTP {resp.status}")
                return None, None
    
    async def test_authenticated_endpoints(self):
        """测试需要认证的端点"""
        if not self.current_token:
            print("⚠️  跳过认证端点测试 - 无有效token")
            return
        
        print_test_section("测试使用有效token访问保护接口")
        headers = create_auth_headers(self.current_token)
        
        # 测试获取当前用户信息
        async with self.session.get(f"{self.config.BASE_URL}{self.config.API_PATHS['user_me']}", headers=headers) as resp:
            print_test_result("GET /agent_backend/user/me", resp.status, 200)
            if resp.status == 200:
                result = await resp.json()
                print(f"   用户: {result.get('username', 'Unknown')}")
        
        # 测试获取聊天会话
        async with self.session.get(f"{self.config.BASE_URL}{self.config.API_PATHS['chat_sessions']}", headers=headers) as resp:
            print_test_result("GET /agent_backend/chat/sessions", resp.status, 200)
            if resp.status == 200:
                result = await resp.json()
                print(f"   会话数量: {len(result) if isinstance(result, list) else 'Unknown'}")
        
        # 测试创建聊天会话
        create_session_data = {"window_id": "test_window_001"}
        json_headers = create_json_headers(self.current_token)
        
        async with self.session.post(
            f"{self.config.BASE_URL}{self.config.API_PATHS['chat_sessions']}",
            headers=json_headers,
            data=json.dumps(create_session_data)
        ) as resp:
            print_test_result("POST /agent_backend/chat/sessions", resp.status, 200)
            if resp.status == 200:
                result = await resp.json()
                print(f"   新会话ID: {result.get('session_id', 'Unknown')}")
        
        # 测试搜索接口
        search_data = {"query": "测试搜索", "limit": 5}
        async with self.session.post(
            f"{self.config.BASE_URL}{self.config.API_PATHS['chat_search']}",
            headers=json_headers,
            data=json.dumps(search_data)
        ) as resp:
            print_test_result("POST /agent_backend/chat/search", resp.status, 200)
            if resp.status == 200:
                result = await resp.json()
                print(f"   搜索结果数: {result.get('total_count', 0)}")
        
        # 测试获取用户会话信息
        async with self.session.get(f"{self.config.BASE_URL}{self.config.API_PATHS['user_sessions']}", headers=headers) as resp:
            print_test_result("GET /agent_backend/user/sessions", resp.status, 200)
            if resp.status == 200:
                result = await resp.json()
                sessions = result.get('data', {}).get('sessions', [])
                print(f"   活跃会话数: {len(sessions)}")
    
    async def test_session_management(self):
        """测试会话管理功能"""
        if not self.current_token:
            print("⚠️  跳过会话管理测试 - 无有效token")
            return
        
        print_test_section("测试Redis会话管理功能")
        headers = create_auth_headers(self.current_token)
        
        # 测试退出登录（清理Redis会话）
        async with self.session.post(f"{self.config.BASE_URL}{self.config.API_PATHS['user_logout']}", headers=headers) as resp:
            print_test_result("POST /agent_backend/user/logout", resp.status, 200)
            if resp.status == 200:
                result = await resp.json()
                print(f"   {result.get('message', 'Logout successful')}")
        
        # 测试退出登录后的token是否失效
        async with self.session.get(f"{self.config.BASE_URL}{self.config.API_PATHS['user_me']}", headers=headers) as resp:
            print_test_result("GET /agent_backend/user/me (退出登录后)", resp.status, 401)
            if resp.status == 401:
                print("   ✅ 会话已失效（预期结果）")
            elif resp.status == 200:
                print("   ⚠️  警告：退出登录后token仍然有效")
    
    async def test_invalid_authentication(self):
        """测试无效认证"""
        print_test_section("测试无效认证")
        
        # 测试无效token
        invalid_headers = {"Authorization": "Bearer invalid_token_123"}
        async with self.session.get(f"{self.config.BASE_URL}{self.config.API_PATHS['chat_sessions']}", headers=invalid_headers) as resp:
            print_test_result("GET /chat/sessions (无效token)", resp.status, 401)
        
        # 测试错误的token格式
        wrong_format_headers = {"Authorization": "InvalidFormat token_123"}
        async with self.session.get(f"{self.config.BASE_URL}{self.config.API_PATHS['chat_sessions']}", headers=wrong_format_headers) as resp:
            print_test_result("GET /chat/sessions (错误格式)", resp.status, 401)
        
        # 测试缺少Authorization header
        async with self.session.get(f"{self.config.BASE_URL}{self.config.API_PATHS['chat_sessions']}") as resp:
            print_test_result("GET /chat/sessions (无header)", resp.status, 401)
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始认证系统测试...")
        print(f"📡 服务器地址: {self.config.BASE_URL}")
        print("=" * 60)
        
        try:
            await self.setup()
            
            # 运行测试套件
            await self.test_public_endpoints()
            await self.test_protected_endpoints_without_auth()
            
            # 用户注册和登录
            registration_success = await self.test_user_registration()
            if registration_success:
                await self.test_user_login()
            
            # 认证相关测试
            await self.test_authenticated_endpoints()
            await self.test_session_management()
            await self.test_invalid_authentication()
            
        except Exception as e:
            print(f"❌ 测试过程中出现错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.teardown()
        
        print("=" * 60)
        print("✅ 认证系统测试完成")


async def main():
    """主函数"""
    tester = AuthenticationTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
