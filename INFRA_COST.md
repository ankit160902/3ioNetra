# 3ioNetra — Infrastructure Cost Breakdown

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Backend | FastAPI (Python 3.11) | API server, ML inference, RAG pipeline |
| Frontend | Next.js 14 (TypeScript) | Chat UI, SSR |
| Database | MongoDB Atlas | Users, conversations, auth tokens |
| Cache | Redis 7.2 (GCP Memorystore) | Sessions, RAG cache, response cache |
| Vector DB | Qdrant (self-hosted) | Scripture vector search |
| LLM | Google Gemini 2.5 Flash | Intent analysis, response generation |
| Embeddings | intfloat/multilingual-e5-large | 1024-dim multilingual embeddings (self-hosted) |
| Reranker | BAAI/bge-reranker-v2-m3 | Neural reranking (self-hosted) |
| Sparse Search | SPLADE | Keyword-level retrieval (self-hosted) |
| TTS | gTTS | Text-to-speech for verses |

---

## Resource Footprint

| Resource | Size | Notes |
|----------|------|-------|
| Embedding model | 1.3 GB | Loaded in RAM at startup |
| Reranker model | 0.5 GB | Lazy-loaded on first search |
| SPLADE model | 0.8 GB | Loaded if enabled |
| Embeddings data (embeddings.npy) | 377 MB | Memory-mapped (no heap cost) |
| Verse metadata (verses.json) | 108 MB | Loaded at startup |
| Docker image (full, with models baked) | ~3.0 GB | Production Dockerfile |
| Docker image (lite, no models) | ~800 MB | Dev Dockerfile.lite |
| Per session (Redis) | 4-8 KB | 60-min TTL |
| Per conversation (MongoDB) | 15-20 KB | Permanent storage |

**Minimum RAM for backend**: ~3.5 GB (embedding model + reranker + verse index + OS overhead)

---

## Environment 1: Local / Development

> Developer laptop running everything via Docker Compose. No cloud costs.

### Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 4 cores | 8 cores |
| RAM | 8 GB | 16 GB |
| Storage | 10 GB free | 20 GB free |
| GPU | Not required | Not required |
| OS | macOS / Linux / WSL2 | macOS / Linux |

### Services (all local via Docker Compose)

| Service | Image | Port | Memory Usage | Cost |
|---------|-------|------|-------------|------|
| Backend | Dockerfile.lite | 8080 | 2-3 GB | $0 |
| Frontend | next dev (hot reload) | 3000 | 200-400 MB | $0 |
| Redis | redis:alpine | 6379 | 50-100 MB | $0 |
| Qdrant | qdrant/qdrant:latest | 6333, 6334 | 500 MB-1 GB | $0 |
| MongoDB | Local or Atlas M0 (free) | 27017 | 200-500 MB | $0 |

### External Services

| Service | Tier | Cost |
|---------|------|------|
| Gemini API | Free tier (15 RPM, 1M tokens/min) | $0 |
| MongoDB Atlas | M0 free (512 MB) | $0 |
| Domain / SSL | Not needed (localhost) | $0 |
| Monitoring | Console logs | $0 |
| Vercel | Not needed (local dev server) | $0 |

### Concurrent Users

| Metric | Value |
|--------|-------|
| Max concurrent sessions | 5-10 |
| Suitable for | 1-2 developers testing |

### Monthly Cost

| Item | Cost (USD) |
|------|-----------|
| Gemini API (dev/testing) | $0-5 |
| Everything else | $0 |
| **Total** | **$0-5/mo** |

---

## Environment 2: Staging / UAT

> Lightweight cloud deployment for QA testing, client demos, and pre-production validation. Not designed for real user traffic.

### Compute — Backend

| Setting | Value | Notes |
|---------|-------|-------|
| Platform | GCP Cloud Run | Managed containers |
| Region | asia-south1 (Mumbai) | Low latency for India |
| vCPU | 2 | Sufficient for light testing |
| Memory | 4 GB | Models + overhead |
| Min instances | 0 | Scale to zero when idle |
| Max instances | 1 | Single instance for UAT |
| Concurrency | 40 | Requests per instance |
| Timeout | 300s | Per request |
| Docker image | Full (models baked in) | ~3 GB |
| Cold start | 10-15 seconds | Due to model loading |

| Cost Component | Calculation | Monthly (USD) |
|----------------|-------------|---------------|
| vCPU | 2 vCPU x ~$0.0000240/vCPU-sec x active hours | $15-40 |
| Memory | 4 GB x ~$0.0000025/GB-sec x active hours | $10-25 |
| Requests | ~10K requests/mo x $0.40/million | ~$0 |
| **Subtotal** | | **$25-65** |

> With min=0, you only pay when someone is actually using it. Expect 4-8 hours of active use per day during testing.

### Compute — Frontend

| Setting | Value | Cost (USD) |
|---------|-------|-----------|
| Platform | Vercel | Free/Hobby |
| Tier | Free | 100 GB bandwidth, unlimited deploys |
| Custom domain | Optional | Included |
| **Subtotal** | | **$0** |

### Database — MongoDB Atlas

| Setting | Value | Cost (USD) |
|---------|-------|-----------|
| Tier | M0 (free) or M2 (shared) | $0-9 |
| Storage | 512 MB (M0) or 2 GB (M2) | Included |
| Connections | Shared pool (max 500) | Included |
| Region | AWS Mumbai / GCP asia-south1 | Included |
| Backups | Daily (M2+) | Included |
| **Subtotal** | | **$0-9** |

### Cache — Redis

| Setting | Value | Cost (USD) |
|---------|-------|-----------|
| Provider | Upstash (serverless) or RedisLabs | $0-10 |
| Tier | Free (10K cmds/day) or Basic | - |
| Memory | 256 MB (sufficient for UAT) | Included |
| Region | asia-south1 | Included |
| **Subtotal** | | **$0-10** |

### Vector DB — Qdrant

| Setting | Value | Cost (USD) |
|---------|-------|-----------|
| Deployment | Embedded in backend container | $0 |
| Storage | Local filesystem (backed by Cloud Run ephemeral disk) | Included |
| Alternative | Qdrant Cloud free tier (1 GB) | $0 |
| **Subtotal** | | **$0** |

### LLM — Gemini API

| Setting | Value | Cost (USD) |
|---------|-------|-----------|
| Model | Gemini 2.5 Flash (primary) | Pay per token |
| Volume | ~500-2K conversations/month (testing) | - |
| Input tokens | ~$0.15 per 1M tokens | - |
| Output tokens | ~$0.60 per 1M tokens | - |
| Per conversation (avg) | ~$0.003 | - |
| Context caching (6h TTL) | 90% discount on cached input | - |
| **Subtotal** | | **$2-10** |

### Networking & Security

| Item | Details | Cost (USD) |
|------|---------|-----------|
| Domain (staging subdomain) | staging.3iosetu.com (existing domain) | $0 |
| SSL certificate | Auto-provisioned by Cloud Run / Vercel | $0 |
| VPC Connector | Not needed (use public Redis endpoint) | $0 |
| Load Balancer | Not needed (Cloud Run handles routing) | $0 |
| DNS | Cloudflare free tier | $0 |
| **Subtotal** | | **$0** |

### Storage & Registry

| Item | Details | Cost (USD) |
|------|---------|-----------|
| Artifact Registry | Docker images (<5 GB) | $0-2 |
| Cloud Storage | Not needed (data baked in image) | $0 |
| **Subtotal** | | **$0-2** |

### Monitoring & Logging

| Item | Details | Cost (USD) |
|------|---------|-----------|
| Cloud Run logs | Default stdout logging (included) | $0 |
| Cloud Monitoring | Basic metrics (included) | $0 |
| Error tracking | Application logs | $0 |
| Uptime checks | Not needed for staging | $0 |
| **Subtotal** | | **$0** |

### Concurrent Users

| Metric | Value |
|--------|-------|
| Max concurrent sessions | 20-40 |
| Max daily users | 50-200 |
| Suitable for | QA team, client demos, UAT |

### Staging Monthly Cost Summary

| Component | Monthly (USD) |
|-----------|---------------|
| Backend (Cloud Run, min=0, 1 max) | $25-65 |
| Frontend (Vercel Free) | $0 |
| MongoDB (Atlas M0/M2) | $0-9 |
| Redis (Upstash/RedisLabs free) | $0-10 |
| Gemini API (~1K convos) | $2-10 |
| Docker Registry | $0-2 |
| Domain / SSL / DNS | $0 |
| Monitoring | $0 |
| **Total** | **$27-96/mo** |

---

## Environment 3: Production

> Full deployment for real users. Designed for reliability, performance, auto-scaling, monitoring, and zero cold starts.

### Compute — Backend (Verified from GCP 2026-03-26)

| Setting | Value | Notes |
|---------|-------|-------|
| Service name | backend | GCP project: ionetra |
| Platform | GCP Cloud Run | Managed, auto-scaling |
| Region | europe-west1 (Belgium) | Current deployed region |
| vCPU | 8 | Handles concurrent RAG + LLM calls |
| Memory | 32 GB | ML models + high headroom for burst traffic |
| Min instances | 1 | Always warm, no cold starts |
| Max instances | 100 | Scale for peak traffic |
| Concurrency | 80 | Requests per instance (max 8,000 concurrent) |
| Timeout | 600s | Per request |
| Startup CPU boost | Enabled | Faster cold starts for new instances |
| Workers | 1 (uvicorn async) | Single-process, async concurrency |
| Docker image | Full (TRANSFORMERS_OFFLINE=1) | ~3 GB, no runtime downloads |
| Reranker | Disabled | Saves ~0.5 GB RAM |
| SPLADE | Disabled | Saves ~0.8 GB RAM |
| HyDE / Query Expansion | Disabled | Reduces latency, saves LLM calls |

| Cost Component | Calculation | Monthly (USD) |
|----------------|-------------|---------------|
| vCPU (min instance, always on) | 8 vCPU x 730 hrs x $0.0864/vCPU-hr | $505 |
| Memory (min instance, always on) | 32 GB x 730 hrs x $0.0090/GB-hr | $210 |
| vCPU (burst instances, ~20% of time) | 8 vCPU x ~146 hrs x $0.0864 | $101 |
| Memory (burst instances) | 32 GB x ~146 hrs x $0.0090 | $42 |
| Requests | ~500K/mo x $0.40/million | $0.20 |
| **Subtotal** | | **$715-858** |

> At scale (5K+ daily users), adding more max instances increases burst cost proportionally.

### Compute — Frontend

| Setting | Value | Cost (USD) |
|---------|-------|-----------|
| Platform | Vercel Pro | $20/mo |
| Bandwidth | 1 TB included | - |
| Edge functions | Included | - |
| Analytics | Included | - |
| Custom domain | 3io-netra.vercel.app + custom | Included |
| Team collaboration | Up to 10 members | Included |
| **Subtotal** | | **$20** |

### Database — MongoDB Atlas

| Setting | Value | Cost (USD) |
|---------|-------|-----------|
| Tier | M10 (dedicated) | $57 |
| vCPU | 2 cores | Included |
| RAM | 2 GB | Included |
| Storage | 10 GB (auto-scales) | Included |
| Backups | Continuous, point-in-time recovery | Included |
| Region | GCP asia-south1 | - |
| Connection pool | min=5, max=50 | - |
| Read preference | primaryPreferred | - |
| Collections | users, conversations, tokens, feedback, products | - |
| TTL indexes | tokens (30-day expiry), cost_logs (90-day) | Auto-cleanup |
| **Subtotal** | | **$57-100** |

> Scale to M30 ($500/mo) at 50K+ daily users or 50+ GB data.

### Cache — Redis (GCP Memorystore)

| Setting | Value | Cost (USD) |
|---------|-------|-----------|
| Provider | GCP Memorystore for Redis | $35-70 |
| Instance name | mitra-cache | - |
| Tier | BASIC (1 GB) | - |
| Redis version | 7.2 | - |
| Region | europe-west1-b | - |
| Access | Private IP (10.246.218.115) via VPC | - |
| Max connections | 20 (async pool) | - |
| DB | 0 (single database) | - |

| Cache Type | TTL | Estimated Size |
|-----------|-----|----------------|
| Sessions | 60 min | ~500 KB per 100 sessions |
| RAG search results | 1 hour | ~50-100 KB per entry |
| Response cache (semantic) | 6 hours | ~200 KB per entry |
| HyDE cache | 24 hours | ~50 KB per entry |
| Gemini context cache | 6 hours | System-level |
| **Total Redis usage** | | **200-800 MB** |

| **Subtotal** | | **$35-70** |

### Vector DB — Qdrant

| Setting | Value | Cost (USD) |
|---------|-------|-----------|
| Deployment | Self-hosted (embedded in backend) | $0 |
| Data | 96K vectors, 1024-dim, memory-mapped | Included in backend memory |
| Alternative (if needed) | Qdrant Cloud Starter (1 GB, 1M vectors) | $25/mo |
| **Subtotal** | | **$0** |

### LLM — Gemini API

| Model | Input (per 1M tokens) | Output (per 1M tokens) | Used For |
|-------|----------------------|----------------------|----------|
| Gemini 2.5 Flash (CURRENTLY DEPLOYED) | $0.15 | $0.60 | All calls — intent, response, everything |
| Gemini 2.5 Pro (available, not active) | $1.25 | $10.00 | Can enable later for complex guidance |

| Volume (conversations/month) | Flash Only (Current) | Flash + Pro (80/20, if enabled) |
|------------------------------|-----------|--------------------------|
| 5,000 | $15 | $55 |
| 10,000 | $30 | $110 |
| 25,000 | $75 | $275 |
| 50,000 | $150 | $550 |
| 100,000 | $300 | $1,100 |

> Context caching (6h TTL) gives ~90% discount on repeated system instruction tokens, reducing input cost significantly.

| **Subtotal (10K convos/mo estimate)** | | **$30-110** |

### Networking & Security

| Item | Details | Cost (USD) |
|------|---------|-----------|
| Custom domain | 3iomitra.3iosetu.com (existing) | $0 |
| Domain renewal | .com domain annual | $12/year = $1/mo |
| SSL certificate | Auto-provisioned (Cloud Run + Vercel) | $0 |
| Cloudflare DNS | Free plan (DNS + basic DDoS protection) | $0 |
| Cloudflare Pro (optional) | WAF, analytics, advanced DDoS | $20 |
| VPC Connector (mitra-connector) | e2-micro, 2-10 instances, private-ranges-only | $7-15 |
| Cloud Armor (optional) | Advanced DDoS / WAF for Cloud Run | $5-25 |
| Load Balancer | Not needed (Cloud Run has built-in LB) | $0 |
| Static IP (optional) | Cloud Run custom domain mapping | $0-3 |
| Egress (India region) | ~50 GB/mo outbound | $5-10 |
| **Subtotal** | | **$13-66** |

### Storage & Registry

| Item | Details | Cost (USD) |
|------|---------|-----------|
| Artifact Registry | Docker images (2-3 versions, ~10 GB) | $2-5 |
| Cloud Storage (backups) | Monthly MongoDB exports (~1 GB) | $0-2 |
| Log storage | Cloud Logging (first 50 GB free) | $0-5 |
| **Subtotal** | | **$2-12** |

### Monitoring, Logging & Alerts

| Item | Details | Cost (USD) |
|------|---------|-----------|
| Cloud Logging | Application logs via stdout | $0 (first 50 GB) |
| Cloud Monitoring | CPU, memory, request metrics | $0 (basic) |
| Uptime checks | Health endpoint monitoring (3 locations) | $0 (up to 10 checks) |
| Alert policies | Email/Slack on errors, latency spikes | $0 (up to 500 incidents) |
| Error Reporting | Automatic error grouping | $0 |
| Cloud Trace (optional) | Distributed tracing | $0-10 |
| External monitoring (optional) | UptimeRobot / Better Uptime | $0-7 |
| **Subtotal** | | **$0-17** |

### Backup & Disaster Recovery

| Item | Details | Cost (USD) |
|------|---------|-----------|
| MongoDB Atlas backups | Continuous + point-in-time (included in M10+) | $0 |
| Redis persistence | Memorystore BASIC (sessions are ephemeral) | $0 |
| Docker image versioning | 3 recent versions in Artifact Registry | Included |
| Scripture data | Static, baked into image (git versioned) | $0 |
| Manual DB export (monthly) | Cloud Storage bucket | $0-2 |
| **Subtotal** | | **$0-2** |

### CI/CD Pipeline

| Item | Details | Cost (USD) |
|------|---------|-----------|
| Cloud Build | Triggered on deploy (120 free min/day) | $0-5 |
| Vercel builds | Auto-deploy on git push (free tier) | $0 |
| GitHub Actions (optional) | Tests, linting (2000 free min/mo) | $0 |
| **Subtotal** | | **$0-5** |

### Secret Management

| Item | Details | Cost (USD) |
|------|---------|-----------|
| GCP Secret Manager | 4 secrets (Gemini, MongoDB, Redis, DB password) | $0 |
| Secret access operations | ~10K/mo (well within free tier of 10K) | $0 |
| **Subtotal** | | **$0** |

### Concurrent Users — Production

| Metric | Value |
|--------|-------|
| Per instance concurrency | 80 requests |
| Min instances (always warm) | 1 |
| Max instances | 10 |
| Max concurrent sessions | 800 (10 instances x 80) |
| Average response time | 2-4 seconds |
| Effective throughput | ~20-40 requests/second |
| Daily active users supported | 5,000-50,000 |
| Sessions per day (at 5K DAU) | ~15,000-25,000 |

### Production Monthly Cost Summary

| Component | Monthly (USD) |
|-----------|---------------|
| Backend (Cloud Run, 8 vCPU / 32 GB, min=1, max=100) | $715-858 |
| Frontend (Vercel Pro) | $20 |
| MongoDB Atlas (M10 dedicated) | $57-100 |
| Redis (GCP Memorystore 1 GB BASIC) | $35-70 |
| Gemini API (~10K convos, Flash only) | $30-50 |
| Networking (VPC connector, DNS, egress, Cloudflare) | $13-74 |
| Storage (Artifact Registry + 2 GCS buckets + logs) | $1-8 |
| Monitoring & Logging | $0-17 |
| Backup & DR | $0-2 |
| CI/CD (Cloud Build) | $0-5 |
| Secret Manager | $0 |
| **Total** | **$871-1,204/mo** |

---

## Gemini API Cost — Detailed Breakdown

Each conversation (avg 6 turns) involves:

| API Call | Model | Input Tokens | Output Tokens | Calls per Turn |
|----------|-------|-------------|--------------|----------------|
| Intent classification | Flash | ~300 | ~80 | 1 |
| Query expansion | Flash | ~200 | ~50 | 1 (if short query) |
| Response generation | Flash or Pro | ~1,500 | ~150 | 1 |
| HyDE generation | Flash | ~200 | ~100 | 1 (if enabled) |

**Per conversation (6 turns):**
- Flash only: ~13K input + ~2.3K output = **~$0.003**
- Flash + Pro mix (80/20): ~13K input + ~2.3K output = **~$0.011**

**Context caching saves ~60-70% on input costs** because the system instruction (~2K tokens) is cached for 6 hours across all requests.

---

## Side-by-Side Comparison

| Component | Local / Dev | Staging / UAT | Production |
|-----------|------------|---------------|------------|
| Backend (Cloud Run) | $0 (Docker) | $25-65 | $715-858 |
| Frontend | $0 (local) | $0 (Vercel Free) | $20 (Vercel Pro) |
| MongoDB | $0 (local/M0) | $0-9 (M0/M2) | $57-100 (M10) |
| Redis | $0 (Docker) | $0-10 (Upstash) | $35-70 (Memorystore) |
| Gemini API | $0-5 | $2-10 | $30-50 |
| Networking/DNS/SSL | $0 | $0 | $13-74 |
| Storage/Registry/GCS | $0 | $0-2 | $1-8 |
| Monitoring | $0 | $0 | $0-17 |
| Backup/DR | $0 | $0 | $0-2 |
| CI/CD | $0 | $0 | $0-5 |
| **Monthly Total** | **$0-5** | **$27-96** | **$871-1,204** |
| **Annual Total** | **$0-60** | **$324-1,152** | **$10,452-14,448** |
| Concurrent users | 5-10 | 20-40 | 8,000+ |
| Daily active users | 1-2 devs | 50-200 testers | 5,000-50,000 |

---

## Cost Optimization Tips

| Optimization | Savings | Trade-off |
|-------------|---------|-----------|
| Downsize Cloud Run to 4 vCPU / 8 GB | ~$400/mo | May hit memory limits under heavy load (reranker/SPLADE already disabled) |
| Set Cloud Run min=0 (prod) | ~$715/mo | 10-15s cold start on first request after idle |
| Reduce max instances from 100 to 10 | $0 (prevents surprise bills) | Limits max concurrent users to ~800 |
| Move region to asia-south1 | ~5-10% on egress | Lower latency for Indian users |
| Use Upstash Redis instead of Memorystore | $25-30/mo | Higher latency, but no VPC connector needed |
| Stay on MongoDB M0 until 512 MB full | $57/mo | No backups, shared cluster |
| Gemini Flash only (already done) | Already active | Pro not enabled currently |
| Reranker/SPLADE/HyDE disabled (already done) | Saves ~1.3 GB RAM | Already done in production |
| Use Dockerfile.lite for staging | Smaller image, faster deploy | Models download on cold start |

---

## Scaling Milestones

| Daily Active Users | Backend Config | MongoDB | Redis | Gemini API | Est. Monthly |
|-------------------|---------------|---------|-------|------------|-------------|
| <500 | 2 vCPU, 4 GB, min=0, max=2 | M0 (free) | Upstash free | Flash only | $30-80 |
| 500-2,000 | 4 vCPU, 8 GB, min=1, max=4 | M2 ($9) | Memorystore 1 GB | Flash only | $250-500 |
| 2,000-10,000 (CURRENT) | 8 vCPU, 32 GB, min=1, max=100 | M10 ($57) | Memorystore 1 GB | Flash only | $871-1,204 |
| 10,000-50,000 | 8 vCPU, 32 GB, min=2, max=100 | M30 ($500) | Memorystore 5 GB | Flash + Pro | $1,800-3,000 |
| 50,000+ | 8 vCPU, 32 GB, min=5, max=100+ | M50+ | Memorystore HA | Flash + Pro | $4,000-6,000+ |
