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

### 5) Conectar a API ao Supabase

A API lê `DATABASE_URL` (e demais variáveis) via `pydantic-settings`. O parser
aceita a string crua do Supabase (`postgresql://…`) e internamente converte
para o driver `psycopg` e acrescenta `sslmode=require` quando o host for
`*.supabase.co`.

1. No Supabase: **Project Settings → Database → Connection string** (aba
   *URI*). Use a *direct connection* (porta `5432`) para rodar Alembic e o
   servidor local; use o *transaction pooler* (porta `6543`) em ambientes
   serverless. Substitua `[YOUR-PASSWORD]` pela senha do Postgres.

2. Criar `.env` na raiz do monorepo (consumido pelo `docker-compose.yml`) a
   partir de `.env.example`:

   ```bash
   cp .env.example .env
   ```

   e, opcionalmente, `apps/api/.env` para rodar a API fora do Docker:

   ```bash
   cp apps/api/.env.example apps/api/.env
   ```

3. Preencher `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY` e, se
   necessário, `SUPABASE_SERVICE_ROLE_KEY` (obtido em **Project Settings →
   API**). Nunca comitar esses arquivos — já estão no `.gitignore`.

4. Rodar as migrações contra o Supabase:

   ```bash
   cd apps/api
   export DATABASE_URL="postgresql://postgres:<DB_PASSWORD>@db.<PROJECT_REF>.supabase.co:5432/postgres"
   alembic upgrade head
   ```

#### Supabase CLI (opcional)

O arquivo `supabase/config.toml` já está versionado com o `project_id`
correto. Para autenticar e vincular sua máquina ao projeto remoto:

```bash
supabase login
supabase link --project-ref paditvetvgtyriooiabs
```

A partir daí dá pra usar `supabase db pull`, `supabase db push`,
`supabase functions deploy`, etc.

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

## Deploy no Vercel

Este monorepo tem **duas** aplicações Next.js. Cada uma deve ser um **projeto
Vercel separado**, apontando para a pasta correspondente.

### Passo a passo

1. Em **Add New Project**, importe o repositório `gondimhugo/oficinapro`.
2. Em **Configure Project → Root Directory**, clique em *Edit* e selecione:
   - `apps/admin-web` para o painel interno, **ou**
   - `apps/client-portal` para o portal do cliente.
3. O framework será detectado como **Next.js** automaticamente. Os arquivos
   `apps/<app>/vercel.json` já definem:
   - `installCommand`: instala workspaces a partir da raiz do monorepo.
   - `buildCommand`: roda `npm run build` do workspace correto.
   - `outputDirectory`: `.next`.
4. Em **Environment Variables**, configure:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - (opcional, só server-side) `SUPABASE_SERVICE_ROLE_KEY`

   A integração Supabase ↔ Vercel preenche as duas primeiras automaticamente.
5. Clique em **Deploy**. Repita o processo criando um segundo projeto Vercel
   para o outro app.

### Observações

- `next.config.ts` usa `output: "standalone"` **apenas** quando
  `BUILD_STANDALONE=1` (configurado nos `Dockerfile`s). No Vercel, esse flag
  fica desligado, então o build usa a saída padrão esperada pela Vercel.
- `outputFileTracingRoot` aponta para a raiz do monorepo para que o Next
  encontre o `node_modules` com hoisting de workspaces.
- Branch de produção recomendada: `main`. Pull requests geram preview
  deployments automaticamente.
