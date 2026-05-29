# Linker — URL Shortener Service

A cloud-native URL shortener built with Flask, containerized with Docker, deployed to Kubernetes via Helm, and managed through GitOps with Argo CD.

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

---

## Run Locally with Docker

**1. Build the image:**
```bash
docker build -t linker:local .
```

**2. Run the container:**
```bash
docker run -p 8080:8080 -e BASE_URL=http://localhost:8080 linker:local
```

**3. Test the endpoints:**
```bash
# Health check
curl http://localhost:8080/health

# Shorten a URL
curl -X POST http://localhost:8080/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.google.com"}'

# Follow the short URL (replace <slug> with the value returned above)
curl -L http://localhost:8080/<slug>

# Stats
curl http://localhost:8080/stats
```

---

## Bootstrap on a Local Cluster (kind or minikube)

### Prerequisites
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [Helm](https://helm.sh/docs/intro/install/)
- [kind](https://kind.sigs.k8s.io/) or [minikube](https://minikube.sigs.k8s.io/)

### 1. Start a local cluster

**kind:**
```bash
kind create cluster --name linker
```

**minikube:**
```bash
minikube start
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
minikube tunnel
# The service will be available at http://localhost:8080
```

**kind** (use port-forward):
```bash
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

Argo CD will now watch the `main` branch of this repository and automatically sync any changes to the cluster.

---

## Verify Everything End-to-End

```bash
# 1. Check pods are running
kubectl get pods -n url-shortener

# 2. Check the service
kubectl get svc -n url-shortener

# 3. Shorten a URL
curl -X POST http://localhost:8080/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.github.com"}'

# 4. Follow the redirect (replace <slug>)
curl -L http://localhost:8080/<slug>

# 5. Check stats
curl http://localhost:8080/stats

# 6. Verify Argo CD sync status
kubectl get application url-shortener -n argocd
```

---

## CI/CD Flow

Every push to `main` triggers the GitHub Actions pipeline which:
1. Builds the Docker image
2. Pushes it to GHCR with two tags: `latest` and the full Git commit SHA
3. Argo CD detects the updated manifests and syncs the cluster automatically

The SHA tag enables full traceability — you can always identify exactly which commit is running in the cluster.

---

## Trade-offs & Design Decisions

**Single replica:** The app uses in-memory storage (`store = {}`). Running multiple replicas would cause state drift — a slug created on replica A wouldn't be found by replica B. Scaling this properly would require an external store (e.g. Redis). For this assignment, `replicaCount: 1` is the correct and intentional choice.

**`BASE_URL` as an environment variable:** The base URL is injected at runtime via `values.yaml` and never baked into the image. For local testing, `http://localhost:8080` works with `minikube tunnel` or `port-forward`. For a real deployment, update `env.baseUrl` in `values.yaml` to match the external IP or domain.

**LoadBalancer service type:** Works out of the box with `minikube tunnel`. For kind, use `kubectl port-forward` instead, or switch `service.type` to `NodePort` in `values.yaml`.
