Here’s a **complete Project Requirement Documentation (PRD)** for the **B2C version of Heimdex**, aligned with your cost-efficient, open-source-first, vector-native architecture vision. It’s structured like a formal internal specification — meant to align engineers, designers, and stakeholders before development.

---

# **Heimdex B2C – Project Requirement Document (PRD)**

**Version:** 1.0
**Date:** November 2025
**Owner:** Heimdex Founding Team
**Stage:** MVP → Public Beta (B2C)

---

## **1. Executive Summary**

Heimdex B2C is a **consumer-facing video intelligence platform** that enables individuals to **search their own videos semantically** — by meaning, action, or person — without uploading their private content to the cloud. Users can upload personal or creative videos and find exact moments like “me crying,” “Minji waving,” or “red car at night” using natural language.

Unlike enterprise Heimdex (which connects to Google Drive for labels and production companies), the B2C version targets **creators, vloggers, and consumers** who want to index and search their personal media easily and privately using **fully open-source AI models** that run in the backend (and optionally offline).

The goal of the MVP is to provide:

* Fast, accurate indexing for short videos (≤ 10 minutes).
* High-recall multimodal search (speech + vision + faces).
* Cloud-deployable and cost-efficient infra built with open weights (Whisper, CLIP, BGE-M3, etc.).

---

## **2. Target Users**

| Segment                  | Description                             | Core Needs                                   |
| ------------------------ | --------------------------------------- | -------------------------------------------- |
| Content creators         | YouTubers, vloggers, short-form editors | Fast indexing, scene search, face tagging    |
| Students / Researchers   | Record interviews, lectures             | Keyword and semantic retrieval               |
| K-pop fans / archivists  | Fan-cam collectors, fancams, etc.       | “Find Minji smiling,” “on stage,” “in Busan” |
| Journalists / Podcasters | Interview archives                      | Search by topic, emotion, or speaker         |
| General public           | Smartphone users with video folders     | Private, automatic video organization        |

---

## **3. Business Goals**

1. **Launch a scalable consumer MVP** to validate semantic video search demand.
2. **Achieve < $0.05 cost per indexed minute** via open models and local GPU.
3. Support **1000 DAU with sub-3s search latency** using pgvector on a single Postgres instance.
4. **Upgrade path** toward Heimdex Pro (paid tier for longer videos, faster GPU queue).
5. Build foundational architecture shared with enterprise Heimdex (same core pipeline, different auth/storage).

---

## **4. Product Scope**

### **In-Scope (MVP)**

✅ Email/password auth (JWT)
✅ Upload up to 10-minute videos (≤1 GB)
✅ Automatic indexing: ASR → scene → embedding → sidecar
✅ Search by:

* Transcript text
* Semantic meaning (“man crying”)
* Person + action (“Minji crying”)
  ✅ Preview via signed URL
  ✅ Usage limits (free tier: 3 uploads/day)
  ✅ Basic metrics dashboard (uploads, storage used)
  ✅ Admin panel for monitoring and deletion

### **Out-of-Scope (Future)**

❌ Payments/subscriptions
❌ Translation or diarization
❌ Shared projects / collaboration
❌ Mobile native app (web only first)

---

## **5. Functional Requirements**

### **5.1 Authentication**

* Email/password registration + magic link login
* Argon2id hashing
* JWT access (15 min) + refresh (7 days)
* Forgot password flow
* Email verification

### **5.2 Upload & Validation**

* Upload limit: ≤ 1 GB, ≤ 600 seconds (server-validated)
* Client precheck using MediaSource metadata
* ffprobe duration verification post-upload
* Background job enqueue after upload completion

### **5.3 Indexing Pipeline**

1. **Audio extraction:** ffmpeg → 16 kHz mono WAV.
2. **ASR (Whisper small/medium):** Korean → transcript segments.
3. **Scene detection:** PySceneDetect (histogram-based).
4. **Alignment:** Match transcript segments with scenes.
5. **Text embedding:** BGE-M3 (FlagEmbedding).
6. **Vision embedding:** OpenCLIP (ViT-B/32) mean-pooled scene frames.
7. **Tagging (zero-shot):** Classify tags (“crying,” “car,” “on stage,” etc.) using CLIP text-image similarity.
8. **Face recognition:** RetinaFace + AdaFace (if enrolled).
9. **Sidecar build:** Store per-scene JSON with transcript, embeddings, tags.

All steps are idempotent and resumable.

### **5.4 Search**

* Hybrid scoring:

  ```
  score = 0.5*text + 0.35*vision + 0.15*tags (+person_boost)
  ```
* Full-text: PGroonga for Korean tokenization.
* Vector: pgvector for text & vision embeddings.
* Filters: duration, date, tag presence.
* Results: scene grid (thumbnail, transcript snippet, score).
* Scene detail: full transcript + signed playback from timestamp.

### **5.5 Face Enrollment**

* Upload 3–10 face images.
* Compute AdaFace embedding → store in `face_profiles`.
* Person matching: if ≥ 40 % of scene frames match threshold, link scene to person.

### **5.6 Playback**

* Signed URL (≤ 10 min TTL).
* Seek to `scene.start_s`.
* No server-side streaming.

---

## **6. Non-Functional Requirements**

| Category            | Target                     | Rationale                  |
| ------------------- | -------------------------- | -------------------------- |
| **Latency**         | Search < 2 s (P95)         | Real-time user experience  |
| **Throughput**      | ≥ 20 jobs/min per GPU node | Efficient indexing         |
| **Availability**    | 99.5 %                     | SaaS baseline              |
| **Scalability**     | Horizontal workers         | Future multi-tenant growth |
| **Cost**            | <$0.05/minute video        | Feasible consumer pricing  |
| **Security**        | OWASP ASVS L2              | Consumer data protection   |
| **Privacy**         | No video stored post-index | Trust and compliance       |
| **Localization**    | Korean (v0)                | Domestic launch focus      |
| **Portability**     | Cloud-agnostic Terraform   | Minimize lock-in           |
| **Maintainability** | < 1 hr MTTR                | Lean ops team              |

---

## **7. System Architecture Overview**

**Core Services**

1. **API Service** – FastAPI
2. **Worker Service** – Dramatiq background jobs
3. **Web Frontend** – Next.js + Tailwind
4. **Database** – Postgres 16 + pgvector + PGroonga
5. **Cache** – Redis
6. **Object Storage** – MinIO (local) / GCS (prod)

**Pipeline Flow**

```
Upload → Validation → Queue(Job)
 → [Audio Extract → ASR → Scene → Embed(Text,Vision) → Tag → Face] 
 → Sidecar → DB + Storage → Search Index
```

**Infra-as-Code**

* Terraform modules for all cloud resources (network, DB, storage, monitoring).
* Docker Compose for local development.
* CI/CD via GitHub Actions → Artifact Registry → Cloud Run deploy.

---

## **8. Open-Source Model Stack**

| Task             | Model                  | License    | Size   | Notes               |
| ---------------- | ---------------------- | ---------- | ------ | ------------------- |
| ASR              | Whisper (small/medium) | MIT        | 1–2 GB | Korean robust       |
| ASR alignment    | WhisperX               | MIT        | 1 GB   | optional speedup    |
| Text embedding   | BGE-M3                 | MIT        | ~1 GB  | multilingual strong |
| Vision embedding | OpenCLIP (ViT-B/32)    | Open       | 600 MB | fast & light        |
| Vision (alt)     | SigLIP-2               | Apache-2.0 | 1 GB   | better multilingual |
| Face detect      | RetinaFace             | MIT        | 150 MB | lightweight         |
| Face embed       | AdaFace                | MIT        | 100 MB | modern, accurate    |
| Scene detect     | PySceneDetect          | BSD        | –      | frame histogram     |
| Tokenizer        | PGroonga               | BSD        | –      | Korean FTS          |
| Vector DB        | pgvector               | MIT        | –      | native to Postgres  |

---

## **9. Security & Compliance**

* **Encryption:** AES-256 at rest; TLS 1.3 in transit.
* **Secrets:** GCP Secret Manager / .env.local (dev).
* **Auth:** Argon2id hashing, short-lived JWTs.
* **RBAC:** user, admin roles.
* **Audit:** every job logged with user_id.
* **Data isolation:** per-user storage buckets.
* **Deletion:** on request, purge all derived data + vectors.
* **Compliance targets:** PIPA (KR), GDPR (metadata only).

---

## **10. Infrastructure Requirements**

| Environment       | Components                                                                    | Notes                         |
| ----------------- | ----------------------------------------------------------------------------- | ----------------------------- |
| **Local Dev**     | Docker Compose: API, Worker, DB (pgvector + PGroonga), Redis, MinIO, Web      | All models downloaded locally |
| **Staging (GCP)** | Cloud Run (API, Worker), Cloud SQL, GCS, Pub/Sub, Memorystore, Secret Manager | Single region (Seoul)         |
| **Prod**          | Multi-region Cloud Run, daily backups, budget alerts                          | SLA 99.5 %                    |

---

## **11. Observability**

* Prometheus metrics: request latency, job duration, queue depth, embedding throughput, GPU utilization.
* OpenTelemetry tracing for API and worker spans.
* Grafana dashboards (SLOs & budgets).
* Alerting: latency > 5 s, job fail > 10 %, cost > 80 % budget.
* Log retention: 30 days (app), 365 days (audit).

---

## **12. UX / UI Requirements**

| Page           | Description                   | Key Features                               |
| -------------- | ----------------------------- | ------------------------------------------ |
| Landing        | Short explanation + login CTA | Hero section + preview gif                 |
| Login/Register | Auth flows                    | Email/password, magic link                 |
| Upload         | Drag-and-drop + limits        | Progress bar, ffprobe validation           |
| Library        | All user uploads              | State badges: uploading/processing/indexed |
| Search         | Input + grid view             | Transcript snippets, filters               |
| Scene Detail   | Scene transcript + tags       | Highlighted search terms + signed URL      |
| Profile        | Face enrollment               | Upload photos, name label                  |
| Dashboard      | Usage stats                   | Upload count, minutes indexed              |

Visual design: clean, minimalist, neutral color palette (white / gray / teal accents).

---

## **13. Success Metrics**

| Metric                  | Goal                   | Measurement        |
| ----------------------- | ---------------------- | ------------------ |
| Upload → Indexed time   | < 5 min (10-min video) | Pipeline logs      |
| Search latency (P95)    | < 2 s                  | Prometheus         |
| Search recall @10       | ≥ 0.85                 | Internal benchmark |
| Active users (30 d)     | ≥ 500                  | Analytics          |
| Cost per minute indexed | ≤ $0.05                | Billing metrics    |
| Crash-free rate         | ≥ 99.5 %               | Sentry logs        |

---

## **14. Roadmap**

| Phase           | Timeframe | Milestone                                               |
| --------------- | --------- | ------------------------------------------------------- |
| **MVP (Alpha)** | 0–3 mo    | Upload → Index → Search; Text + Vision + Person queries |
| **Beta**        | 3–6 mo    | Face search polish; Metrics dashboard; Improved UI      |
| **Pro Launch**  | 6–12 mo   | Paid plans, longer videos, multi-language ASR           |
| **v2.0**        | 12 mo +   | Offline desktop app; global multi-tenant cloud          |

---

## **15. Risks & Mitigations**

| Risk                             | Mitigation                                                   |
| -------------------------------- | ------------------------------------------------------------ |
| GPU cost spikes                  | Run models on CPU fallback or local GPU node                 |
| ASR inaccuracy (Korean dialects) | Fine-tune WhisperX KR subset                                 |
| PGvector scale limits            | Shard by user id; Qdrant adapter ready                       |
| Face model licensing             | Use AdaFace (MIT) only; verify datasets legality             |
| Large uploads                    | Hard-limit 1 GB; server validation via ffprobe               |
| Cloud egress cost                | Keep processing inside region; no video download post-upload |
| Privacy concerns                 | Delete raw video after index; store metadata only            |

---

## **16. Deliverables**

1. **Backend API (FastAPI)** with fully documented OpenAPI spec.
2. **Worker pipeline (Dramatiq)** with Whisper + CLIP + BGE-M3 integration.
3. **Frontend (Next.js)** with upload, search, and playback UI.
4. **Terraform IaC** for dev/staging/prod.
5. **Docker Compose** local setup.
6. **Monitoring Dashboard (Grafana + Prometheus)**.
7. **Comprehensive test suite (Pytest)** > 90 % coverage core.
8. **Deployment guide + README** with model download automation.

---

## **17. Acceptance Criteria**

✅ User can register, log in, and upload ≤ 10-minute video.
✅ Upload validated (size/duration).
✅ Indexing completes with sidecar in ≤ 5 minutes.
✅ Search by:

* Free text over transcript.
* Visual phrase (“man crying”).
* Person + action (“Minji crying”).
  ✅ Search returns relevant scene(s) < 2 s.
  ✅ Signed playback URL works and expires after TTL.
  ✅ Logs, metrics, alerts functional.
  ✅ All models loaded locally with open licenses.

---

## **18. Future Enhancements**

* Support for **English & Japanese** ASR/embeddings.
* **Diarization & speaker labeling.**
* **Temporal summarization** (scene descriptions).
* **Mobile app / PWA** for smartphone ingestion.
* **Social “shared search spaces.”**
* **Paid Pro tier** (longer video + faster GPU queue + analytics).

---

## **19. References**

* Whisper: [https://github.com/openai/whisper](https://github.com/openai/whisper)
* WhisperX: [https://github.com/m-bain/whisperX](https://github.com/m-bain/whisperX)
* BGE-M3: [https://huggingface.co/BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3)
* OpenCLIP: [https://github.com/mlfoundations/open_clip](https://github.com/mlfoundations/open_clip)
* SigLIP-2: [https://github.com/google-research/siglip](https://github.com/google-research/siglip)
* AdaFace: [https://github.com/mk-minchul/AdaFace](https://github.com/mk-minchul/AdaFace)
* RetinaFace: [https://github.com/serengil/retinaface](https://github.com/serengil/retinaface)
* PySceneDetect: [https://pyscenedetect.readthedocs.io/](https://pyscenedetect.readthedocs.io/)
* pgvector: [https://github.com/pgvector/pgvector](https://github.com/pgvector/pgvector)
* PGroonga: [https://pgroonga.github.io/](https://pgroonga.github.io/)

---

**End of Document — Heimdex B2C PRD v1.0**
