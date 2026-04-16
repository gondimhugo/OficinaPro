# Oficina Pro Monorepo

Monorepo com três aplicações principais:

- `apps/admin-web`: painel interno para equipe operacional.
- `apps/client-portal`: portal para clientes.
- `apps/api`: backend FastAPI com SQLAlchemy e Alembic.

## Stack padronizada

### Frontend (admin-web e client-portal)

- Next.js (App Router)
- TypeScript
- Tailwind CSS
- Biblioteca de componentes UI (padrão `components/ui`, com base em primitives estilo shadcn/Radix)
- Lint/format: ESLint + Prettier
- Testes: Vitest

### Backend (`apps/api`)

- FastAPI
- SQLAlchemy 2
- Alembic
- Pydantic / pydantic-settings
- PostgreSQL
- Lint/format: Ruff + Black
- Testes: Pytest

## Pré-requisitos

- Node.js 20+
- Python 3.11+
- Docker + Docker Compose

## Setup local

### 1) Instalar dependências frontend (workspaces)

```bash
npm install
```

### 2) Rodar frontends em modo desenvolvimento

```bash
npm run dev --workspace=@oficina/admin-web
npm run dev --workspace=@oficina/client-portal
```

### 3) Setup backend

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .[dev]
```

### 4) Subir stack completa com Docker

```bash
docker compose up --build
```

Serviços:

- API: `http://localhost:8000`
- Admin Web: `http://localhost:3000`
- Client Portal: `http://localhost:3001`
- Postgres: `localhost:5432`

## Comandos de qualidade

### Frontend

```bash
npm run lint --workspaces
npm run format --workspaces
npm run test --workspaces
npm run build --workspaces
```

### Backend

```bash
cd apps/api
ruff check .
black --check .
pytest
```

## Migrações (Alembic)

```bash
cd apps/api
alembic upgrade head
```

## Convenções do repositório

1. **Estrutura por apps**: cada aplicação vive em `apps/<nome-app>`.
2. **Separação de responsabilidades**:
   - frontends com `app/`, `components/`, `lib/`, `tests/`;
   - backend com `app/`, `alembic/`, `tests/`.
3. **Qualidade obrigatória no CI**:
   - lint + testes + build frontend;
   - ruff + black + pytest backend.
4. **PRs pequenos e rastreáveis**:
   - descrever objetivo,
   - incluir comandos executados,
   - não misturar refactor amplo com feature sem necessidade.

## CI

Pipeline em `.github/workflows/ci.yml` com dois jobs:

- `frontend`: install, lint, test, build dos workspaces Next.js.
- `backend`: install, ruff, black e pytest da API.
