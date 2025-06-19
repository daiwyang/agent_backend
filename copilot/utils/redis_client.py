import asyncio
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, AsyncGenerator, Callable, Optional, Union

from redis.asyncio import ConnectionPool, Redis
from redis.exceptions import RedisError

from copilot.config.settings import conf
from copilot.utils.logger import logger


def redis_error_handler(func: Callable) -> Callable:
    """Redis操作异常处理装饰器"""

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except RedisError as e:
            operation = func.__name__.upper()
            key_info = args[0] if args else "unknown"
            logger.error(f"Redis {operation} {key_info} failed: {str(e)}")
            raise

    return wrapper


class RedisClient:
    """智能Redis客户端 - 单例模式，连接池管理，异常处理"""

    _instance: Optional["RedisClient"] = None
    _client: Optional[Redis] = None
    _pool: Optional[ConnectionPool] = None
    _initialized: bool = False
    _lock = asyncio.Lock()

    def __new__(cls) -> "RedisClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self) -> None:
        """线程安全的初始化Redis连接"""
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:  # 双重检查
                return

            redis_config = conf.get("redis", {})
            logger.debug(f"Redis config: {redis_config}")

            # 构建Redis URL
            host = redis_config.get("host", "localhost")
            port = redis_config.get("port", 6379)
            db = redis_config.get("db", 0)
            password = redis_config.get("password")
            max_connections = redis_config.get("max_connections", 20)

            url = f"redis://:{password}@{host}:{port}/{db}" if password else f"redis://{host}:{port}/{db}"
            logger.debug(f"Redis connection URL: {url.split('@')[0]}****@{url.split('@')[1] if '@' in url else url}")

            try:
                # 创建连接池
                self._pool = ConnectionPool.from_url(
                    url,
                    max_connections=max_connections,
                    retry_on_timeout=True,
                    socket_keepalive=True,
                    socket_keepalive_options={},
                    decode_responses=True,
                )

                # 创建客户端
                self._client = Redis(connection_pool=self._pool)

                # 测试连接
                await self._client.ping()
                self._initialized = True

                logger.info(f"Redis client initialized: {host}:{port}/{db} (pool size: {max_connections})")
            except Exception as e:
                logger.error(f"Redis connection failed: {str(e)}")
                raise

    async def close(self) -> None:
        """关闭Redis连接"""
        async with self._lock:
            if self._client:
                await self._client.aclose()
                self._client = None
            if self._pool:
                await self._pool.aclose()
                self._pool = None
            self._initialized = False
            logger.info("Redis client closed")

    def _ensure_initialized(self) -> Redis:
        """确保客户端已初始化"""
        if not self._initialized or self._client is None:
            raise RuntimeError("Redis client not initialized. Call initialize() first.")
        return self._client

    async def ping(self) -> bool:
        """健康检查"""
        try:
            client = self._ensure_initialized()
            return await client.ping()
        except Exception as e:
            logger.error(f"Redis health check failed: {str(e)}")
            return False

    # === 基础操作 ===
    @redis_error_handler
    async def get(self, key: str) -> Optional[str]:
        """获取键值"""
        client = self._ensure_initialized()
        return await client.get(key)

    @redis_error_handler
    async def set(self, key: str, value: Union[str, bytes], ex: Optional[int] = None, nx: bool = False) -> bool:
        """设置键值，支持过期时间和NX选项"""
        client = self._ensure_initialized()
        return await client.set(key, value, ex=ex, nx=nx)

    @redis_error_handler
    async def delete(self, *keys: str) -> int:
        """删除键"""
        client = self._ensure_initialized()
        return await client.delete(*keys)

    @redis_error_handler
    async def exists(self, *keys: str) -> int:
        """检查键是否存在"""
        client = self._ensure_initialized()
        return await client.exists(*keys)

    @redis_error_handler
    async def expire(self, key: str, seconds: int) -> bool:
        """设置过期时间"""
        client = self._ensure_initialized()
        return await client.expire(key, seconds)

    @redis_error_handler
    async def ttl(self, key: str) -> int:
        """获取键的过期时间"""
        client = self._ensure_initialized()
        return await client.ttl(key)

    # === 集合操作 ===
    @redis_error_handler
    async def sadd(self, key: str, *values: str) -> int:
        """向集合添加元素"""
        client = self._ensure_initialized()
        return await client.sadd(key, *values)

    @redis_error_handler
    async def smembers(self, key: str) -> set:
        """获取集合所有元素"""
        client = self._ensure_initialized()
        return await client.smembers(key)

    @redis_error_handler
    async def srem(self, key: str, *values: str) -> int:
        """从集合删除元素"""
        client = self._ensure_initialized()
        return await client.srem(key, *values)

    @redis_error_handler
    async def sismember(self, key: str, value: str) -> bool:
        """检查元素是否在集合中"""
        client = self._ensure_initialized()
        return await client.sismember(key, value)

    # === 高级操作 ===
    @redis_error_handler
    async def keys(self, pattern: str = "*") -> list:
        """获取匹配模式的键（生产环境慎用）"""
        client = self._ensure_initialized()
        return await client.keys(pattern)

    @redis_error_handler
    async def scan(self, cursor: int = 0, match: Optional[str] = None, count: int = 100):
        """安全的键扫描方法"""
        client = self._ensure_initialized()
        return await client.scan(cursor, match=match, count=count)

    async def scan_iter(self, match: Optional[str] = None, count: int = 100) -> AsyncGenerator[str, None]:
        """异步迭代扫描键"""
        client = self._ensure_initialized()
        async for key in client.scan_iter(match=match, count=count):
            yield key

    # === 上下文管理器 ===
    async def __aenter__(self) -> "RedisClient":
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        # 不关闭连接，由应用程序生命周期管理
        pass

    # === 列表操作 ===
    @redis_error_handler
    async def lrange(self, key: str, start: int, end: int) -> list:
        """获取列表指定范围内的元素"""
        client = self._ensure_initialized()
        return await client.lrange(key, start, end)

    @redis_error_handler
    async def lpush(self, key: str, *values: Union[str, bytes, int, float]) -> int:
        """向列表头部添加元素"""
        client = self._ensure_initialized()
        processed_values = [str(v) if not isinstance(v, (str, bytes)) else v for v in values]
        return await client.lpush(key, *processed_values)

    @redis_error_handler
    async def rpush(self, key: str, *values: Union[str, bytes, int, float]) -> int:
        """向列表尾部添加元素，支持多种数据类型"""
        client = self._ensure_initialized()
        processed_values = [str(v) if not isinstance(v, (str, bytes)) else v for v in values]
        return await client.rpush(key, *processed_values)

    @redis_error_handler
    async def ltrim(self, key: str, start: int, end: int) -> bool:
        """修剪列表，只保留指定范围内的元素"""
        client = self._ensure_initialized()
        return await client.ltrim(key, start, end)

    @redis_error_handler
    async def llen(self, key: str) -> int:
        """获取列表长度"""
        client = self._ensure_initialized()
        return await client.llen(key)

    # === 便捷方法 ===
    async def get_or_set(self, key: str, value_func: Callable, ex: Optional[int] = None) -> str:
        """获取键值，如果不存在则设置"""
        result = await self.get(key)
        if result is None:
            if asyncio.iscoroutinefunction(value_func):
                result = await value_func()
            else:
                result = value_func()
            await self.set(key, result, ex=ex)
        return result

    async def increment_with_expire(self, key: str, amount: int = 1, ex: int = 3600) -> int:
        """递增计数器并设置过期时间"""
        client = self._ensure_initialized()
        async with client.pipeline() as pipe:
            await pipe.incr(key, amount)
            await pipe.expire(key, ex)
            results = await pipe.execute()
            return results[0]


# 全局单例实例
redis_client = RedisClient()


# === 便捷函数 ===
@asynccontextmanager
async def get_redis() -> AsyncGenerator[RedisClient, None]:
    """异步上下文管理器，获取已初始化的Redis客户端"""
    async with redis_client as client:
        yield client


async def init_redis() -> None:
    """初始化Redis客户端"""
    await redis_client.initialize()


async def close_redis() -> None:
    """关闭Redis客户端"""
    await redis_client.close()
