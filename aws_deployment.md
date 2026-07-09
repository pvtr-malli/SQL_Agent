# SQL Agent — AWS Production Deployment Architecture

```mermaid
graph TB
    %% ── External ──────────────────────────────────────────────────────────────
    Client(["Client\n(Browser / API consumer)"])

    %% ── Edge / Ingress ────────────────────────────────────────────────────────
    subgraph Edge ["  Edge  "]
        R53["Route 53\nDNS"]
        ALB["Application Load Balancer\nHTTPS · health checks"]
    end

    %% ── Application Layer ─────────────────────────────────────────────────────
    subgraph AppLayer ["  Application Layer — ECS Fargate (Auto Scaling)  "]
        direction LR
        API1["SQL Agent\nFastAPI container\nTask 1"]
        API2["SQL Agent\nFastAPI container\nTask 2"]
        API3["SQL Agent\nFastAPI container\nTask N"]
    end

    %% ── Cache Layer ───────────────────────────────────────────────────────────
    subgraph CacheLayer ["  Cache Layer  "]
        Redis[("ElastiCache Redis\nSemantic query cache\nShared across all tasks")]
    end

    %% ── LLM Layer ─────────────────────────────────────────────────────────────
    subgraph LLMLayer ["  LLM Layer  "]
        direction LR
        LLM1["LLM Host\nEC2 GPU (g5 / p3)\nOllama · vLLM\nNode 1"]
        LLM2["LLM Host\nEC2 GPU\nNode 2"]
    end

    %% ── Storage Layer ─────────────────────────────────────────────────────────
    subgraph StorageLayer ["  Storage Layer  "]
        EFS[("Amazon EFS\nShared vector index\nMounted by all tasks")]
        S3[("Amazon S3\nSchema Excel source\nIndex snapshots · backups")]
    end

    %% ── Observability ─────────────────────────────────────────────────────────
    subgraph Observability ["  Observability  "]
        CW["CloudWatch\nLogs · Metrics · Alarms"]
        XRay["AWS X-Ray\nDistributed tracing"]
    end

    %% ── Security ──────────────────────────────────────────────────────────────
    subgraph Security ["  Security  "]
        SM["Secrets Manager\nAPI keys · env vars"]
        IAM["IAM Roles\nLeast-privilege task roles"]
    end

    %% ── CI/CD ─────────────────────────────────────────────────────────────────
    subgraph CICD ["  CI/CD  "]
        GH["GitHub Actions\nBuild · Test · Push image"]
        ECR["Amazon ECR\nContainer registry"]
        ECSdeploy["ECS Rolling Deploy\nZero-downtime update"]
    end

    %% ── Connections ───────────────────────────────────────────────────────────
    Client --> R53 --> ALB
    ALB --> API1 & API2 & API3

    API1 & API2 & API3 --> Redis
    API1 & API2 & API3 --> LLM1 & LLM2
    API1 & API2 & API3 --> EFS
    API1 & API2 & API3 --> CW
    API1 & API2 & API3 --> XRay
    API1 & API2 & API3 --> SM

    S3 --> EFS
    GH --> ECR --> ECSdeploy --> AppLayer
```

---

## Component Decisions

| Component | AWS Service | Why |
|---|---|---|
| DNS | Route 53 | Latency-based routing; health-check failover |
| Load balancer | ALB | Distributes requests across Fargate tasks; TLS termination; health checks |
| App runtime | ECS Fargate | No server management; scales tasks in/out automatically |
| Shared cache | ElastiCache Redis | Replaces file-backed cache; safe for multi-task concurrent writes; supports semantic cache via Redis VSS |
| LLM backend | EC2 GPU (g5/p3) | Self-hosted LLM (Ollama / vLLM); keeps data on-prem; swap for Bedrock if managed is preferred |
| Vector index | Amazon EFS | Shared read-only mount across all Fargate tasks; index rebuilt to S3 then synced |
| Schema source | Amazon S3 | Durable schema Excel storage; triggers re-index on upload via S3 event → Lambda |
| Logs & metrics | CloudWatch | Structured log ingestion from stdout; alarms on error rate / latency |
| Tracing | AWS X-Ray | Per-request latency breakdown across nodes |
| Secrets | Secrets Manager | LLM API keys, Redis credentials injected at task startup |
| Container registry | ECR | Private image storage; image scanning on push |
| CI/CD | GitHub Actions + ECR + ECS | Push to `main` → build image → push ECR → rolling deploy with zero downtime |

---

## Scaling Notes

- **App tier**: ECS Service Auto Scaling on CPU / request count — scale out task count, not instance size.
- **LLM tier**: GPU instances are expensive; scale with a target-tracking policy on GPU utilisation or queue depth. Consider a request queue (SQS) in front of the LLM pool for burst smoothing.
- **Cache**: Redis single-node for dev; Multi-AZ replication group for production.
- **Index rebuild**: S3 event → Lambda → trigger `/index` on one task; tasks reload index from EFS without restart.

---

## Network Layout

```mermaid
graph LR
    subgraph VPC ["  VPC (10.0.0.0/16)  "]
        subgraph PublicSubnets ["  Public Subnets (2 AZs)  "]
            ALB2["ALB"]
        end
        subgraph PrivateSubnets ["  Private Subnets (2 AZs)  "]
            Fargate["Fargate Tasks"]
            Redis2["ElastiCache"]
            GPU["GPU EC2 (LLM)"]
        end
    end
    Internet(["Internet"]) --> ALB2 --> Fargate
    Fargate --> Redis2
    Fargate --> GPU
    Fargate -->|"NAT Gateway"| Internet
```

All app, cache, and LLM resources live in **private subnets** — no public IPs. Only the ALB is public-facing. Fargate tasks reach the internet (for model downloads, S3) via a NAT Gateway.
- No sure about the network mapping thought, this is best possible I can think of.