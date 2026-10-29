# Docker
```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose logs -f api
docker compose exec api sh
docker compose stop
docker compose down
```

# FastAPI con PostgreSQL y Redis en Ubuntu

Ejemplo para alumnos: crear usuarios, listar usuarios y observar una caché. La aplicación se despliega directamente en Ubuntu 24.04 con Python 3.12 y systemd. Docker se usa únicamente en GitHub Actions para PostgreSQL y Redis durante los tests.

El CD ejecuta `rsync`, `pip` y `systemctl` para instalar la aplicación nativamente. Reemplaza cualquier workflow de despliegue anterior por `.github/workflows/cd.yml` de este proyecto: debe quedar un solo workflow de CD activo.

## Funcionamiento

| Petición | Qué ocurre |
|---|---|
| `POST /users` | Guarda en PostgreSQL y elimina la caché de la lista |
| `GET /users` | Consulta Redis; si no hay caché, consulta PostgreSQL y guarda la lista por 60 segundos |
| `GET /health` | Comprueba que la API responde |

`GET /users` devuelve una lista directamente. La cabecera `X-Cache` muestra `MISS` si consultó PostgreSQL o `HIT` si leyó Redis. Si Redis falla, la API sigue consultando PostgreSQL.

## Archivos

```text
app/                    # Endpoints, validación, SQL y caché
tests/unit/             # Cuatro tests con mocks
tests/integration/      # Dos tests con PostgreSQL y Redis reales
.github/workflows/
  ci.yml                # Ruff y tests; bases en contenedores de servicio
  cd.yml                # Copiar código por SSH y reiniciar systemd
deploy/
  users-api.service     # Servicio de Ubuntu
  users-api.env.example # Conexiones y clave Redis por alumno
requirements.txt        # Dependencias de la aplicación
requirements-dev.txt    # Dependencias para revisar y probar
pyproject.toml          # Configuración de Ruff y pytest
```

En `app/`, lee en este orden: `schemas.py`, `database.py`, `service.py` y `main.py`. `config.py` obtiene las variables de entorno. No hay ORM ni un framework de migraciones.

## 1. Preparar PostgreSQL y Redis

Ambos servicios deben estar instalados, localmente o en otros servidores accesibles. Cada alumno debe usar su propia base PostgreSQL y su propia `CACHE_KEY` si comparten Redis.

Si la base y el usuario aún no existen, un administrador puede ejecutar en PostgreSQL:

```sql
CREATE USER app_user WITH PASSWORD 'CAMBIA_ESTA_CLAVE';
CREATE DATABASE app_db OWNER app_user;
```

Usa otros nombres para cada alumno. Si ya existen, omite esos comandos. El usuario de la aplicación debe poder crear la tabla en el esquema `public`, leerla y escribir en ella. Debe tener acceso de red y autorización en `pg_hba.conf`.

**No necesitas ejecutar `migrate`.** Al arrancar, `main.py` llama a `database.init_db()`, que ejecuta `CREATE TABLE IF NOT EXISTS users`. Crea la tabla vacía la primera vez y conserva los usuarios en los siguientes arranques. No crea la base ni el usuario PostgreSQL.

Si después cambias las columnas, `CREATE TABLE IF NOT EXISTS` no modifica una tabla existente: debes aplicar el cambio con SQL, por ejemplo `ALTER TABLE`. Para este ejercicio mantenemos una tabla fija.

## 2. Preparar el servidor Ubuntu una vez

Como administrador del servidor:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip rsync curl openssh-server
sudo adduser --disabled-password --gecos "" deploy
sudo install -d -o deploy -g deploy -m 755 /opt/users-api
sudo install -d -o deploy -g deploy -m 700 /home/deploy/.ssh
```

Si `deploy` ya existe, omite `adduser`. Sube los dos archivos de `deploy/` al servidor. Desde la carpeta que contiene esos archivos, instala la configuración:

```bash
sudo install -m 644 deploy/users-api.service /etc/systemd/system/users-api.service
sudo install -m 600 deploy/users-api.env.example /etc/users-api.env
sudo nano /etc/users-api.env
sudo systemctl daemon-reload
sudo systemctl enable users-api.service
```

Si aparece **`Unit file users-api.service does not exist`**, comprueba que ejecutaste `install` desde la raíz del proyecto con `ls -l deploy/users-api.service`. El CD solo copia `app/` y `requirements.txt`; los archivos de `deploy/` se preparan una vez en el servidor.

Si no tienes la carpeta `deploy/` en Ubuntu, crea el servicio directamente:

```bash
sudo tee /etc/systemd/system/users-api.service >/dev/null <<'EOF'
[Unit]
Description=FastAPI users API
After=network-online.target
Wants=network-online.target

[Service]
User=deploy
Group=deploy
WorkingDirectory=/opt/users-api
EnvironmentFile=/etc/users-api.env
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/opt/users-api/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Crear el archivo de variables solo si todavía no existe.
sudo test -e /etc/users-api.env || sudo install -m 600 /dev/null /etc/users-api.env
sudo nano /etc/users-api.env
sudo systemctl daemon-reload
sudo systemctl enable users-api.service
sudo systemctl cat users-api.service
```

En `/etc/users-api.env` deben estar estas variables, con los valores reales:

```ini
DATABASE_URL=postgresql://app_user:CAMBIA_ESTA_CLAVE@IP_POSTGRES:5432/app_db
REDIS_URL=redis://IP_REDIS:6379/0
CACHE_KEY=alumno01:users:all
```

`enable` configura el arranque automático, pero no inicia la API. El primer CD la iniciará después de instalar el código y las dependencias.

Edita las URLs con tus IP privadas, base, usuario y contraseña reales. Cambia `CACHE_KEY` por alumno: `alumno01:users:all`, `alumno02:users:all`, etc. Si la contraseña tiene caracteres especiales, codifícalos para la URL. Redis no lleva contraseña en este ejemplo.

systemd lee `/etc/users-api.env`; la aplicación no carga archivos `.env` automáticamente. El archivo pertenece a root y no se sube a GitHub. No arranques el servicio todavía: el primer CD creará el entorno virtual e instalará el código.

Con `sudo visudo -f /etc/sudoers.d/users-api-deploy`, agrega:

```sudoers
deploy ALL=(root) NOPASSWD: /usr/bin/systemctl restart users-api.service
```

## 3. Configurar SSH

En tu computadora, crea una clave exclusiva para el despliegue:

```bash
ssh-keygen -t ed25519 -C "lab_github" -f github-deploy -N ""
```

En el servidor, agrega el contenido de `github-deploy.pub` a `/home/deploy/.ssh/authorized_keys`, usando `sudo nano`. Luego:

```bash
sudo chown deploy:deploy /home/deploy/.ssh/authorized_keys
sudo chmod 600 /home/deploy/.ssh/authorized_keys
```

Prueba desde tu computadora: `ssh -i github-deploy deploy@IP_SERVIDOR`.

## 4. Configurar GitHub Actions

Sube el contenido del proyecto a la **raíz del repositorio**, incluyendo `.github`, y usa `main` como rama predeterminada. En **Settings > Secrets and variables > Actions**, crea:

| Secreto | Valor |
|---|---|
| `SERVER_HOST` | IP o DNS del servidor, sin `http://` |
| `SERVER_USER` | `deploy` |
| `SSH_PRIVATE_KEY` | Contenido completo del archivo `github-deploy` |
| `SERVER_KNOWN_HOSTS` | Host y clave SSH pública del servidor |

Para obtener la identidad del servidor, ejecuta en su consola `sudo cat /etc/ssh/ssh_host_ed25519_key.pub`. Copia el tipo y la clave, omite el comentario final y antepone el mismo host que usaste en `SERVER_HOST`:

```text
IP_SERVIDOR ssh-ed25519 CLAVE_PUBLICA_DEL_SERVIDOR
```

- **CI:** cada push y pull request ejecuta Ruff y seis tests. Python, PostgreSQL y Redis usan contenedores dentro del runner. Las conexiones usan los nombres `postgres` y `redis`; las credenciales de prueba se definen en `ci.yml`, sin secretos del servidor.
- **CD:** después de un CI exitoso de un push a `main`, sincroniza `app/` y copia `requirements.txt` a `/opt/users-api`, instala dependencias en `.venv`, reinicia `users-api.service` y consulta `/health`. Los pull requests no despliegan. Las variables de PostgreSQL y Redis se leen de `/etc/users-api.env`.

El runner debe alcanzar el servidor por SSH en el puerto 22 y disponer de SSH, SCP y rsync, disponibles en el runner Ubuntu de GitHub. Si solo tiene IP privada, usa un runner propio dentro de la VPC e instala esas herramientas allí. En GCP, la configuración SSH/OS Login debe permitir que `deploy` se autentique con `authorized_keys` para este ejemplo.

El firewall debe permitir TCP 8000 desde los alumnos, y la aplicación debe alcanzar PostgreSQL:5432 y Redis:6379. El workflow no cambia las credenciales ni la configuración del servicio.

## 5. Probar la API

Abre `http://IP_SERVIDOR:8000/docs`, o ejecuta:

```bash
curl -X POST http://IP_SERVIDOR:8000/users \
  -H 'Content-Type: application/json' \
  -d '{"name":"Ana","email":"ana@example.com"}'
curl -i http://IP_SERVIDOR:8000/users
curl -i http://IP_SERVIDOR:8000/users
```

La primera consulta muestra `MISS` y la segunda `HIT`. El cuerpo es:

```json
[{"id": 1, "name": "Ana", "email": "ana@example.com"}]
```

Un email repetido devuelve 409 y los datos inválidos, 422. Crea otro usuario y comprueba que la siguiente lectura muestre `MISS` con la lista actualizada.

Para revisar el servidor:

```bash
sudo systemctl status users-api.service
sudo journalctl -u users-api.service -n 50 --no-pager
```

## 6. Tests y ejecución manual

Los unitarios no necesitan PostgreSQL ni Redis:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
ruff check .
pytest tests/unit -q
```

Los tests de integración se ejecutan en CI. Para ejecutarlos manualmente, necesitas servicios de prueba dedicados, una base llamada `users_test` y Redis DB 15:

```bash
export DATABASE_URL='postgresql://USUARIO:CLAVE@IP_POSTGRES:5432/users_test'
export REDIS_URL='redis://IP_REDIS:6379/15'
export CACHE_KEY='tests:users:all'
pytest -q
```

Estos tests vacían la tabla de pruebas antes y después de cada caso. Usa exclusivamente servicios dedicados a tests.

Para iniciar la API manualmente en una computadora, instala `requirements.txt`, exporta `DATABASE_URL`, `REDIS_URL` y `CACHE_KEY` con los valores del laboratorio y ejecuta `uvicorn app.main:app --host 0.0.0.0 --port 8000`. Si antes ejecutaste tests, cambia las URLs para salir de los servicios de prueba.

## Alcance

Se mantiene una implementación corta, sin autenticación, paginación ni rollback automático. Actualizar y reiniciar puede interrumpir brevemente la API. La caché puede quedar desactualizada hasta que expire el TTL si falla la invalidación o hay consultas y escrituras concurrentes. `/health` comprueba que la API responde, no PostgreSQL ni Redis.

Referencias: [PostgreSQL CREATE TABLE](https://www.postgresql.org/docs/17/sql-createtable.html), [GitHub workflow_run](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run) y [FastAPI](https://fastapi.tiangolo.com/deployment/manually/).