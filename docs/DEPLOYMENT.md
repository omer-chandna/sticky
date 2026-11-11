# Deployment

Sticky’s web app and API deploy separately. You do not need a database or an object store.

## API

Build `services/api/Dockerfile` and run it with the port published.

```bash
docker build -t sticky-api services/api
docker run --rm -p 8000:8000 \
  -e STICKY_CORS_ORIGINS=https://your-web-origin \
  -e STICKY_DATA_DIR=/data \
  -v sticky-data:/data \
  sticky-api
```

Put the API on any container host (Fly.io, Render, a VPS, Cloud Run). Give it a disk or accept that the container’s `/data` is ephemeral. The TTL still applies.

Use HTTPS in production. Sticky does not terminate TLS itself.

Health check: `GET /api/health`.

## Web

### Vercel

1. Import the repository.
2. Set the root directory to `apps/web` if the importer requires an app directory. Because `@sticky/shared` lives outside that folder, it is simpler to set the project root to the repository and the install/build commands to:

   - Install: `npm ci`
   - Build: `npm run build --workspace @sticky/web`

3. Set `NEXT_PUBLIC_API_URL` to the public API origin, including `https://`.
4. Set `NEXT_TELEMETRY_DISABLED=1`.

The browser calls the API directly, so the API’s `STICKY_CORS_ORIGINS` must include the Vercel origin (and your custom domain).

### Node

`apps/web/Dockerfile` builds the Next.js standalone server. The browser still needs `NEXT_PUBLIC_API_URL` to be the API the user’s browser can reach, not an internal Docker hostname, unless you put both behind one origin and proxy `/api`.

## One machine

`docker compose up --build` runs both and publishes ports 3000 and 8000. That is the local-development deployment. It is also a reasonable single-computer install.

## What not to configure

Do not set an OpenAI key, a Stripe key, or a cloud bucket. Nothing in the default path reads them. Leave `STICKY_ENABLE_REMBG` false unless you have reviewed the checkpoint license and you are willing to download the weights on that server.
