# UpPing Backend

This is the FastAPI backend service for the UpPing monitoring system. It provides a REST API and WebSocket server for managing sites, executing background health checks, and streaming status updates.

## Local Development

1. Create a virtual environment: `python3 -m venv venv`
2. Activate it: `source venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Run the development server: `make dev`

## Deployment Guidelines

### Using Docker Compose

This project includes a `docker-compose.yml` configured for production-ready deployment.

**Steps to deploy:**
1. Clone this repository to your server.
2. In the `upping-be` directory, create a `.env` file (or set environment variables in your environment) with the following values:
   - `JWT_SECRET`: A strong random string for authentication.
   - `FRONTEND_URL`: The URL of your deployed frontend (e.g., `https://upping.yourdomain.com`). This is required for CORS.
   - `COOKIE_SECURE`: Set to `true` if you are running behind an HTTPS reverse proxy.
   - *(Optional)* SMTP settings for email alerts: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`.
3. Run the following command:
   ```bash
   make up
   ```
   *(Or simply `docker compose up -d`)*

### Using Portainer Stacks
If you are using Portainer, you can create a new Stack pointing to this repository:
1. Go to **Stacks** -> **Add stack**.
2. Choose **Repository** and provide your Git repository URL.
3. Set the **Compose path** to `upping-be/docker-compose.yml`.
4. Provide the Environment variables mentioned above.
5. Click **Deploy the stack**.

The backend will be available on port `8000` by default. You can access the automatic API documentation at `http://your-server-ip:8000/docs`.
