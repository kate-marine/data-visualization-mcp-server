from __future__ import annotations

import sys

# Tool and resource registrations 
import data_viz_mcp.tools.datasets  
import data_viz_mcp.tools.transforms  
import data_viz_mcp.tools.specs 
import data_viz_mcp.tools.plots  

from data_viz_mcp.server import logger, mcp


def main() -> None:
    logger.info(
        "starting",
        extra={
            "tool": "startup",
            "resource_ids": [],
            "outcome": f"python={sys.version.split()[0]} transport=stdio",
        },
    )
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
