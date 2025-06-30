"""认证中间件模块"""

from fastapi import Request, status
from fastapi.responses import JSONResponse

from copilot.service.user_service import UserService
from copilot.utils.logger import logger


class AuthenticationMiddleware:
    """认证中间件类"""

    def __init__(self):
        self.user_service = UserService()

        # 定义需要认证的路径前缀
        self.protected_paths = [
            "/agent_backend/chat",  # 聊天相关接口需要认证
            "/agent_backend/user/profile",  # 用户信息管理需要认证
            "/agent_backend/user/update",  # 用户信息更新需要认证
            "/agent_backend/user/me",  # 获取当前用户信息需要认证
            "/agent_backend/mcp",  # 用户登出需要认证
        ]

        # 定义公开路径（不需要认证）
        self.public_paths = [
            "/agent_backend/user/register",  # 用户注册
            "/agent_backend/user/login",  # 用户登录
            "/agent_backend/chat/health",  # 健康检查（如果存在）
            "/docs",  # API文档
            "/openapi.json",  # OpenAPI规范
            "/redoc",  # ReDoc文档
        ]

    async def authenticate_request(self, request: Request, call_next):
        """用户认证中间件"""
        path = request.url.path
        logger.debug(f"Processing request path: {path}")

        # 检查是否为公开路径
        if any(path.startswith(public_path) for public_path in self.public_paths):
            logger.debug(f"Path {path} is public, skipping authentication")
            return await call_next(request)

        # 检查是否为需要保护的路径
        if any(path.startswith(protected_path) for protected_path in self.protected_paths):
            logger.debug(f"Path {path} requires authentication")
            # 获取Authorization header
            authorization = request.headers.get("Authorization")
            logger.debug(f"Authorization header: {authorization[:50] if authorization else 'None'}...")

            if not authorization:
                logger.warning(f"Missing authorization header for path: {path}")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"code": 401, "message": "缺少认证信息", "detail": "请提供有效的Authorization header"},
                )

            # 验证Bearer token格式
            if not authorization.startswith("Bearer "):
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"code": 401, "message": "无效的认证格式", "detail": "Authorization header必须使用Bearer格式"},
                )

            # 提取token
            token = authorization.split(" ")[1] if len(authorization.split(" ")) == 2 else None

            if not token:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED, content={"code": 401, "message": "无效的认证信息", "detail": "无法获取有效的token"}
                )

            try:
                logger.debug(f"Verifying token: {token[:6]}...{token[-6:]}")
                # 验证token
                session_data = await self.user_service.verify_token(token)
                logger.debug(f"Token verification result for {token[:6]}...{token[-6:]}: session_data={session_data}")

                if session_data is None:
                    logger.warning(f"Token verification failed for {token[:6]}...{token[-6:]}")
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED, content={"code": 401, "message": "认证失败", "detail": "无效或过期的token"}
                    )

                # 从会话数据中获取用户名
                username = session_data.get("username")
                if not username:
                    logger.warning(f"No username found in session data: {session_data}")
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED, content={"code": 401, "message": "会话数据无效", "detail": "无法获取用户名信息"}
                    )

                # 获取用户信息
                logger.debug(f"Fetching user info for username: {username}")
                user = await self.user_service.get_user_by_username(username)
                if user is None:
                    logger.warning(f"User not found for username: {username}")
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED, content={"code": 401, "message": "用户不存在", "detail": "无法找到对应的用户信息"}
                    )

                # 检查用户是否被禁用
                if not user.get("is_active", True):
                    logger.warning(f"User account disabled: {username}")
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN, content={"code": 403, "message": "用户账户已被禁用", "detail": "请联系管理员激活账户"}
                    )

                # 将用户信息和会话信息添加到请求状态中，供后续处理使用
                request.state.current_user = user
                request.state.session_data = session_data
                logger.debug(f"Authentication successful for user: {username}")

            except Exception as e:
                logger.error(f"Authentication error for token {token[:6]}...{token[-6:]}: {str(e)}", exc_info=True)
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED, content={"code": 401, "message": "认证验证失败", "detail": "无法验证用户身份"}
                )

        return await call_next(request)


# 创建全局实例
auth_middleware = AuthenticationMiddleware()


async def authentication_middleware(request: Request, call_next):
    """认证中间件函数（兼容原有的装饰器方式）"""
    return await auth_middleware.authenticate_request(request, call_next)
