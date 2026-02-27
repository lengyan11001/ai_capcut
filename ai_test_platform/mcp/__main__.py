"""MCP Server 入口：默认 stdio；加 --http 时以独立端口提供 HTTP MCP（token 走 query）。"""
import sys

from .server import mcp

if __name__ == "__main__":
    if "--http" in sys.argv:
        import uvicorn
        from . import http_server
        port = 8001
        for i, a in enumerate(sys.argv):
            if a == "--port" and i + 1 < len(sys.argv):
                try:
                    port = int(sys.argv[i + 1])
                except ValueError:
                    pass
                break
        uvicorn.run(
            http_server.app,
            host="0.0.0.0",
            port=port,
            log_level="info",
        )
    else:
        mcp.run()
