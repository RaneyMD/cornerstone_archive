# Contributing to Cornerstone Archive

Thank you for contributing to Cornerstone Archive! This document provides guidelines to help you make meaningful contributions.

## Table of Contents

- [Code Standards](#code-standards)
- [Commit Guidelines](#commit-guidelines)
- [CHANGELOG Requirements](#changelog-requirements)
- [Pull Request Process](#pull-request-process)
- [Development Workflow](#development-workflow)
- [Testing](#testing)

## Code Standards

### File Organization

- **Web Console**: `web_console/console_root/` - PHP/JavaScript frontend
  - `pages/` - HTML page templates
  - `api/` - REST API endpoints
  - `assets/` - CSS and JavaScript files
  - `auth/` - Authentication logic
  - `app/` - Core application classes
  - `config/` - Configuration (example.php provided, config.php in .gitignore)

- **Watcher**: `scripts/watcher/` - Python task execution engine
  - Continuous monitoring and handler execution

- **Supervisor**: `scripts/supervisor/` - Python control operations
  - Handler implementations for supervisor tasks

- **Database**: `database/migrations/` - SQL migration files
  - Sequential numbering: `001_`, `002_`, `003_`, etc.

### Code Style

- **PHP**: Follow PSR-12 coding standard
  - Use prepared statements for all database queries
  - Always escape output with `htmlspecialchars()` or `escapeHtml()`
  - Proper error handling with try-catch blocks

- **JavaScript**: ES6+ modern standards
  - Use `const`/`let` instead of `var`
  - Clear function documentation with JSDoc comments
  - Defensive programming (handle null/undefined values)

- **Python**: Follow PEP 8
  - Use type hints where applicable
  - Comprehensive error handling with custom exceptions
  - Clear logging at appropriate levels

## Commit Guidelines

### Conventional Commits

Follow [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation changes
- `style` - Code style (formatting, missing semicolons, etc.)
- `refactor` - Code refactoring without feature changes
- `perf` - Performance improvements
- `test` - Test additions or modifications
- `chore` - Build system, dependency updates, etc.
- `debug` - Temporary debugging additions

**Scopes:**
- `dashboard` - Dashboard/frontend changes
- `api` - API endpoint changes
- `watcher` - Watcher service changes
- `supervisor` - Supervisor service changes
- `database` - Database schema/migrations
- `utils` - Utility functions and helpers
- `config` - Configuration changes

**Subject:**
- Use imperative mood ("add" not "added")
- Don't capitalize first letter
- No period at end
- Max 50 characters

**Body:**
- Explain *what* and *why*, not *how*
- Wrap at 72 characters
- Reference issues and PRs when applicable

### Example Commits

```
feat(dashboard): display queued jobs in task queue

Add job loading and display functionality so control flags
appear immediately after creation. Implement auto-refresh
every 5 seconds to show real-time job status updates.

Fixes #123
```

```
fix(utils): make escapeHtml handle non-string inputs

escapeHtml() was throwing TypeError when receiving numeric
values from database queries. Now converts all inputs to
strings and handles null/undefined gracefully.
```

## CHANGELOG Requirements

**⚠️ CRITICAL: Every meaningful code change must include a CHANGELOG entry.**

### When to Update CHANGELOG

Update `CHANGELOG.md` for:
- ✅ New features (`feat`)
- ✅ Bug fixes (`fix`)
- ✅ Critical changes (`fix` with impact on user experience)
- ✅ API changes
- ✅ Database migrations
- ✅ Security fixes

Do NOT update for:
- ❌ Typo fixes in comments
- ❌ Code formatting/style changes
- ❌ Internal refactoring with no user impact
- ❌ Test-only changes

### CHANGELOG Format

Add entries under the appropriate section (`Added`, `Changed`, `Fixed`) in the `[Unreleased]` section:

```markdown
### Added

#### Feature Name
- **Specific capability**: Description of what it does
  - Implementation detail 1
  - Implementation detail 2
  - Configuration option if applicable

### Fixed

#### Issue Name
- **Problem**: What was broken
- **Impact**: How it affected users
- **Solution**: What was changed
- **Verification**: How to verify the fix
```

### CHANGELOG Workflow

1. **Before committing**: Draft CHANGELOG entry describing the change
2. **Stage files**: Add both the code AND CHANGELOG.md
3. **Commit**: Include both in single commit
4. **Verify**: Check that CHANGELOG is committed alongside code

Example git flow:
```bash
git add web_console/console_root/api/new_endpoint.php CHANGELOG.md
git commit -m "feat(api): add new_endpoint"
git push origin main
```

## Pull Request Process

1. **Create branch** from `main`:
   ```bash
   git checkout -b feature/descriptive-name
   ```

2. **Implement changes** following code standards

3. **Update CHANGELOG.md** with your changes

4. **Commit early and often** with conventional commit messages

5. **Push to remote** and create PR with:
   - Clear title describing the feature/fix
   - Detailed description of changes
   - Reference to related issues
   - Test instructions

6. **Address review feedback**:
   - Don't amend published commits - create new commits
   - Keep discussion in PR comments

7. **Merge** only after approval and all checks pass

## Development Workflow

### Local Setup

```bash
# Clone repository
git clone https://github.com/RaneyMD/cornerstone_archive.git
cd cornerstone_archive

# Set up configuration
cp web_console/console_root/config/config.example.php web_console/console_root/config/config.php
# Edit config.php with your local settings

# Create .claude directory for Claude Code settings (optional)
mkdir -p .claude
```

### Testing Changes

Before committing:

1. **Test locally** - Verify feature works as expected
2. **Check console** - No JavaScript errors or warnings
3. **Database** - Run migrations if schema changed
4. **API** - Test endpoints return expected responses
5. **UI** - Verify page rendering and interactions

### Reverting Changes

- **Uncommitted**: `git restore <file>`
- **Staged**: `git restore --staged <file>`
- **Committed (new)**: Create new commit with revert
- **Published**: Use `git revert` instead of `git reset --hard`

## Testing

### PHP API Endpoints

Test with curl or browser:
```bash
curl -X GET https://dev-console.raneyworld.com/api/list_jobs.php
```

### JavaScript Changes

Check browser console (F12):
- No JavaScript errors
- Check Network tab for API responses
- Verify proper HTML escaping in rendered content

### Database Migrations

Apply migrations:
```bash
python scripts/database/apply_migration.py --config config/config.dev.yaml
```

Verify table structure:
```bash
mysql -h host -u user -p database -e "DESCRIBE table_name;"
```

## Questions?

- Check existing issues and documentation
- Review recent commits for similar patterns
- Ask in PR comments or issues

## Code of Conduct

- Be respectful and constructive
- Provide helpful feedback
- Focus on code quality and user experience
- Acknowledge contributions from others

---

**Last Updated**: February 2026
