# SailPoint Homelab — URL Shortener

A minimal URL shortener service demonstrating a full GitOps pipeline: a containerized Flask app, a Helm chart for Kubernetes deployment, a GitHub Actions CI pipeline that builds and pushes images to GHCR, and an ArgoCD `Application` for continuous deployment.

## Architecture

```
Push to main ──> GitHub Actions ──> Build & push image to GHCR
                                          │
                                          ▼
   Git repo (Helm chart) <── watches ── ArgoCD ──> Kubernetes (minikube)
                                                        │
                                                        ▼
                                                 Flask app (Deployment + Service)
```

The flow: code is pushed to `main`, CI builds a Docker image and publishes it to GitHub Container Registry, and ArgoCD syncs the Helm chart from Git into the cluster.

## Repository Layout

| Path | Purpose |
|------|---------|
| `app.py` | Flask URL shortener (in-memory store, MD5-based slugs) |
| `requirements.txt` | Python dependencies (Flask, Gunicorn) |
| `Dockerfile` | Builds the app image; runs as non-root via Gunicorn on port 8080 |
| `url-shortner-chart/` | Helm chart (Deployment + Service templates, `values.yaml`) |
| `argocd/argocd-app.yaml` | ArgoCD `Application` manifest for GitOps sync |
| `.github/workflows/ci-pipeline.yaml` | CI: build and push image to GHCR on push to `main` |

## The Application

A small Flask service that stores URL mappings in memory.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check used by Kubernetes liveness/readiness probes |
| `/shorten` | POST | Body `{"url": "..."}` → returns `{"short_url": "..."}` (201) |
| `/<slug>` | GET | 302 redirect to the original URL, or 404 if unknown |
| `/stats` | GET | Returns the total number of stored links |

The base URL used in shortened links is read from the `BASE_URL` environment variable (injected by the Helm chart from `values.yaml`).

> **Note:** Storage is in-memory, so `replicaCount` is intentionally locked to `1`. Scaling beyond one replica without a shared datastore would cause inconsistent results (a slug created on one pod won't resolve on another).

## Prerequisites

Install the following locally:

- [Docker](https://docs.docker.com/get-docker/)
- [minikube](https://minikube.sigs.k8s.io/docs/start/)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [Helm](https://helm.sh/docs/intro/install/)
- [ArgoCD CLI](https://argo-cd.readthedocs.io/en/stable/cli_installation/) (optional, for the GitOps path)

---

## Running Locally with Docker

The fastest way to try the app without Kubernetes:

```bash
# Build
docker build -t url-shortener .

# Run
docker run -p 8080:8080 -e BASE_URL="http://localhost:8080" url-shortener

# Test
curl -X POST http://localhost:8080/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.sailpoint.com"}'
# → {"short_url": "http://localhost:8080/<slug>"}

curl -i http://localhost:8080/<slug>   # 302 redirect
curl http://localhost:8080/stats       # {"total_links": 1}
```

---

## Running on minikube with Helm

### 1. Start the cluster

```bash
minikube start
```

### 2. Deploy the chart

```bash
helm install url-shortener ./url-shortner-chart
```

Check the rollout:

```bash
kubectl get pods
kubectl get svc
```

### 3. Access the service

The Service type is `LoadBalancer`. On minikube, open a tunnel in a separate terminal:

```bash
minikube tunnel
```

Then get the external IP:

```bash
kubectl get svc url-shortener-service
```

Use the `EXTERNAL-IP` with port `8080`. Alternatively, skip the tunnel and port-forward:

```bash
kubectl port-forward svc/url-shortener-service 8080:8080
curl http://localhost:8080/health
```

### 4. Override values (optional)

```bash
helm upgrade url-shortener ./url-shortner-chart \
  --set image.tag=latest \
  --set env.baseUrl="http://localhost:8080"
```

### 5. Uninstall

```bash
helm uninstall url-shortener
```

---

## GitOps with ArgoCD

### 1. Install ArgoCD

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

Wait for the pods to be ready:

```bash
kubectl wait --for=condition=available --timeout=300s \
  deployment/argocd-server -n argocd
```

### 2. Access the ArgoCD UI

```bash
kubectl port-forward svc/argocd-server -n argocd 8081:443
```

Open https://localhost:8081. Get the initial admin password:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d; echo
```

Log in with username `admin`.

### 3. Apply the Application manifest

```bash
kubectl apply -f argocd/argocd-app.yaml
```

ArgoCD will create the `url-shortener` namespace, sync the Helm chart from the repo, and self-heal any manual drift (`prune` and `selfHeal` are enabled).

Check sync status:

```bash
kubectl get applications -n argocd
# or, with the CLI:
argocd app get url-shortener
```

> **⚠️ Path mismatch to fix before this works**
> The chart folder in the repo is named **`url-shortner-chart`** (missing the second "e"), but `argocd/argocd-app.yaml` points `spec.source.path` to **`url-shortener-chart`**. ArgoCD will fail to find the chart until these match. Either rename the folder to `url-shortener-chart` or update the `path` field in the manifest to `url-shortner-chart`.

---

## CI Pipeline

`.github/workflows/ci-pipeline.yaml` runs on every push to `main`:

1. Checks out the code.
2. Logs in to GitHub Container Registry (GHCR) using the built-in `GITHUB_TOKEN`.
3. Builds the Docker image and tags it with both `latest` and the full Git commit SHA (the SHA tag enables precise GitOps traceability).
4. Pushes the image to `ghcr.io/noa020604/sailpoint-homelab`.

To consume a specific build, set `image.tag` in `values.yaml` (or via `--set`) to the commit SHA tag.

---

## Configuration Reference

Key values in `url-shortner-chart/values.yaml`:

| Key | Default | Description |
|-----|---------|-------------|
| `replicaCount` | `1` | Locked to 1 due to in-memory storage |
| `image.repository` | `ghcr.io/noa020604/sailpoint-homelab` | Image source |
| `image.tag` | `latest` | Image tag (updated by CI to the commit SHA) |
| `image.pullPolicy` | `Always` | Ensures the newest image is pulled |
| `service.type` | `LoadBalancer` | Requires `minikube tunnel` locally |
| `service.port` | `8080` | External service port |
| `env.baseUrl` | `http://localhost:8080` | Base URL for generated short links |
| `resources.limits` | `200m` CPU / `256Mi` | Pod resource ceiling |
| `resources.requests` | `100m` CPU / `128Mi` | Pod resource reservation |

## Tech Stack

Python · Flask · Gunicorn · Docker · Kubernetes · Helm · ArgoCD · GitHub Actions · GHCR
