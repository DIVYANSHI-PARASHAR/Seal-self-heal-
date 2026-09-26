# Development connections

The harness uses its own MongoDB and LangSmith SDK clients at runtime. The
development connections below are separate, human or coding-agent tools for
inspecting the same services while evolving the harness.

## MongoDB Atlas

`scripts/atlas-readonly-mcp` starts the official MongoDB MCP server in Docker.
It loads `ATLAS_URI` from the existing `.env` file only when the process starts,
maps it to the MCP server's connection-string setting, and enables read-only
mode. The Codex configuration contains only the launcher path, never the
connection string.

The server is pinned to version `3.0.4`. It exposes read, connection, and
metadata tools and cannot make database changes. A dedicated Atlas database
user with the `read` role on `self_heal` remains the recommended credential for
this connection.

After the one-time Codex registration, restart Codex and ask ordinary questions
such as “List the collections in the self_heal database” or “Show the schema of
the runs collection.”

## LangSmith

LangSmith's Remote MCP server currently cannot authenticate from Codex CLI due
to a documented OAuth compatibility issue. Use the official LangSmith CLI from
Codex instead:

```sh
./scripts/langsmith-readonly projects
./scripts/langsmith-readonly traces 5
./scripts/langsmith-readonly runs 5
./scripts/langsmith-readonly trace <trace-id>
```

The wrapper loads the existing `LANGSMITH_API_KEY` only when a query runs; it
does not copy it into Codex configuration or the command line. It allows only
read commands. You can instead authenticate the CLI independently with
`langsmith auth login`, which stores an OAuth token in the user profile. The
harness continues to use `LANGSMITH_API_KEY` from `.env` for application
tracing.

## References

- [MongoDB MCP Server security guidance](https://www.mongodb.com/docs/mcp-server/local-mcp/security-best-practices/)
- [MongoDB MCP Docker setup](https://github.com/mongodb-js/mongodb-mcp-server#option-5-using-docker)
- [LangSmith Remote MCP compatibility](https://docs.langchain.com/langsmith/langsmith-remote-mcp#known-client-incompatibilities)
- [LangSmith CLI](https://docs.langchain.com/langsmith/langsmith-cli)
