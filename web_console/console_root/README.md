# Cornerstone Archive Console

Multi-watcher management and real-time monitoring system for the Cornerstone Archive.

## Project Structure

```
console_root/
├── index.php                    # Entry point and router
├── config/
│   ├── config.example.php      # Configuration template
│   └── config.php              # (Create from example, add credentials)
├── auth/
│   ├── login.php               # Login form and authentication
│   ├── logout.php              # Session cleanup
│   └── session_check.php       # Session validator (included in protected pages)
├── app/
│   ├── Database.php            # DB wrapper class
│   ├── NasMonitor.php          # Heartbeat file reader (coming soon)
│   ├── Watcher.php             # Single watcher status (coming soon)
│   ├── WatcherManager.php      # Multi-watcher management (coming soon)
│   └── TaskManager.php         # Task operations (coming soon)
├── api/
│   ├── heartbeat.php           # AJAX: all watcher statuses (coming soon)
│   ├── watcher.php             # AJAX: single watcher detail (coming soon)
│   ├── tasks.php               # AJAX: task lists (coming soon)
│   ├── control.php             # AJAX: control actions (coming soon)
│   └── logs.php                # AJAX: watcher logs (coming soon)
├── pages/
│   ├── dashboard.php           # Main dashboard page
│   ├── watcher.php             # Single watcher detail (coming soon)
│   ├── tasks.php               # Task management (coming soon)
│   └── settings.php            # Configuration page (coming soon)
├── assets/
│   ├── css/
│   │   └── style.css           # Custom Bootstrap overrides
│   └── js/
│       ├── dashboard.js        # Dashboard AJAX logic (coming soon)
│       └── utils.js            # Shared AJAX and utilities
└── .htaccess                    # URL rewriting and security

```

## Quick Start

### 1. Create Configuration

```bash
cp config/config.example.php config/config.php
```

Edit `config/config.php` with:
- Database credentials (MySQL)
- Console username and password hash
- Watcher list (OrionMX, OrionMega, etc.)
- NAS paths (Windows UNC format)

### 2. Generate Password Hash

```bash
php -r "echo password_hash('your_password_here', PASSWORD_BCRYPT);"
```

Copy the output into `CONSOLE_PASSWORD_HASH` in config.php.

### 3. Set up Database

Ensure the MySQL database `raneywor_csa_state` exists with required tables:
- `audit_log_t` — Login/logout/action logs
- `watcher_state_t` — Watcher status snapshots
- Other task/result tables as per watcher schema

### 4. Deploy to HostGator

```bash
cp -r console_root/* /home/cornerstonearchive/public_html/
```

### 5. Test

Visit: `https://console.raneyworld.com`

## Authentication Flow

1. User visits console → redirected to `/auth/login.php` if not authenticated
2. Username + password form
3. Validates against `CONSOLE_USERNAME` and `CONSOLE_PASSWORD_HASH`
4. On success: Creates session, logs action to `audit_log_t`, redirects to dashboard
5. All pages check session via `auth/session_check.php`
6. Session timeout: 1 hour (configurable)

## Security Features

- ✅ HTTPS enforced via `.htaccess`
- ✅ SQL injection prevention (PDO prepared statements)
- ✅ XSS prevention (htmlspecialchars for all output)
- ✅ CSRF token support (ready for POST endpoints)
- ✅ Password hashing (bcrypt)
- ✅ Session security (HttpOnly, Secure flags, regeneration)
- ✅ Audit logging (all actions logged to database)
- ✅ Path traversal prevention (file inclusion checks)

## Coming Next

1. **NAS Monitor** — Read heartbeat files from all watchers
2. **Watcher Manager** — Query and manage multiple watcher instances
3. **AJAX Endpoints** — Real-time status polling
4. **Dashboard Logic** — Multi-watcher cards, refresh, controls
5. **Control Actions** — Restart, logs, create test tasks
6. **Task Management** — List pending/recent results

## Dependencies

- PHP 7.4+ (HostGator standard)
- MySQL 5.7+ (HostGator database)
- Bootstrap 5.3 (CDN)
- jQuery 3.6 (CDN)

No Composer, npm, or external PHP packages required.

## Configuration Reference

See `config/config.example.php` for all available settings.

Key env vars (can be set in HostGator control panel):
- `DB_HOST` — MySQL host
- `DB_USER` — MySQL user
- `DB_PASS` — MySQL password
- `DB_NAME` — MySQL database name
- `CONSOLE_USERNAME` — Login username
- `CONSOLE_PASSWORD_HASH` — Bcrypt password hash
- `DEBUG_MODE` — Enable debug output (false by default)

## Support

For issues, check:
1. `DEBUG_MODE` in config to enable verbose output
2. Browser DevTools console for AJAX errors
3. PHP error log on HostGator (cPanel)
4. Database connection and table creation

---

**Version:** 1.0.0
**Author:** Cornerstone Archive Team
**License:** See LICENSE file
