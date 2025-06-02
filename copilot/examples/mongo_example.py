"""
MongoDB客户端使用示例

这个示例展示了如何使用MongoDB客户端进行基本的CRUD操作。

使用前请确保：
1. MongoDB服务已启动 (docker-compose up -d mongodb)
2. 已安装依赖包：pip install motor pymongo
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any

from copilot.utils.mongo_client import MongoClient
from copilot.utils.logger import logger


async def user_crud_example():
    """用户CRUD操作示例"""
    async with MongoClient() as mongo:
        collection = "users"
        
        print("=== MongoDB用户CRUD操作示例 ===\n")
        
        # 1. 插入单个用户
        print("1. 插入单个用户")
        user_doc = {
            "username": "张三",
            "email": "zhangsan@example.com",
            "age": 28,
            "created_at": datetime.now(),
            "profile": {
                "city": "北京",
                "hobby": ["阅读", "旅游", "编程"]
            }
        }
        user_id = await mongo.insert_one(collection, user_doc)
        print(f"插入用户ID: {user_id}\n")
        
        # 2. 插入多个用户
        print("2. 插入多个用户")
        users = [
            {
                "username": "李四",
                "email": "lisi@example.com", 
                "age": 25,
                "created_at": datetime.now(),
                "profile": {"city": "上海", "hobby": ["音乐", "电影"]}
            },
            {
                "username": "王五",
                "email": "wangwu@example.com",
                "age": 30,
                "created_at": datetime.now(),
                "profile": {"city": "深圳", "hobby": ["运动", "游戏"]}
            }
        ]
        user_ids = await mongo.insert_many(collection, users)
        print(f"插入用户IDs: {user_ids}\n")
        
        # 3. 查找单个用户
        print("3. 查找单个用户")
        user = await mongo.find_one(collection, {"username": "张三"})
        print(f"找到用户: {user}\n")
        
        # 4. 查找多个用户
        print("4. 查找所有用户")
        all_users = await mongo.find_many(collection, {})
        print(f"所有用户数量: {len(all_users)}")
        for user in all_users:
            print(f"  - {user['username']} ({user['email']})")
        print()
        
        # 5. 条件查询
        print("5. 条件查询 - 年龄大于26岁的用户")
        adult_users = await mongo.find_many(collection, {"age": {"$gt": 26}})
        for user in adult_users:
            print(f"  - {user['username']}: {user['age']}岁")
        print()
        
        # 6. 更新用户信息
        print("6. 更新用户信息")
        updated_count = await mongo.update_one(
            collection,
            {"username": "张三"},
            {"$set": {"age": 29, "profile.city": "广州"}}
        )
        print(f"更新了 {updated_count} 个用户")
        
        # 验证更新
        updated_user = await mongo.find_one(collection, {"username": "张三"})
        print(f"更新后的用户信息: {updated_user}\n")
        
        # 7. 文档计数
        print("7. 统计文档数量")
        total_count = await mongo.count_documents(collection)
        adult_count = await mongo.count_documents(collection, {"age": {"$gte": 28}})
        print(f"总用户数: {total_count}")
        print(f"年龄>=28的用户数: {adult_count}\n")
        
        # 8. 创建索引
        print("8. 创建索引")
        try:
            index_name = await mongo.create_index(collection, "email", unique=True)
            print(f"创建索引: {index_name}\n")
        except Exception as e:
            print(f"索引创建失败（可能已存在）: {e}\n")
        
        # 9. 删除操作
        print("9. 删除操作")
        deleted_count = await mongo.delete_one(collection, {"username": "李四"})
        print(f"删除了 {deleted_count} 个用户")
        
        # 最终统计
        final_count = await mongo.count_documents(collection)
        print(f"最终用户数: {final_count}")


async def article_example():
    """文章管理示例"""
    async with MongoClient() as mongo:
        collection = "articles"
        
        print("\n=== MongoDB文章管理示例 ===\n")
        
        # 插入文章
        articles = [
            {
                "title": "Python异步编程指南",
                "author": "张三",
                "content": "这是关于Python异步编程的详细指南...",
                "tags": ["python", "async", "编程"],
                "views": 150,
                "published": True,
                "created_at": datetime.now()
            },
            {
                "title": "MongoDB入门教程", 
                "author": "李四",
                "content": "MongoDB是一个流行的NoSQL数据库...",
                "tags": ["mongodb", "database", "nosql"],
                "views": 89,
                "published": True,
                "created_at": datetime.now()
            },
            {
                "title": "Docker容器化部署",
                "author": "王五", 
                "content": "使用Docker进行应用容器化部署...",
                "tags": ["docker", "部署", "容器"],
                "views": 203,
                "published": False,
                "created_at": datetime.now()
            }
        ]
        
        await mongo.insert_many(collection, articles)
        print("插入了3篇文章")
        
        # 查询已发布的文章
        published_articles = await mongo.find_many(
            collection, 
            {"published": True},
            sort=[("views", -1)]  # 按浏览量降序
        )
        print(f"\n已发布文章 (按浏览量排序):")
        for article in published_articles:
            print(f"  - {article['title']} (浏览量: {article['views']})")
        
        # 标签查询
        python_articles = await mongo.find_many(
            collection,
            {"tags": {"$in": ["python"]}}
        )
        print(f"\n包含'python'标签的文章:")
        for article in python_articles:
            print(f"  - {article['title']}")
        
        # 清理测试数据
        await mongo.delete_many(collection, {})
        print(f"\n清理了文章测试数据")


async def connection_test():
    """连接测试"""
    print("=== MongoDB连接测试 ===\n")
    
    try:
        async with MongoClient() as mongo:
            is_connected = await mongo.ping()
            if is_connected:
                print("✅ MongoDB连接成功!")
                
                # 获取数据库信息
                if mongo._client:
                    db_stats = await mongo._client.admin.command("dbStats")
                    print(f"数据库统计信息: {db_stats}")
            else:
                print("❌ MongoDB连接失败!")
                
    except Exception as e:
        print(f"❌ 连接错误: {e}")
        print("请确保:")
        print("1. MongoDB服务已启动: docker-compose up -d mongodb")  
        print("2. 配置文件中的连接信息正确")
        print("3. 已安装依赖: pip install motor pymongo")


async def main():
    """主函数"""
    # 首先测试连接
    await connection_test()
    
    # 如果连接成功，运行CRUD示例
    try:
        await user_crud_example()
        await article_example()
    except Exception as e:
        logger.error(f"示例运行出错: {e}")
        print(f"\n❌ 示例运行出错: {e}")
        print("请检查MongoDB服务是否正常运行")


if __name__ == "__main__":
    asyncio.run(main())