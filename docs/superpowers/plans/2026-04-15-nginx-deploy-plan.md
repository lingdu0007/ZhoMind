# Frontend Deployment & Documentation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the latest frontend, deploy the static bundle behind Nginx (serving assets + proxying API to FastAPI on :8000), then produce a frontend design doc and backend API doc for downstream teams, finally assess whether these docs are sufficient for backend implementation.

**Architecture:** Vue 3 frontend compiled via Vite. Nginx serves `/` from `/var/www/zhomind-frontend` (or configurable root) and proxies `/api` routes to FastAPI (`http://127.0.0.1:8000`). Documentation stored under `docs/` within repo.

**Tech Stack:** Node 18+/npm, Vite build, Nginx (sites-available/sites-enabled), Markdown documentation.

---

## File Overview
- `frontend/` — Vue source; `npm run build` outputs `frontend/dist`.
- `/var/www/zhomind-frontend` — target static root (create).
- `/etc/nginx/sites-available/zhomind-frontend` — Nginx site config (symlink to sites-enabled).
- `docs/frontend-design.md` — new comprehensive design doc.
- `docs/backend-api.md` — new backend API spec summary.
- `docs/backend-api.md` + `docs/frontend-design.md` will be reviewed for completeness.

---

### Task 1: Build Latest Frontend Bundle

**Files/Dirs**
- `frontend/dist`

- [ ] **Step 1.1:** Install dependencies (ensures lock consistent).

```bash
cd frontend
npm install
```

- [ ] **Step 1.2:** Produce production build & verify output exists.

```bash
cd frontend
npm run build
test -d dist || { echo "dist missing"; exit 1; }
```

Expected: `dist/index.html` & `dist/assets/*`.

---

### Task 2: Deploy Bundle to Nginx

**Files/Dirs**
- `/var/www/zhomind-frontend`
- `/etc/nginx/sites-available/zhomind-frontend`
- `/etc/nginx/sites-enabled/zhomind-frontend`

- [ ] **Step 2.1:** Create deploy root & sync dist.

```bash
sudo mkdir -p /var/www/zhomind-frontend
sudo rsync -a --delete frontend/dist/ /var/www/zhomind-frontend/
sudo chown -R www-data:www-data /var/www/zhomind-frontend
```

- [ ] **Step 2.2:** Write Nginx server block.

`/etc/nginx/sites-available/zhomind-frontend`:

```nginx
server {
    listen 80;
    server_name _;

    root /var/www/zhomind-frontend;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

- [ ] **Step 2.3:** Enable site & reload.

```bash
sudo ln -sf /etc/nginx/sites-available/zhomind-frontend /etc/nginx/sites-enabled/zhomind-frontend
sudo nginx -t
sudo systemctl reload nginx
```

Confirm `curl -I http://localhost/` returns 200.

---

### Task 3: Author Frontend Design Document

**File:** `docs/frontend-design.md`

- [ ] **Step 3.1:** Create Markdown doc covering:
  - Overall layout (12-column grid, sidebar, cards, typography, palette).
  - Page-by-page details (Chat, Documents, Config) including components & states.
  - Interaction flows (session drawer, streaming indicators, upload workflow).
  - Deployment notes (static assets + API proxy expectations).

Sample structure:

```markdown
# ZhoMind Frontend Design
## Overview
## Visual System
## Architecture
## Page Specs
...
```

- [ ] **Step 3.2:** Proofread for completeness (no TODOs).

---

### Task 4: Author Backend API Document

**File:** `docs/backend-api.md`

- [ ] **Step 4.1:** Summarize available endpoints (auth, sessions, chat, documents) referencing OpenAPI. Include:
  - Base URL assumptions.
  - Request/response schema tables.
  - Authentication requirements.
  - Streaming `/chat/stream` contract (SSE event types).

- [ ] **Step 4.2:** Highlight dependencies (Milvus, queues) and any assumptions for backend devs.

---

### Task 5: Assess Documentation Sufficiency

- [ ] **Step 5.1:** Read both docs end-to-end.
- [ ] **Step 5.2:** Produce analysis (in final response) noting:
  - Whether frontend design doc fully informs future modifications.
  - Whether backend API doc covers data flows/backpressure/retry, etc.
  - Identify gaps (e.g., missing error codes, auth flows, SSE timing).

---

## Self-Review
- Ensure commands reference correct directories.
- Confirm docs paths exist under repo and no placeholders remain.
- Verify Nginx config handles `/api/` correctly; adjust prefix if backend expects `/`.
