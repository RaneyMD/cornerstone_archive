# Prompt Library

Store Claude Code markdown prompts for the spec watcher in this directory.

Example usage:

```bash
spec_watcher --prompt-file prompts/refactor.md
spec_watcher --prompt-file prompts/generate-tests.md --model sonnet
```

Prompt results are stored in the task result payload under `prompt_execution`.
If Claude fails, `prompt_execution.success` is `false` and an `error` message is
included, so consumers should handle failures gracefully.

The watcher passes the prompt contents directly to `claude -p` using a
subprocess argument list (not a shell string), so newlines and special
characters are preserved without shell interpretation.

If Claude exits successfully but emits warnings on stderr, the watcher logs
stderr in the prompt execution payload without treating it as a failure.
