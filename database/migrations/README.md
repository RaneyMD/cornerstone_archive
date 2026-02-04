# Database Migrations

Migrations are applied in numeric order. Each migration is idempotent (safe to run multiple times).

## Running Migrations

**Development:**
```bash
python -m scripts.database.apply_migration \
  --config config/config.dev.yaml \
  --migration database/migrations/001_create_schema_foundation.sql
```

**Production:**
```bash
python -m scripts.database.apply_migration \
  --config config/config.yaml \
  --migration database/migrations/001_create_schema_foundation.sql
```

## Migration List

- **001_create_schema_foundation.sql** — Create base tables (families, titles, issues, containers, pages, works)
- **002_add_instance_keys.sql** — Add instance_key columns and auto-generation
- **003_create_hybrid_schema.sql** — Add page packs and manifest support
- **004_page_assets_and_manifests.sql** — Track extracted images and OCR files

## Rollback

Each migration should have a rollback script to revert changes if needed.

## Safe Testing

Always test migrations in dev first:
1. Apply to `raneywor_csa_dev_state`
2. Verify schema with `SHOW TABLES;` and `DESCRIBE table_name;`
3. Once confident, apply to production
4. Never skip backups
