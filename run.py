#!/usr/bin/env python3
"""
项目启动脚本
"""
import uvicorn

from copilot.main import app

if __name__ == "__main__":
    uvicorn.run("copilot.main:app", host="0.0.0.0", port=5002, reload=True, reload_dirs=["copilot"])
