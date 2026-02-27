"""MCP Server 入口：默认 stdio 传输，供 Cursor 等客户端连接。"""
from .server import mcp

if __name__ == "__main__":
    mcp.run()
