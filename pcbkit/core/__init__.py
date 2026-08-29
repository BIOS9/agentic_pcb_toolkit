"""Pure functions behind every pcbkit frontend.

Nothing here touches argv, prints to stdout, or calls sys.exit. The CLI (and
later an MCP server, and the v2 gate wrappers) are thin shells over this
package -- that split is what keeps the v2 gate layer cheap to add.
"""
