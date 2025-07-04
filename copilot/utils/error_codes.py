"""
错误编码管理类
提供统一的错误编码和错误信息管理
"""

from typing import Dict, Any
from enum import Enum
from fastapi import HTTPException


class ErrorCategory(Enum):
    """错误类别枚举"""
    AUTHENTICATION = "AUTH"      # 认证相关错误
    AUTHORIZATION = "AUTHZ"      # 授权相关错误
    USER = "USER"               # 用户相关错误
    CHAT = "CHAT"               # 聊天相关错误
    SESSION = "SESSION"         # 会话相关错误
    DATABASE = "DB"             # 数据库相关错误
    REDIS = "REDIS"             # Redis相关错误
    VALIDATION = "VALID"        # 数据验证错误
    SYSTEM = "SYS"              # 系统错误
    NETWORK = "NET"             # 网络相关错误


class ErrorCode:
    """错误编码类"""
    
    def __init__(self, category: ErrorCategory, code: str, message: str, 
                 http_status: int, detail: str = None):
        self.category = category
        self.code = code
        self.message = message
        self.http_status = http_status
        self.detail = detail or message
        
    @property
    def full_code(self) -> str:
        """获取完整的错误编码"""
        return f"{self.category.value}{self.code}"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error_code": self.full_code,
            "message": self.message,
            "detail": self.detail,
            "category": self.category.value
        }
    
    def to_http_exception(self, detail: str = None) -> HTTPException:
        """转换为HTTPException"""
        error_detail = detail or self.detail
        return HTTPException(
            status_code=self.http_status,
            detail={
                "error_code": self.full_code,
                "message": self.message,
                "detail": error_detail,
                "category": self.category.value
            }
        )


class ErrorCodes:
    """错误编码常量类"""
    
    # ========== 认证相关错误 (AUTH) ==========
    # 缺少认证信息
    MISSING_AUTHENTICATION = ErrorCode(
        category=ErrorCategory.AUTHENTICATION,
        code="001",
        message="缺少认证信息",
        http_status=401,
        detail="请提供有效的认证信息"
    )
    
    # 认证格式错误
    INVALID_AUTH_FORMAT = ErrorCode(
        category=ErrorCategory.AUTHENTICATION,
        code="002", 
        message="无效的认证格式",
        http_status=401,
        detail="认证信息格式不正确"
    )
    
    # 认证失败
    AUTHENTICATION_FAILED = ErrorCode(
        category=ErrorCategory.AUTHENTICATION,
        code="003",
        message="认证失败",
        http_status=401,
        detail="用户名或密码错误"
    )
    
    # Token无效
    INVALID_TOKEN = ErrorCode(
        category=ErrorCategory.AUTHENTICATION,
        code="004",
        message="无效的访问令牌",
        http_status=401,
        detail="访问令牌无效或已过期"
    )
    
    # Token过期
    TOKEN_EXPIRED = ErrorCode(
        category=ErrorCategory.AUTHENTICATION,
        code="005",
        message="访问令牌已过期",
        http_status=401,
        detail="访问令牌已过期，请重新登录"
    )
    
    # 会话无效
    INVALID_SESSION = ErrorCode(
        category=ErrorCategory.AUTHENTICATION,
        code="006",
        message="会话无效",
        http_status=401,
        detail="用户会话无效或已过期"
    )
    
    # ========== 授权相关错误 (AUTHZ) ==========
    # 权限不足
    INSUFFICIENT_PERMISSIONS = ErrorCode(
        category=ErrorCategory.AUTHORIZATION,
        code="001",
        message="权限不足",
        http_status=403,
        detail="您没有执行此操作的权限"
    )
    
    # 账户被禁用
    ACCOUNT_DISABLED = ErrorCode(
        category=ErrorCategory.AUTHORIZATION,
        code="002",
        message="账户已被禁用",
        http_status=403,
        detail="用户账户已被禁用，请联系管理员"
    )
    
    # 访问被拒绝
    ACCESS_DENIED = ErrorCode(
        category=ErrorCategory.AUTHORIZATION,
        code="003",
        message="访问被拒绝",
        http_status=403,
        detail="您无权访问此资源"
    )
    
    # ========== 用户相关错误 (USER) ==========
    # 用户不存在
    USER_NOT_FOUND = ErrorCode(
        category=ErrorCategory.USER,
        code="001",
        message="用户不存在",
        http_status=404,
        detail="指定的用户不存在"
    )
    
    # 用户名已存在
    USERNAME_EXISTS = ErrorCode(
        category=ErrorCategory.USER,
        code="002",
        message="用户名已存在",
        http_status=400,
        detail="该用户名已被注册，请选择其他用户名"
    )
    
    # 邮箱已被注册
    EMAIL_EXISTS = ErrorCode(
        category=ErrorCategory.USER,
        code="003",
        message="邮箱已被注册",
        http_status=400,
        detail="该邮箱已被其他用户注册"
    )
    
    # 用户创建失败
    USER_CREATION_FAILED = ErrorCode(
        category=ErrorCategory.USER,
        code="004",
        message="用户创建失败",
        http_status=500,
        detail="创建用户时发生错误"
    )
    
    # 用户信息获取失败
    USER_INFO_FETCH_FAILED = ErrorCode(
        category=ErrorCategory.USER,
        code="005",
        message="用户信息获取失败",
        http_status=500,
        detail="获取用户信息时发生错误"
    )
    
    # 用户信息更新失败
    USER_UPDATE_FAILED = ErrorCode(
        category=ErrorCategory.USER,
        code="006",
        message="用户信息更新失败",
        http_status=500,
        detail="更新用户信息时发生错误"
    )
    
    # 密码错误
    INVALID_PASSWORD = ErrorCode(
        category=ErrorCategory.USER,
        code="007",
        message="密码错误",
        http_status=400,
        detail="提供的密码不正确"
    )
    
    # ========== 聊天相关错误 (CHAT) ==========
    # 会话创建失败
    CHAT_SESSION_CREATION_FAILED = ErrorCode(
        category=ErrorCategory.CHAT,
        code="001",
        message="聊天会话创建失败",
        http_status=500,
        detail="创建聊天会话时发生错误"
    )
    
    # 会话不存在
    CHAT_SESSION_NOT_FOUND = ErrorCode(
        category=ErrorCategory.CHAT,
        code="002",
        message="聊天会话不存在",
        http_status=404,
        detail="指定的聊天会话不存在"
    )
    
    # 消息发送失败
    MESSAGE_SEND_FAILED = ErrorCode(
        category=ErrorCategory.CHAT,
        code="003",
        message="消息发送失败",
        http_status=500,
        detail="发送消息时发生错误"
    )
    
    # 历史记录获取失败
    CHAT_HISTORY_FETCH_FAILED = ErrorCode(
        category=ErrorCategory.CHAT,
        code="004",
        message="聊天历史获取失败",
        http_status=500,
        detail="获取聊天历史时发生错误"
    )
    
    # 会话列表获取失败
    CHAT_SESSIONS_FETCH_FAILED = ErrorCode(
        category=ErrorCategory.CHAT,
        code="005",
        message="会话列表获取失败",
        http_status=500,
        detail="获取会话列表时发生错误"
    )
    
    # 聊天权限被拒绝
    CHAT_PERMISSION_DENIED = ErrorCode(
        category=ErrorCategory.CHAT,
        code="006",
        message="聊天权限被拒绝",
        http_status=403,
        detail="您没有权限执行此聊天操作"
    )
    
    # 工具权限响应处理失败
    CHAT_PERMISSION_RESPONSE_FAILED = ErrorCode(
        category=ErrorCategory.CHAT,
        code="007",
        message="工具权限响应处理失败",
        http_status=500,
        detail="处理工具权限响应时发生错误"
    )
    
    # 权限请求已超时
    CHAT_PERMISSION_TIMEOUT = ErrorCode(
        category=ErrorCategory.CHAT,
        code="008",
        message="权限请求已超时",
        http_status=410,  # Gone - 资源已不存在
        detail="权限请求已超时，无法再进行响应"
    )
    
    # ========== 会话管理相关错误 (SESSION) ==========
    # 会话创建失败
    SESSION_CREATION_FAILED = ErrorCode(
        category=ErrorCategory.SESSION,
        code="001",
        message="会话创建失败",
        http_status=500,
        detail="创建用户会话时发生错误"
    )
    
    # 会话不存在
    SESSION_NOT_FOUND = ErrorCode(
        category=ErrorCategory.SESSION,
        code="002",
        message="会话不存在",
        http_status=404,
        detail="指定的会话不存在"
    )
    
    # 会话撤销失败
    SESSION_REVOKE_FAILED = ErrorCode(
        category=ErrorCategory.SESSION,
        code="003",
        message="会话撤销失败",
        http_status=500,
        detail="撤销会话时发生错误"
    )
    
    # 会话获取失败
    SESSION_FETCH_FAILED = ErrorCode(
        category=ErrorCategory.SESSION,
        code="004",
        message="会话获取失败",
        http_status=500,
        detail="获取会话信息时发生错误"
    )
    
    # 登录失败
    LOGIN_FAILED = ErrorCode(
        category=ErrorCategory.SESSION,
        code="005",
        message="登录失败",
        http_status=500,
        detail="登录过程中发生错误"
    )
    
    # 退出失败
    LOGOUT_FAILED = ErrorCode(
        category=ErrorCategory.SESSION,
        code="006",
        message="退出失败",
        http_status=500,
        detail="退出登录时发生错误"
    )
    
    # ========== 数据库相关错误 (DB) ==========
    # 数据库连接失败
    DATABASE_CONNECTION_FAILED = ErrorCode(
        category=ErrorCategory.DATABASE,
        code="001",
        message="数据库连接失败",
        http_status=500,
        detail="无法连接到数据库"
    )
    
    # 数据库操作失败
    DATABASE_OPERATION_FAILED = ErrorCode(
        category=ErrorCategory.DATABASE,
        code="002",
        message="数据库操作失败",
        http_status=500,
        detail="数据库操作时发生错误"
    )
    
    # 数据查询失败
    DATABASE_QUERY_FAILED = ErrorCode(
        category=ErrorCategory.DATABASE,
        code="003",
        message="数据查询失败",
        http_status=500,
        detail="查询数据时发生错误"
    )
    
    # 数据插入失败
    DATABASE_INSERT_FAILED = ErrorCode(
        category=ErrorCategory.DATABASE,
        code="004",
        message="数据插入失败",
        http_status=500,
        detail="插入数据时发生错误"
    )
    
    # 数据更新失败
    DATABASE_UPDATE_FAILED = ErrorCode(
        category=ErrorCategory.DATABASE,
        code="005",
        message="数据更新失败",
        http_status=500,
        detail="更新数据时发生错误"
    )
    
    # 数据删除失败
    DATABASE_DELETE_FAILED = ErrorCode(
        category=ErrorCategory.DATABASE,
        code="006",
        message="数据删除失败",
        http_status=500,
        detail="删除数据时发生错误"
    )
    
    # ========== Redis相关错误 (REDIS) ==========
    # Redis连接失败
    REDIS_CONNECTION_FAILED = ErrorCode(
        category=ErrorCategory.REDIS,
        code="001",
        message="Redis连接失败",
        http_status=500,
        detail="无法连接到Redis服务器"
    )
    
    # Redis操作失败
    REDIS_OPERATION_FAILED = ErrorCode(
        category=ErrorCategory.REDIS,
        code="002",
        message="Redis操作失败",
        http_status=500,
        detail="Redis操作时发生错误"
    )
    
    # ========== 数据验证错误 (VALID) ==========
    # 请求参数无效
    INVALID_REQUEST_PARAMS = ErrorCode(
        category=ErrorCategory.VALIDATION,
        code="001",
        message="请求参数无效",
        http_status=400,
        detail="请求参数格式不正确或缺少必要参数"
    )
    
    # 数据格式错误
    INVALID_DATA_FORMAT = ErrorCode(
        category=ErrorCategory.VALIDATION,
        code="002",
        message="数据格式错误",
        http_status=400,
        detail="提供的数据格式不符合要求"
    )
    
    # 必填字段缺失
    MISSING_REQUIRED_FIELD = ErrorCode(
        category=ErrorCategory.VALIDATION,
        code="003",
        message="缺少必填字段",
        http_status=400,
        detail="请提供所有必填字段"
    )
    
    # 字段值无效
    INVALID_FIELD_VALUE = ErrorCode(
        category=ErrorCategory.VALIDATION,
        code="004",
        message="字段值无效",
        http_status=400,
        detail="提供的字段值不符合要求"
    )
    
    # ========== 系统错误 (SYS) ==========
    # 内部服务器错误
    INTERNAL_SERVER_ERROR = ErrorCode(
        category=ErrorCategory.SYSTEM,
        code="001",
        message="内部服务器错误",
        http_status=500,
        detail="服务器内部发生错误，请稍后重试"
    )
    
    # 服务不可用
    SERVICE_UNAVAILABLE = ErrorCode(
        category=ErrorCategory.SYSTEM,
        code="002",
        message="服务不可用",
        http_status=503,
        detail="服务暂时不可用，请稍后重试"
    )
    
    # 请求超时
    REQUEST_TIMEOUT = ErrorCode(
        category=ErrorCategory.SYSTEM,
        code="003",
        message="请求超时",
        http_status=408,
        detail="请求处理超时，请稍后重试"
    )
    
    # 资源不足
    INSUFFICIENT_RESOURCES = ErrorCode(
        category=ErrorCategory.SYSTEM,
        code="004",
        message="系统资源不足",
        http_status=503,
        detail="系统资源不足，请稍后重试"
    )
    
    # ========== 网络相关错误 (NET) ==========
    # 网络连接失败
    NETWORK_CONNECTION_FAILED = ErrorCode(
        category=ErrorCategory.NETWORK,
        code="001",
        message="网络连接失败",
        http_status=502,
        detail="网络连接失败，请检查网络连接"
    )
    
    # 请求过于频繁
    TOO_MANY_REQUESTS = ErrorCode(
        category=ErrorCategory.NETWORK,
        code="002",
        message="请求过于频繁",
        http_status=429,
        detail="请求过于频繁，请稍后重试"
    )


class ErrorHandler:
    """错误处理器"""
    
    @staticmethod
    def raise_error(error_code: ErrorCode, detail: str = None):
        """抛出错误"""
        raise error_code.to_http_exception(detail)
    
    @staticmethod
    def handle_database_error(e: Exception, operation: str = "操作") -> HTTPException:
        """处理数据库错误"""
        error_msg = f"数据库{operation}失败: {str(e)}"
        return ErrorCodes.DATABASE_OPERATION_FAILED.to_http_exception(error_msg)
    
    @staticmethod
    def handle_redis_error(e: Exception, operation: str = "操作") -> HTTPException:
        """处理Redis错误"""
        error_msg = f"Redis{operation}失败: {str(e)}"
        return ErrorCodes.REDIS_OPERATION_FAILED.to_http_exception(error_msg)
    
    @staticmethod
    def handle_system_error(e: Exception, context: str = "系统操作") -> HTTPException:
        """处理系统错误"""
        error_msg = f"{context}失败: {str(e)}"
        return ErrorCodes.INTERNAL_SERVER_ERROR.to_http_exception(error_msg)


# 便捷函数
def raise_auth_error(error_code: ErrorCode = None, detail: str = None):
    """抛出认证错误"""
    error_code = error_code or ErrorCodes.AUTHENTICATION_FAILED
    ErrorHandler.raise_error(error_code, detail)


def raise_user_error(error_code: ErrorCode, detail: str = None):
    """抛出用户相关错误"""
    ErrorHandler.raise_error(error_code, detail)


def raise_chat_error(error_code: ErrorCode, detail: str = None):
    """抛出聊天相关错误"""
    ErrorHandler.raise_error(error_code, detail)


def raise_validation_error(detail: str = None):
    """抛出数据验证错误"""
    ErrorHandler.raise_error(ErrorCodes.INVALID_REQUEST_PARAMS, detail)


def raise_system_error(detail: str = None):
    """抛出系统错误"""
    ErrorHandler.raise_error(ErrorCodes.INTERNAL_SERVER_ERROR, detail)
