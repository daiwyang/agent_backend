"""
错误编码系统测试
验证错误编码类的功能和使用方式
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from copilot.utils.error_codes import (
    ErrorCodes, ErrorHandler, ErrorCategory,
    raise_auth_error, raise_user_error, raise_system_error
)
from fastapi import HTTPException


def test_error_code_basic():
    """测试错误编码基本功能"""
    print("=== 测试错误编码基本功能 ===")
    
    # 测试错误编码属性
    error = ErrorCodes.USER_NOT_FOUND
    print(f"错误编码: {error.full_code}")
    print(f"错误消息: {error.message}")
    print(f"HTTP状态码: {error.http_status}")
    print(f"错误详情: {error.detail}")
    print(f"错误类别: {error.category.value}")
    
    # 测试转换为字典
    error_dict = error.to_dict()
    print(f"字典格式: {error_dict}")
    
    print()


def test_error_code_categories():
    """测试不同类别的错误编码"""
    print("=== 测试不同类别的错误编码 ===")
    
    test_errors = [
        ErrorCodes.MISSING_AUTHENTICATION,    # AUTH001
        ErrorCodes.ACCOUNT_DISABLED,          # AUTHZ002
        ErrorCodes.USERNAME_EXISTS,           # USER002
        ErrorCodes.CHAT_SESSION_NOT_FOUND,    # CHAT002
        ErrorCodes.SESSION_NOT_FOUND,         # SESSION002
        ErrorCodes.DATABASE_OPERATION_FAILED, # DB002
        ErrorCodes.REDIS_CONNECTION_FAILED,   # REDIS001
        ErrorCodes.INVALID_REQUEST_PARAMS,    # VALID001
        ErrorCodes.INTERNAL_SERVER_ERROR,     # SYS001
        ErrorCodes.TOO_MANY_REQUESTS,         # NET002
    ]
    
    for error in test_errors:
        print(f"{error.full_code}: {error.message}")
    
    print()


def test_http_exception_conversion():
    """测试转换为HTTPException"""
    print("=== 测试转换为HTTPException ===")
    
    # 测试基本转换
    error = ErrorCodes.USER_NOT_FOUND
    http_exception = error.to_http_exception()
    
    print(f"状态码: {http_exception.status_code}")
    print(f"详情: {http_exception.detail}")
    
    # 测试自定义详情
    custom_exception = error.to_http_exception("指定的用户ID不存在")
    print(f"自定义详情: {custom_exception.detail}")
    
    print()


def test_convenience_functions():
    """测试便捷函数"""
    print("=== 测试便捷函数 ===")
    
    try:
        # 测试认证错误
        raise_auth_error(ErrorCodes.INVALID_TOKEN)
    except HTTPException as e:
        print(f"认证错误: {e.status_code} - {e.detail}")
    
    try:
        # 测试用户错误
        raise_user_error(ErrorCodes.USERNAME_EXISTS, "用户名 'admin' 已存在")
    except HTTPException as e:
        print(f"用户错误: {e.status_code} - {e.detail}")
    
    try:
        # 测试系统错误
        raise_system_error("数据库连接失败")
    except HTTPException as e:
        print(f"系统错误: {e.status_code} - {e.detail}")
    
    print()


def test_error_handler():
    """测试错误处理器"""
    print("=== 测试错误处理器 ===")
    
    # 模拟数据库错误
    try:
        try:
            raise Exception("Connection timeout")
        except Exception as e:
            raise ErrorHandler.handle_database_error(e, "用户查询")
    except HTTPException as e:
        print(f"数据库错误: {e.status_code} - {e.detail}")
    
    # 模拟Redis错误
    try:
        try:
            raise Exception("Redis server not available")
        except Exception as e:
            raise ErrorHandler.handle_redis_error(e, "会话存储")
    except HTTPException as e:
        print(f"Redis错误: {e.status_code} - {e.detail}")
    
    # 模拟系统错误
    try:
        try:
            raise Exception("Unexpected error occurred")
        except Exception as e:
            raise ErrorHandler.handle_system_error(e, "业务处理")
    except HTTPException as e:
        print(f"系统错误: {e.status_code} - {e.detail}")
    
    print()


def test_error_response_format():
    """测试错误响应格式"""
    print("=== 测试错误响应格式 ===")
    
    # 模拟API错误响应
    def simulate_api_error():
        try:
            raise_user_error(
                ErrorCodes.USER_NOT_FOUND,
                "用户ID '12345' 不存在于系统中"
            )
        except HTTPException as e:
            return {
                "status_code": e.status_code,
                "response_body": e.detail
            }
    
    error_response = simulate_api_error()
    print(f"HTTP状态码: {error_response['status_code']}")
    print(f"响应体: {error_response['response_body']}")
    
    print()


def test_real_world_scenarios():
    """测试真实世界场景"""
    print("=== 测试真实世界场景 ===")
    
    # 场景1: 用户注册
    def simulate_user_registration(username: str, email: str):
        """模拟用户注册"""
        # 模拟用户名已存在
        if username == "admin":
            raise_user_error(ErrorCodes.USERNAME_EXISTS)
        
        # 模拟邮箱已被注册
        if email == "admin@example.com":
            raise_user_error(ErrorCodes.EMAIL_EXISTS)
        
        return {"status": "success", "message": "用户注册成功"}
    
    # 测试正常注册
    try:
        result = simulate_user_registration("newuser", "new@example.com")
        print(f"注册成功: {result}")
    except HTTPException as e:
        print(f"注册失败: {e.detail}")
    
    # 测试用户名冲突
    try:
        result = simulate_user_registration("admin", "new@example.com")
        print(f"注册成功: {result}")
    except HTTPException as e:
        print(f"注册失败: {e.detail}")
    
    # 场景2: 用户登录
    def simulate_user_login(username: str, password: str):
        """模拟用户登录"""
        # 模拟用户不存在
        if username == "nonexistent":
            raise_user_error(ErrorCodes.USER_NOT_FOUND)
        
        # 模拟密码错误
        if password == "wrongpassword":
            raise_auth_error(ErrorCodes.AUTHENTICATION_FAILED)
        
        # 模拟账户被禁用
        if username == "disabled":
            raise_auth_error(ErrorCodes.ACCOUNT_DISABLED)
        
        return {"status": "success", "token": "jwt_token_here"}
    
    # 测试正常登录
    try:
        result = simulate_user_login("user", "correctpassword")
        print(f"登录成功: {result}")
    except HTTPException as e:
        print(f"登录失败: {e.detail}")
    
    # 测试密码错误
    try:
        result = simulate_user_login("user", "wrongpassword")
        print(f"登录成功: {result}")
    except HTTPException as e:
        print(f"登录失败: {e.detail}")
    
    print()


def main():
    """主测试函数"""
    print("🧪 错误编码系统测试")
    print("=" * 50)
    
    test_error_code_basic()
    test_error_code_categories()
    test_http_exception_conversion()
    test_convenience_functions()
    test_error_handler()
    test_error_response_format()
    test_real_world_scenarios()
    
    print("✅ 所有测试完成")


if __name__ == "__main__":
    main()
