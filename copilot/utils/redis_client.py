from typing import Any, Optional, Union

from redis.asyncio import ConnectionPool, Redis
from redis.exceptions import RedisError

from copilot.config.settings import conf
from copilot.utils.logger import logger


class RedisClientManager:
    """Redis客户端管理器 - 单例模式"""
    _instance: Optional["RedisClientManager"] = None
    _client: Optional[Redis] = None
    _pool: Optional[ConnectionPool] = None

    def __new__(cls) -> "RedisClientManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self) -> None:
        """初始化Redis连接池和客户端"""
        if self._client is not None:
            return
        
        # 从全局配置加载Redis配置
        redis_config = conf.get("redis", {})
        host = redis_config.get("host", "localhost")
        port = redis_config.get("port", 6379)
        db = redis_config.get("db", 0)
        password = redis_config.get("password")
        max_connections = redis_config.get("max_connections", 10)
        
        # 创建连接池
        self._pool = ConnectionPool.from_url(
            f"redis://{host}:{port}/{db}", 
            password=password, 
            max_connections=max_connections, 
            decode_responses=True
        )
        
        # 创建客户端
        self._client = Redis(connection_pool=self._pool)
        logger.info(f"Redis client initialized with {host}:{port}/{db}")

    async def close(self) -> None:
        """关闭Redis连接"""
        if self._client:
            await self._client.aclose()
            self._client = None
        if self._pool:
            await self._pool.aclose()
            self._pool = None
        logger.info("Redis client closed")

    @property
    def client(self) -> Redis:
        """获取Redis客户端实例"""
        if self._client is None:
            raise RuntimeError("Redis client not initialized. Call initialize() first.")
        return self._client

    async def ping(self) -> bool:
        """检查Redis连接状态"""
        try:
            return await self.client.ping()
        except RedisError as e:
            logger.error(f"Redis PING failed: {str(e)}")
            return False


# 全局Redis管理器实例
redis_manager = RedisClientManager()


class RedisClient:
    """异步Redis客户端封装类 - 使用单例管理器"""

    def __init__(self):
        pass

    async def __aenter__(self) -> "RedisClient":
        await redis_manager.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        # 不再关闭连接，让管理器管理连接生命周期
        pass

    async def get(self, key: str) -> Optional[str]:
        """获取键值"""
        try:
            return await redis_manager.client.get(key)
        except RedisError as e:
            logger.error(f"Redis GET {key} failed: {str(e)}")
            raise

    async def set(self, key: str, value: Union[str, bytes], ex: Optional[int] = None) -> bool:
        """设置键值"""
        try:
            return await redis_manager.client.set(key, value, ex=ex)
        except RedisError as e:
            logger.error(f"Redis SET {key} failed: {str(e)}")
            raise

    async def delete(self, *keys: str) -> int:
        """删除键"""
        try:
            return await redis_manager.client.delete(*keys)
        except RedisError as e:
            logger.error(f"Redis DELETE {keys} failed: {str(e)}")
            raise

    async def exists(self, *keys: str) -> int:
        """检查键是否存在"""
        try:
            return await redis_manager.client.exists(*keys)
        except RedisError as e:
            logger.error(f"Redis EXISTS {keys} failed: {str(e)}")
            raise

    async def expire(self, key: str, seconds: int) -> bool:
        """设置过期时间"""
        try:
            return await redis_manager.client.expire(key, seconds)
        except RedisError as e:
            logger.error(f"Redis EXPIRE {key} failed: {str(e)}")
            raise

    async def ping(self) -> bool:
        """检查连接"""
        return await redis_manager.ping()

    async def sadd(self, key: str, *values: str) -> int:
        """向集合添加元素"""
        try:
            return await redis_manager.client.sadd(key, *values)
        except RedisError as e:
            logger.error(f"Redis SADD {key} failed: {str(e)}")
            raise

    async def smembers(self, key: str) -> set:
        """获取集合所有元素"""
        try:
            return await redis_manager.client.smembers(key)
        except RedisError as e:
            logger.error(f"Redis SMEMBERS {key} failed: {str(e)}")
            raise

    async def srem(self, key: str, *values: str) -> int:
        """从集合删除元素"""
        try:
            return await redis_manager.client.srem(key, *values)
        except RedisError as e:
            logger.error(f"Redis SREM {key} failed: {str(e)}")
            raise

    async def keys(self, pattern: str) -> list:
        """获取匹配模式的键"""
        try:
            return await redis_manager.client.keys(pattern)
        except RedisError as e:
            logger.error(f"Redis KEYS {pattern} failed: {str(e)}")
            raise


# 便捷函数，用于获取Redis客户端管理器
def get_redis_manager() -> RedisClientManager:
    """获取Redis客户端管理器实例"""
    return redis_manager
