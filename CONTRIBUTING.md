# Contributing

Contributions are very welcome! For bigger changes, it may be a good idea to open an issue first and
discuss the proposed changes before submitting a pull request.

## Setting up

1. First, install [mise](https://mise.jdx.dev/) — it will automatically install uv and Python for you.
2. Run `mise run install` to create a virtual env and install dev dependencies.
3. To run tests, run `mise run test`. Pass extra pytest args with `mise run test -- -x -k test_foo`.

## Claude Code

This repo ships an [`AGENTS.md`](AGENTS.md) with guidance for AI agents. Claude Code doesn't read `AGENTS.md` natively — to load it, use [claude-agents-md-loader](https://tangled.org/btao.org/claude-agents-md-loader).
