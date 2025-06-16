#!/bin/bash

# Agent Backend 测试运行脚本

set -e

# 默认配置
SERVER_URL="http://localhost:8000"
TEST_MODULE="all"
PYTHON_CMD="python"

# 帮助信息
show_help() {
    cat << EOF
Agent Backend 测试运行脚本

用法: $0 [选项]

选项:
    -s, --server URL     指定服务器地址 (默认: http://localhost:8000)
    -t, --test MODULE    指定测试模块 (默认: all)
                         可选值: all, auth, session, chat
    -p, --python CMD     指定Python命令 (默认: python)
    -h, --help           显示此帮助信息

示例:
    $0                                    # 运行所有测试
    $0 --test auth                        # 只运行认证测试
    $0 --server http://192.168.1.100:8000 # 指定服务器地址
    $0 --python python3                   # 使用python3命令

环境变量:
    TEST_BASE_URL        服务器地址 (覆盖 --server 参数)
    TEST_MODULE          测试模块 (覆盖 --test 参数)
EOF
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -s|--server)
            SERVER_URL="$2"
            shift 2
            ;;
        -t|--test)
            TEST_MODULE="$2"
            shift 2
            ;;
        -p|--python)
            PYTHON_CMD="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "未知参数: $1"
            show_help
            exit 1
            ;;
    esac
done

# 检查环境变量
if [[ -n "${TEST_BASE_URL}" ]]; then
    SERVER_URL="${TEST_BASE_URL}"
fi

if [[ -n "${TEST_MODULE}" ]]; then
    TEST_MODULE="${TEST_MODULE}"
fi

# 检查Python命令是否可用
if ! command -v "$PYTHON_CMD" &> /dev/null; then
    echo "❌ Python命令不可用: $PYTHON_CMD"
    exit 1
fi

# 检查依赖包
echo "🔍 检查依赖包..."
if ! $PYTHON_CMD -c "import aiohttp" 2>/dev/null; then
    echo "❌ 缺少依赖包: aiohttp"
    echo "请运行: pip install aiohttp"
    exit 1
fi

# 获取脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🚀 Agent Backend 测试套件"
echo "📂 项目目录: $PROJECT_DIR"
echo "📡 服务器地址: $SERVER_URL"
echo "🧪 测试模块: $TEST_MODULE"
echo "🐍 Python命令: $PYTHON_CMD"
echo ""

# 切换到tests目录
cd "$SCRIPT_DIR"

# 设置Python路径
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

# 运行测试
echo "▶️  开始运行测试..."
$PYTHON_CMD test_suite.py --test "$TEST_MODULE" --server "$SERVER_URL"
TEST_EXIT_CODE=$?

echo ""
if [[ $TEST_EXIT_CODE -eq 0 ]]; then
    echo "✅ 测试执行成功"
else
    echo "❌ 测试执行失败 (退出代码: $TEST_EXIT_CODE)"
fi

exit $TEST_EXIT_CODE
