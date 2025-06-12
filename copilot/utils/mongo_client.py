from typing import Any, Dict, List, Optional, Union

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo.errors import PyMongoError

from copilot.utils.config import conf
from copilot.utils.logger import logger


class MongoClient:
    """异步MongoDB客户端封装类"""

    def __init__(self):
        # 从全局配置加载MongoDB配置
        mongo_config = conf.get("mongodb", {})
        self.host = mongo_config.get("host", "localhost")
        self.port = mongo_config.get("port", 27017)
        self.database_name = mongo_config.get("database", "copilot")
        self.username = mongo_config.get("username")
        self.password = mongo_config.get("password")
        self.auth_source = mongo_config.get("auth_source", "admin")
        self.max_pool_size = mongo_config.get("max_pool_size", 10)
        self.min_pool_size = mongo_config.get("min_pool_size", 1)
        self.connect_timeout = mongo_config.get("connect_timeout", 30000)
        self.server_selection_timeout = mongo_config.get("server_selection_timeout", 30000)

        self._client: Optional[AsyncIOMotorClient] = None
        self._database: Optional[AsyncIOMotorDatabase] = None

        logger.info(f"MongoDB client initialized for {self.host}:{self.port}/{self.database_name}")

    async def __aenter__(self) -> "MongoClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def connect(self) -> None:
        """连接到MongoDB"""
        try:
            # 构建连接URI
            if self.username and self.password:
                uri = f"mongodb://{self.username}:{self.password}@{self.host}:{self.port}/{self.database_name}?authSource={self.auth_source}"
            else:
                uri = f"mongodb://{self.host}:{self.port}/{self.database_name}"

            self._client = AsyncIOMotorClient(
                uri,
                maxPoolSize=self.max_pool_size,
                minPoolSize=self.min_pool_size,
                connectTimeoutMS=self.connect_timeout,
                serverSelectionTimeoutMS=self.server_selection_timeout,
            )

            self._database = self._client[self.database_name]

            # 测试连接
            if self._client:
                await self._client.admin.command("ping")
            logger.info(f"Successfully connected to MongoDB at {self.host}:{self.port}")

        except PyMongoError as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise

    async def close(self) -> None:
        """关闭MongoDB连接"""
        if self._client:
            self._client.close()
            logger.info("MongoDB connection closed")

    def get_collection(self, collection_name: str) -> AsyncIOMotorCollection:
        """获取集合对象"""
        if self._database is None:
            raise RuntimeError("MongoDB client not connected")
        return self._database[collection_name]

    async def ping(self) -> bool:
        """检查连接状态"""
        if self._client is None:
            return False
        try:
            await self._client.admin.command("ping")
            return True
        except PyMongoError as e:
            logger.error(f"MongoDB ping failed: {str(e)}")
            return False

    # 文档操作方法
    async def insert_one(self, collection_name: str, document: Dict[str, Any]) -> str:
        """插入单个文档"""
        try:
            collection = self.get_collection(collection_name)
            result = await collection.insert_one(document)
            logger.debug(f"Inserted document into {collection_name}: {result.inserted_id}")
            return str(result.inserted_id)
        except PyMongoError as e:
            logger.error(f"Failed to insert document into {collection_name}: {str(e)}")
            raise

    async def insert_many(self, collection_name: str, documents: List[Dict[str, Any]]) -> List[str]:
        """插入多个文档"""
        try:
            collection = self.get_collection(collection_name)
            result = await collection.insert_many(documents)
            ids = [str(oid) for oid in result.inserted_ids]
            logger.debug(f"Inserted {len(ids)} documents into {collection_name}")
            return ids
        except PyMongoError as e:
            logger.error(f"Failed to insert documents into {collection_name}: {str(e)}")
            raise

    async def find_one(
        self, collection_name: str, filter_dict: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """查找单个文档"""
        try:
            collection = self.get_collection(collection_name)
            result = await collection.find_one(filter_dict or {}, projection)
            if result and "_id" in result:
                result["_id"] = str(result["_id"])
            return result
        except PyMongoError as e:
            logger.error(f"Failed to find document in {collection_name}: {str(e)}")
            raise

    async def find_many(
        self,
        collection_name: str,
        filter_dict: Optional[Dict[str, Any]] = None,
        projection: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
        sort: Optional[List[tuple]] = None,
    ) -> List[Dict[str, Any]]:
        """查找多个文档"""
        try:
            collection = self.get_collection(collection_name)
            cursor = collection.find(filter_dict or {}, projection)

            if skip:
                cursor = cursor.skip(skip)
            if limit:
                cursor = cursor.limit(limit)
            if sort:
                cursor = cursor.sort(sort)

            results = await cursor.to_list(length=None)

            # 转换ObjectId为字符串
            for result in results:
                if "_id" in result:
                    result["_id"] = str(result["_id"])

            return results
        except PyMongoError as e:
            logger.error(f"Failed to find documents in {collection_name}: {str(e)}")
            raise

    async def update_one(self, collection_name: str, filter_dict: Dict[str, Any], update_dict: Dict[str, Any], upsert: bool = False) -> int:
        """更新单个文档"""
        try:
            collection = self.get_collection(collection_name)
            result = await collection.update_one(filter_dict, update_dict, upsert=upsert)
            logger.debug(f"Updated {result.modified_count} document(s) in {collection_name}")
            return result.modified_count
        except PyMongoError as e:
            logger.error(f"Failed to update document in {collection_name}: {str(e)}")
            raise

    async def update_many(self, collection_name: str, filter_dict: Dict[str, Any], update_dict: Dict[str, Any], upsert: bool = False) -> int:
        """更新多个文档"""
        try:
            collection = self.get_collection(collection_name)
            result = await collection.update_many(filter_dict, update_dict, upsert=upsert)
            logger.debug(f"Updated {result.modified_count} document(s) in {collection_name}")
            return result.modified_count
        except PyMongoError as e:
            logger.error(f"Failed to update documents in {collection_name}: {str(e)}")
            raise

    async def delete_one(self, collection_name: str, filter_dict: Dict[str, Any]) -> int:
        """删除单个文档"""
        try:
            collection = self.get_collection(collection_name)
            result = await collection.delete_one(filter_dict)
            logger.debug(f"Deleted {result.deleted_count} document(s) from {collection_name}")
            return result.deleted_count
        except PyMongoError as e:
            logger.error(f"Failed to delete document from {collection_name}: {str(e)}")
            raise

    async def delete_many(self, collection_name: str, filter_dict: Dict[str, Any]) -> int:
        """删除多个文档"""
        try:
            collection = self.get_collection(collection_name)
            result = await collection.delete_many(filter_dict)
            logger.debug(f"Deleted {result.deleted_count} document(s) from {collection_name}")
            return result.deleted_count
        except PyMongoError as e:
            logger.error(f"Failed to delete documents from {collection_name}: {str(e)}")
            raise

    async def count_documents(self, collection_name: str, filter_dict: Optional[Dict[str, Any]] = None) -> int:
        """统计文档数量"""
        try:
            collection = self.get_collection(collection_name)
            count = await collection.count_documents(filter_dict or {})
            return count
        except PyMongoError as e:
            logger.error(f"Failed to count documents in {collection_name}: {str(e)}")
            raise

    async def create_index(self, collection_name: str, keys: Union[str, List[tuple]], unique: bool = False, background: bool = True) -> str:
        """创建索引"""
        try:
            collection = self.get_collection(collection_name)
            result = await collection.create_index(keys, unique=unique, background=background)
            logger.info(f"Created index on {collection_name}: {result}")
            return result
        except PyMongoError as e:
            logger.error(f"Failed to create index on {collection_name}: {str(e)}")
            raise
