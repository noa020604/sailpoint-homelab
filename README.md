# URL Shortener Service (SailPoint DevOps Homelab)

A minimal URL shortener service demonstrating a full GitOps pipeline: 
a containerized Flask app, a Helm chart for Kubernetes deployment, 
a GitHub Actions CI pipeline that builds and pushes images to GHCR, and an ArgoCD 

---
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

---

## Project Structure

```
sailpoint-homelab/
├── .github/
│   └── workflows/
│       └── ci-pipeline.yaml       # GitHub Actions: build & push image on push to main
├── argocd/
│   └── argocd-app.yaml            # Argo CD Application manifest
├── url-shortener-chart/           # Helm chart
│   ├── templates/
│   │   ├── deployment.yaml
│   │   └── service.yaml
│   ├── Chart.yaml
│   └── values.yaml
├── app.py                         # Flask application
├── Dockerfile
└── requirements.txt
```
## Repository Layout

| Path | Purpose |
|------|---------|
| `app.py` | Flask URL shortener (in-memory store, MD5-based slugs) |
| `requirements.txt` | Python dependencies (Flask, Gunicorn) |
| `Dockerfile` | Builds the app image; runs as non-root via Gunicorn on port 8080 |
| `url-shortener-chart/` | Helm chart (Deployment + Service templates, `values.yaml`) |
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


## Run Locally with Docker

**1. Build the image:**
```bash
docker build -t url-shortener:latest .  
```

**2. Run the container:**
```bash
docker run -d -p 8080:8080 url-shortener:latest
```

**3. Test the endpoints:**
```bash
# Health check
# Linux/macOS
curl http://localhost:8080/health
# Windows (PowerShell)
curl.exe http://localhost:8080/health

# Shorten a URL
# Linux/macOS
curl -X POST http://localhost:8080/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.google.com"}'
# Windows (PowerShell)
curl.exe -i -X POST http://localhost:8080/shorten -H "Content-Type: application/json" -d '{\"url\": \"https://www.google.com\"}'

# Follow the short URL (replace <slug> with the value returned above)
# Linux/macOS
curl -i http://localhost:8080/<your-slug>
# Windows (PowerShell)
curl.exe -i http://localhost:8080/<your-slug>

# Stats
# Linux/macOS
curl http://localhost:8080/stats
# Windows (PowerShell)
curl.exe http://localhost:8080/stats
```

---

## Bootstrap on a Local Cluster (kind or minikube)

### Prerequisites
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [Helm](https://helm.sh/docs/intro/install/)
- [kind](https://kind.sigs.k8s.io/) or [minikube](https://minikube.sigs.k8s.io/)

### 1. Start a local cluster

**minikube:**
```bash
minikube start
```

**kind:**
```bash
kind create cluster --name url-shortener
```

### 2. Make the GHCR image public

By default, GitHub Container Registry packages are private. Before deploying, go to:

**GitHub → Your Profile → Packages → `sailpoint-homelab` → Package Settings → Change visibility → Public**

This allows Kubernetes to pull the image without credentials.

### 3. Deploy with Helm

```bash
helm install url-shortener ./url-shortener-chart
```

To override the base URL (e.g. after getting an external IP):
```bash
helm install url-shortener ./url-shortener-chart --set env.baseUrl=http://<EXTERNAL-IP>:8080
```

### 4. Access the service

**minikube:**
```bash
# Open a new terminal window
minikube tunnel
# The service will be available at http://localhost:8080
```

**kind** (use port-forward):
```bash
# Open a new terminal window
kubectl port-forward svc/url-shortener-service 8080:8080
```

---

## Install and Configure Argo CD

### 1. Install Argo CD
```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

### 2. Access the Argo CD UI
```bash
# Open a new terminal window
kubectl port-forward svc/argocd-server -n argocd 8081:443
```
Open https://localhost:8081 in your browser.

### 3. Get the initial admin password
```bash
kubectl get secret argocd-initial-admin-secret -n argocd \
  -o jsonpath="{.data.password}" | base64 -d
```
Login with username `admin` and the password above.

### 4. Apply the Argo CD Application manifest
```bash
kubectl apply -f argocd/argocd-app.yaml
```
> **Note:** The argocd-app.yaml manifest is configured to automatically create the required namespace upon synchronization. If you prefer manual control, ensure the url-shortener namespace exists before applying.

Argo CD will now watch the `main` branch of this repository and automatically sync any changes to the cluster.

---

## Verify Everything End-to-End

```bash
# Check that pods and services are running
kubectl get pods -n url-shortener
kubectl get svc -n url-shortener

# Verify Argo CD sync status
kubectl get application url-shortener -n argocd
```
### Functional Verification

Now that the infrastructure is confirmed to be running, verify that the application logic works correctly within the cluster. You can run the same functional tests described in the Run Locally with Docker section to ensure your endpoints (Health, Shorten, Redirect, Stats) are behaving as expected.

---

## CI/CD Flow

The project follows a GitOps methodology, separating the artifact build process from the cluster deployment:


1. **Continuous Integration (CI):** Every `push` to the `main` branch triggers the GitHub Actions pipeline. It builds the Docker image and pushes it to GHCR with two tags: `latest` and the unique `commit SHA`.
2. **GitOps Synchronization:** The deployment is managed by Argo CD, which continuously monitors the Helm chart configurations in this repository.
3. **Rollout Mechanism:** To update the app, just update the image.tag in your values.yaml to the latest commit SHA and push the change to Git. Argo CD will immediately spot the difference, sync the cluster, and handle the Rolling Update for you automatically.

The SHA tag enables full traceability — you can always identify exactly which commit is running in the cluster.

---

## Trade-offs & Design Decisions

**Single replica:** The app uses in-memory storage (`store = {}`). Running multiple replicas would cause state drift — a slug created on replica A wouldn't be found by replica B. Scaling this properly would require an external store (e.g. Redis). For this assignment, `replicaCount: 1` is the correct and intentional choice.

**`BASE_URL` as an environment variable:** The base URL is injected at runtime via `values.yaml` and never baked into the image. For local testing, `http://localhost:8080` works with `minikube tunnel` or `port-forward`. For a real deployment, update `env.baseUrl` in `values.yaml` to match the external IP or domain.

**Service Exposure:** The service is currently set to `LoadBalancer` for ease of local testing with `minikube tunnel`. In a production environment, this would be changed to `ClusterIP` and exposed via an `Ingress` controller to handle routing, SSL termination, and host-based pathing.

**Image Tagging & Rolling Updates**: For this lab, I am using the `latest tag` combined with `imagePullPolicy: Always` to allow for rapid testing. While this triggers a pull of the newest image upon `pod restart`, it creates a **configuration drift** where the cluster state deviates from Git. In a production-grade `GitOps workflow`, I would use **immutable tags** (like the commit SHA) and update the `values.yaml` in Git for every deployment. This ensures that the `Git repository` remains the **Single Source of Truth** and enables safe, controlled **Rolling Updates** managed by `Argo CD`.