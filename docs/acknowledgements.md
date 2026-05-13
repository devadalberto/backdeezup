# Acknowledgements

BackDeezUp is built on the shoulders of excellent open-source projects and services.

---

## Core framework

**[Django](https://www.djangoproject.com/)**
The web framework this project is built on. Django's ORM, admin interface, and batteries-included philosophy make it ideal for data-heavy backend pipelines.
License: BSD-3-Clause

**[Django Ninja](https://django-ninja.dev/)**
FastAPI-style API framework for Django. Provides automatic Swagger/OpenAPI documentation, type-safe request/response schemas via Pydantic, and clean routing without the overhead of DRF.
License: MIT

---

## Google integration

**[Google APIs Python Client](https://github.com/googleapis/google-api-python-client)**
The official Python client library for Google APIs, used for Drive v3 and Photos Library API integration.
License: Apache-2.0

**[google-auth-oauthlib](https://github.com/googleapis/google-auth-library-python-oauthlib)**
OAuth 2.0 integration for Google APIs. Powers the local OAuth flow via `InstalledAppFlow`.
License: Apache-2.0

---

## Security

**[cryptography](https://cryptography.io/)**
Provides the `Fernet` symmetric encryption used to store OAuth tokens encrypted on disk. Industry-standard, audited cryptography library.
License: Apache-2.0 / BSD

---

## Package management

**[uv](https://docs.astral.sh/uv/)** by [Astral](https://astral.sh/)
A blazing-fast Rust-based Python package and project manager. Replaces pip, virtualenv, and pip-tools with a single tool that is 10-100x faster. BackDeezUp adopted uv in v0.2.0.
License: MIT / Apache-2.0

---

## Infrastructure

**[Gunicorn](https://gunicorn.org/)**
Production WSGI server for serving the Django application.
License: MIT

**[WhiteNoise](https://whitenoise.readthedocs.io/)**
Efficient static file serving directly from Django without a separate static file server.
License: MIT

**[psycopg2](https://www.psycopg.org/)**
PostgreSQL adapter for Python, used for production database connectivity.
License: LGPL-3.0

**[python-decouple](https://github.com/HBNetwork/python-decouple)**
Clean separation of configuration from code. All environment variables are read through decouple.
License: MIT

**[dj-database-url](https://github.com/jazzband/dj-database-url)**
Parse `DATABASE_URL` environment variables into Django `DATABASES` settings.
License: BSD-2-Clause

---

## Documentation

**[MkDocs](https://www.mkdocs.org/)**
Static site generator for project documentation. Builds this documentation site from Markdown files.
License: BSD-2-Clause

**[MkDocs Material](https://squidfunk.github.io/mkdocs-material/)** by [Martin Donath](https://github.com/squidfunk)
The Material Design theme for MkDocs used by this documentation site. Provides dark/light mode, search, navigation tabs, code copy, and Mermaid diagram rendering.
License: MIT

**[PyMdown Extensions](https://facelessuser.github.io/pymdown-extensions/)**
Markdown extensions providing admonitions, tabbed content, syntax highlighting, and superfences (Mermaid support).
License: MIT

---

## Code quality

**[pre-commit](https://pre-commit.com/)**
Git hook framework for running linters and formatters automatically before each commit.
License: MIT

---

## Knowledge graph

**[graphify](https://github.com/graphify-dev/graphify)** *(if applicable)*
AST-based codebase knowledge graph used to map relationships between modules, functions, and classes. Enables AI agents to navigate the codebase without redundant file scanning.

---

## AI collaboration

This project is developed with assistance from AI coding agents:

- **[Claude](https://claude.ai/)** by Anthropic — primary AI development assistant
- **Gemini CLI** by Google — parallel AI agent for code review and suggestions
- **Codex** by OpenAI — parallel AI agent for implementation tasks

Agent coordination is managed via `shared_context.md` and per-agent instruction files (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`).

---

## License

BackDeezUp is released under the [MIT License](https://opensource.org/licenses/MIT).

```
MIT License

Copyright (c) 2026 devadalberto

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
