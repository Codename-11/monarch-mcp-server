"""FastMCP application instance and entry point."""

import logging

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("Monarch Money MCP Server")

# Import tools package to trigger @mcp.tool() registration
import monarch_mcp_server.tools  # noqa: E402, F401
from monarch_mcp_server.access_policy import apply_tool_access_policy  # noqa: E402

apply_tool_access_policy(mcp)

# Export for `mcp run`
app = mcp


def main() -> None:
    """Main entry point for the server."""
    logger.info("Starting Monarch Money MCP Server...")
    try:
        mcp.run()
    except Exception as e:
        logger.error(f"Failed to run server: {str(e)}")
        raise


if __name__ == "__main__":
    main()
