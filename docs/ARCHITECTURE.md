# Architecture Overview (v1.6.1)

## System Architecture

NPM Monitor has evolved into a highly modular, multi-container security platform. It separates high-load log processing from the user interface and AI-driven analysis to ensure maximum stability and responsiveness.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              NPM Monitor Stack                              │
│                                                                             │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐               │
│  │    npm-ui    │      │  npm-worker  │      │    npm-ai    │               │
│  │ (Dashboard & │      │(Log parsing, │      │ (Behavioral  │               │
│  │ Assistant)   │      │ Uptime, Ban) │      │ Analysis)    │               │
│  └──────┬───────┘      └──────┬───────┘      └──────┬───────┘               │
│         │                     │                     │                       │
│         └──────────┬──────────┴──────────┬──────────┘                       │
│                    │                     │                                  │
│         ┌──────────▼──────────┐      ┌───▼──────────────────────────┐       │
│         │   Shared Postgres   │      │      External Services       │       │
│         │ (Data, User, State) │      │ (OpenRouter, Cloudflare API) │       │
│         └──────────┬──────────┘      └──────────────────────────────┘       │
│                    │                                                        │
│         ┌──────────▼──────────┐                                             │
│         │      CrowdSec       │                                             │
│         │ (Threat Intel LAPI) │                                             │
│         └─────────────────────┘                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Description

### 1. Presentation Layer (`npm-ui`)
- **Framework**: Streamlit
- **Features**:
  - **Live Dashboard**: Real-time traffic insights and bandwidth monitoring.
  - **AI Assistant**: Conversational interface for log interrogation.
  - **3D Threat Map**: Animated pydeck-based visualization of global attacks.
  - **Security Management**: UI for unblocking IPs, ASN management, and user roles.

### 2. Processing Layer (`npm-worker`)
- **Responsibility**: The heart of the system's "Local Defense".
- **Tasks**:
  - **Log Sync**: Incrementally reads NPM logs and updates the database.
  - **Blocking Logic**: Evaluates thresholds (404s, Honey-Paths, Rate-Limits).
  - **Uptime Monitoring**: Periodically checks NPM hosts and SSL certificates.
  - **Firewall Sync**: Propagates bans to iptables/Cloudflare.

### 3. Intelligence Layer (`npm-ai`)
- **Responsibility**: "Cognitive Defense".
- **Tasks**:
  - **Auto-Analysis**: Monitors the blocklist and automatically fetches logs for new bans.
  - **OpenRouter Integration**: Sends context to LLMs (Gemini/DeepSeek) to determine attacker intent.
  - **Report Generation**: Stores detailed behavioral assessments in the database.

### 4. Security Layer (`crowdsec`)
- **Responsibility**: "Community Defense".
- **Tasks**:
  - Provides a local API (LAPI) for IP reputation checks.
  - Syncs with global blocklists.

### 5. Data Layer (`shared-postgres`)
- **Tables**:
  - `traffic`: Central log storage.
  - `blocklist`: Active bans (Local, ASN, Cloudflare).
  - `host_health`: Uptime and SSL history.
  - `ai_analysis`: Detailed behavioral reports.
  - `users`: Securely hashed credentials and roles.

## Security Model: Four Lines of Defense

1. **Local Defense (Worker)**: Immediate reaction to flooding, honey-paths, and brute force.
2. **Community Defense (CrowdSec)**: Blocks IPs known to the global security community.
3. **Cognitive Defense (AI)**: Understands and identifies zero-day or complex probing patterns.
4. **Edge Defense (Cloudflare)**: Prevents traffic from reaching the server at all.

## Performance Design
- **Connection Pooling**: Via `psycopg_pool` for efficient DB access across containers.
- **Batched I/O**: Logs are parsed in chunks and inserted in batches.
- **Asynchronous Checks**: Health checks and AI analysis run out-of-band to keep the UI smooth.
