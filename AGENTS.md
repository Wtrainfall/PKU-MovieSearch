# Repository Guidelines

## Project Structure & Module Organization
This repository is a Dockerized Django movie search project. Root-level orchestration lives in `docker-compose.yml`, with service images in `web/` and `es/`. The Django project is under `web/MovieSearch/`; app modules are `movies/`, `search/`, and `users/`, with shared templates in `web/MovieSearch/templates/`. Raw source data lives in `web/data_origin/`, while processed JSON caches live in `web/data_cache/`. Search ingestion utilities and custom management commands are in `web/MovieSearch/search/utils/` and `web/MovieSearch/search/management/commands/`.

## Build, Test, and Development Commands
Use Docker for local development:

- `docker compose up --build`: start MySQL, Elasticsearch, Django, and Kibana.
- `docker compose exec web python MovieSearch/manage.py migrate`: apply database migrations.
- `docker compose exec web python MovieSearch/manage.py test`: run the Django test suite.
- `docker compose exec web python MovieSearch/manage.py processData --path /app/data_origin`: preprocess raw movie text files.
- `docker compose exec web python MovieSearch/manage.py createIndex`: create the Elasticsearch index.
- `docker compose exec web python MovieSearch/manage.py importMovie --path /app/data_cache/db_cache --db --type movie`: import processed data into MySQL.

## Coding Style & Naming Conventions
Follow existing Django and Python conventions: 4-space indentation, `snake_case` for functions and modules, `CamelCase` for model, form, and command classes. Keep apps and URL modules lowercase. Group imports as standard library, third-party, then local modules. No formatter or linter is configured in the repo, so keep changes PEP 8-aligned and consistent with surrounding code.

## Testing Guidelines
Tests currently use Django’s `TestCase` and live in each app’s `tests.py`. Add or expand tests whenever you change models, views, auth flows, or management commands. Prefer test names like `test_search_returns_results` that describe behavior directly. Run `docker compose exec web python MovieSearch/manage.py test` before opening a PR.

## Commit & Pull Request Guidelines
Recent history uses short, imperative commit subjects, often in Chinese, such as `修改环境配置` and `添加了用户管理与数据库模型`. Keep commit messages concise and focused on one change. PRs should include a brief summary, affected areas, required environment or data steps, and screenshots for template/UI changes.

## Security & Configuration Tips
Keep secrets in `.env`; do not hardcode API keys or database passwords. Review `web/MovieSearch/MovieSearch/settings.py` when changing environment variables, database settings, or Elasticsearch connectivity.
