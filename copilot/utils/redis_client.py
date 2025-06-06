from typing import Any, Optional, Union

from redis.asyncio import ConnectionPool, Redis
from redis.exceptions import RedisError

from copilot.utils.config import conf
from copilot.utils.logger import logger


class RedisClient:
    """异步Redis客户端封装类"""

    def __init__(self):
        # 从全局配置加载或使用传入参数
        redis_config = conf.get("redis", {})
        host = redis_config.get("host", "localhost")
        port = redis_config.get("port", 6379)
        db = redis_config.get("db", 0)
        password = redis_config.get("password")
        max_connections = redis_config.get("max_connections", 10)
        self._pool = ConnectionPool.from_url(f"redis://{host}:{port}/{db}", password=password, max_connections=max_connections, decode_responses=True)
        self._client: Optional[Redis] = None
        logger.info(f"Redis client initialized with {host}:{port}/{db}")

    async def __aenter__(self) -> "RedisClient":
        self._client = Redis(connection_pool=self._pool)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()

    async def get(self, key: str) -> Optional[str]:
        """获取键值"""
        if self._client is None:
            raise RuntimeError("Redis client not initialized")
        try:
            client: Redis = self._client
            return await client.get(key)
        except RedisError as e:
            logger.error(f"Redis GET {key} failed: {str(e)}")
            raise

    async def set(self, key: str, value: Union[str, bytes], ex: Optional[int] = None) -> bool:
        """设置键值"""
        if self._client is None:
            raise RuntimeError("Redis client not initialized")
        try:
            client: Redis = self._client
            return await client.set(key, value, ex=ex)
        except RedisError as e:
            logger.error(f"Redis SET {key} failed: {str(e)}")
            raise

    async def delete(self, *keys: str) -> int:
        """删除键"""
        if self._client is None:
            raise RuntimeError("Redis client not initialized")
        try:
            client: Redis = self._client
            return await client.delete(*keys)
        except RedisError as e:
            logger.error(f"Redis DELETE {keys} failed: {str(e)}")
            raise

    async def exists(self, *keys: str) -> int:
        """检查键是否存在"""
        if self._client is None:
            raise RuntimeError("Redis client not initialized")
        try:
            client: Redis = self._client
            return await client.exists(*keys)
        except RedisError as e:
            logger.error(f"Redis EXISTS {keys} failed: {str(e)}")
            raise

    async def expire(self, key: str, seconds: int) -> bool:
        """设置过期时间"""
        if self._client is None:
            raise RuntimeError("Redis client not initialized")
        try:
            client: Redis = self._client
            return await client.expire(key, seconds)
        except RedisError as e:
            logger.error(f"Redis EXPIRE {key} failed: {str(e)}")
            raise

    async def ping(self) -> bool:
        """检查连接"""
        if self._client is None:
            raise RuntimeError("Redis client not initialized")
        try:
            client: Redis = self._client
            return await client.ping()
        except RedisError as e:
            logger.error(f"Redis PING failed: {str(e)}")
            return False


async def test_redis():
    """测试Redis客户端"""
    redis = RedisClient()
    async with redis:
        print("PING:", await redis.ping())
        await redis.set("test_key", "test_value", ex=10)
        print("GET:", await redis.get("test_key"))
        print("EXISTS:", await redis.exists("test_key"))
        await redis.delete("test_key")
        print("AFTER DELETE - EXISTS:", await redis.exists("test_key"))


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_redis())
