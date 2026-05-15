# SST Backend

API FastAPI para autenticacion, capacitaciones, checklists y chat.

## Variables de entorno

Copia `.env.example` a `.env` y ajusta al menos:

- `APP_ENV`
- `SECRET_KEY`
- `DATABASE_URL`
- `FRONTEND_URLS`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_DAYS`
- `DISABLE_2FA`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM`
- `SMTP_USE_TLS`
- `SMTP_USE_SSL`

En un entorno real, `SECRET_KEY` debe ser un valor propio y `DISABLE_2FA` no debe quedar en `true` salvo en una ventana controlada de pruebas.

## Desarrollo local

```bash
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8010
```

## Despliegue

Usa estos comandos en un servicio Python tipo Render:

- Build command: `pip install -r requirements.txt`
- Start command: `sh -c 'alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT'`

Antes de publicar, configura `SECRET_KEY`, `DATABASE_URL` y `FRONTEND_URLS` en el proveedor.

## Repo de despliegue

El backend puede publicarse desde este repositorio:

- `https://github.com/JoseAlexxander123/sstbackend.git`

## Render / UAT

El repo ya incluye `render.yaml` y `.python-version`.

Con eso puedes desplegarlo como Blueprint:

1. En Render, entra a `New > Blueprint`.
2. Conecta `https://github.com/JoseAlexxander123/sstbackend`.
3. Render detectara `render.yaml` y creara un Web Service `sst-backend-uat`.
4. Durante la creacion, pega tu `DATABASE_URL` de UAT en el campo solicitado.

Despues del primer deploy, revisa estas variables en el servicio:

- `APP_ENV`: debe quedar en `uat`.
- `DISABLE_2FA`: controla si el login salta OTP. En `true` no se enviara codigo; en `false`, UAT tambien exigira OTP real.
- `FRONTEND_URLS`: cambia el valor local por la URL real de tu frontend cuando lo publiques.
- `DATABASE_URL`: si tu base tambien esta en Render, conviene usar la URL interna de Postgres desde la pantalla `Info` de la base para menor latencia.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`: si no configuras SMTP, el login con OTP no podra enviar correos.
- `SMTP_USE_TLS` o `SMTP_USE_SSL`: ajustalos segun tu proveedor real. No actives ambos a la vez.
- `STORAGE_PROVIDER`, `SUPABASE_PROJECT_ID`, `SUPABASE_STORAGE_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`: son obligatorias para uploads reales.
- `SUPABASE_S3_DIRECT_HOST` o `SUPABASE_S3_ENDPOINT`: basta con una de las dos para habilitar storage.

Nota para plan `free`:

- Render no permite `preDeployCommand` en servicios gratis.
- Por eso este repo ejecuta `alembic upgrade head` dentro del `startCommand`.

Health check:

- `GET /health`
