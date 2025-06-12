import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Union

import aiohttp
from aiohttp import ClientSession, ClientTimeout

from copilot.utils.logger import logger


class AsyncHttpClient:
    """异步HTTP客户端类"""

    def __init__(
        self, timeout: float = 30.0, max_connections: int = 100, max_connections_per_host: int = 30, headers: Optional[Dict[str, str]] = None
    ):
        """
        初始化异步HTTP客户端

        Args:
            timeout: 请求超时时间（秒）
            max_connections: 最大连接数
            max_connections_per_host: 每个主机最大连接数
            headers: 默认请求头
        """
        self.timeout = ClientTimeout(total=timeout)
        self.connector = aiohttp.TCPConnector(
            limit=max_connections,
            limit_per_host=max_connections_per_host,
            enable_cleanup_closed=True,
            force_close=True,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        self.default_headers = headers or {"User-Agent": "AsyncHttpClient/1.0", "Content-Type": "application/json"}
        self._session: Optional[ClientSession] = None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.start_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close_session()

    async def start_session(self):
        """启动会话"""
        if self._session is None or self._session.closed:
            self._session = ClientSession(connector=self.connector, timeout=self.timeout, headers=self.default_headers)

    async def close_session(self):
        """关闭会话"""
        if self._session and not self._session.closed:
            try:
                await self._session.close()
            except Exception as e:
                logger.warning(f"Error while closing session: {e}")

        if hasattr(self, "connector") and self.connector:
            try:
                await self.connector.close()
            except Exception as e:
                logger.warning(f"Error while closing connector: {e}")

    async def _request(
        self,
        method: str,
        url: str,
        data: Optional[Union[Dict, str, bytes]] = None,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        发送HTTP请求的通用方法

        Args:
            method: HTTP方法 (GET, POST, PUT, DELETE等)
            url: 请求URL
            data: 请求体数据
            json_data: JSON数据（自动序列化）
            headers: 请求头
            params: URL参数
            **kwargs: 其他aiohttp参数

        Returns:
            包含响应信息的字典
        """
        start_time = time.time()
        request_id = id(asyncio.current_task())

        # 确保会话已启动
        await self.start_session()

        # 合并请求头
        request_headers = self.default_headers.copy()
        if headers:
            request_headers.update(headers)

        # 准备请求数据
        if json_data is not None:
            data = json.dumps(json_data, ensure_ascii=False)
            request_headers["Content-Type"] = "application/json"

        logger.info(f"Request[{request_id}] {method} {url}", extra={"method": method, "url": url, "params": params})

        try:
            # 确保会话存在
            if self._session is None:
                raise RuntimeError("Session not started")

            async with self._session.request(method=method, url=url, data=data, headers=request_headers, params=params, **kwargs) as response:
                # 读取响应内容
                content = await response.text()

                # 尝试解析JSON
                try:
                    response_data = json.loads(content) if content else {}
                except json.JSONDecodeError:
                    response_data = {"raw_content": content}

                elapsed_time = (time.time() - start_time) * 1000

                result = {
                    "status_code": response.status,
                    "headers": dict(response.headers),
                    "data": response_data,
                    "elapsed_ms": round(elapsed_time, 2),
                    "url": str(response.url),
                    "success": 200 <= response.status < 300,
                }

                logger.info(
                    f"Response[{request_id}] {response.status} in {result['elapsed_ms']}ms",
                    extra={"status_code": response.status, "elapsed_ms": result["elapsed_ms"], "success": result["success"]},
                )

                return result

        except asyncio.TimeoutError:
            elapsed_time = (time.time() - start_time) * 1000
            logger.error(f"Request[{request_id}] timeout after {elapsed_time:.2f}ms", extra={"method": method, "url": url, "error": "timeout"})
            return {
                "status_code": 408,
                "headers": {},
                "data": {"error": "Request timeout"},
                "elapsed_ms": round(elapsed_time, 2),
                "url": url,
                "success": False,
            }

        except Exception as e:
            elapsed_time = (time.time() - start_time) * 1000
            logger.error(
                f"Request[{request_id}] failed: {str(e)}", extra={"method": method, "url": url, "error": str(e), "error_type": type(e).__name__}
            )
            return {
                "status_code": 0,
                "headers": {},
                "data": {"error": str(e), "error_type": type(e).__name__},
                "elapsed_ms": round(elapsed_time, 2),
                "url": url,
                "success": False,
            }

    async def get(self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
        """发送GET请求"""
        return await self._request("GET", url, params=params, headers=headers, **kwargs)

    async def post(
        self,
        url: str,
        data: Optional[Union[Dict, str, bytes]] = None,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """发送POST请求"""
        return await self._request("POST", url, data=data, json_data=json_data, headers=headers, **kwargs)

    async def put(
        self,
        url: str,
        data: Optional[Union[Dict, str, bytes]] = None,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """发送PUT请求"""
        return await self._request("PUT", url, data=data, json_data=json_data, headers=headers, **kwargs)

    async def delete(self, url: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
        """发送DELETE请求"""
        return await self._request("DELETE", url, headers=headers, **kwargs)

    async def patch(
        self,
        url: str,
        data: Optional[Union[Dict, str, bytes]] = None,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """发送PATCH请求"""
        return await self._request("PATCH", url, data=data, json_data=json_data, headers=headers, **kwargs)


# 全局客户端实例
_global_client: Optional[AsyncHttpClient] = None


async def get_client() -> AsyncHttpClient:
    """获取全局客户端实例"""
    global _global_client
    if _global_client is None:
        _global_client = AsyncHttpClient()
        await _global_client.start_session()
    return _global_client


async def close_client():
    """关闭全局客户端"""
    global _global_client
    if _global_client:
        await _global_client.close_session()
        _global_client = None


# 便捷函数
async def get(url: str, **kwargs) -> Dict[str, Any]:
    """发送GET请求的便捷函数"""
    client = await get_client()
    return await client.get(url, **kwargs)


async def post(url: str, **kwargs) -> Dict[str, Any]:
    """发送POST请求的便捷函数"""
    client = await get_client()
    return await client.post(url, **kwargs)


async def put(url: str, **kwargs) -> Dict[str, Any]:
    """发送PUT请求的便捷函数"""
    client = await get_client()
    return await client.put(url, **kwargs)


async def delete(url: str, **kwargs) -> Dict[str, Any]:
    """发送DELETE请求的便捷函数"""
    client = await get_client()
    return await client.delete(url, **kwargs)


async def patch(url: str, **kwargs) -> Dict[str, Any]:
    """发送PATCH请求的便捷函数"""
    client = await get_client()
    return await client.patch(url, **kwargs)


# 批量请求功能
async def batch_requests(requests: List[Dict[str, Any]], max_concurrent: int = 10) -> List[Dict[str, Any]]:
    """
    批量发送请求

    Args:
        requests: 请求列表，每个请求包含method, url等信息
        max_concurrent: 最大并发数

    Returns:
        响应结果列表
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    client = await get_client()

    async def _make_request(request_info: Dict[str, Any]) -> Dict[str, Any]:
        async with semaphore:
            method = request_info.pop("method", "GET")
            url = request_info.pop("url")
            try:
                return await client._request(method, url, **request_info)
            except Exception as e:
                return {
                    "status_code": 0,
                    "headers": {},
                    "data": {"error": str(e), "error_type": type(e).__name__},
                    "elapsed_ms": 0,
                    "url": url,
                    "success": False,
                }

    tasks = [_make_request(req.copy()) for req in requests]
    results = await asyncio.gather(*tasks, return_exceptions=False)
    return results


# 使用示例
if __name__ == "__main__":

    async def main():
        # 使用上下文管理器
        async with AsyncHttpClient() as client:
            response = await client.get("https://httpbin.org/get")
            print(f"Status: {response['status_code']}")
            print(f"Data: {response['data']}")

        # 使用便捷函数
        response = await get("https://httpbin.org/get", params={"test": "value"})
        print(f"Response: {response}")

        # 批量请求
        requests = [
            {"method": "GET", "url": "https://httpbin.org/get"},
            {"method": "POST", "url": "https://httpbin.org/post", "json_data": {"key": "value"}},
        ]
        responses = await batch_requests(requests)
        print(f"Batch responses: {len(responses)}")

        # 关闭全局客户端
        await close_client()

    asyncio.run(main())
