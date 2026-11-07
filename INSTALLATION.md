# Installation & Local LAN Deployment Guide (`INSTALLATION.md`)

## 1. System Requirements (Ubuntu Linux)

- **OS**: Ubuntu 22.04 LTS / 24.04 LTS (x86_64)
- **CPU**: 4+ threads recommended (runs on standard Intel/AMD CPUs; no NVIDIA GPU required)
- **RAM**: 4 GB minimum (8 GB recommended)
- **System Packages**:
  - `ffmpeg` and `ffprobe` (mandatory)
  - `python3` (`>= 3.10`) and `python3-venv`
  - `nodejs` (`>= 18`) and `npm`
  - Optional: `melt` (MLT framework), `shotcut`, `espeak-ng`

Verify installed binaries:
```bash
command -v ffmpeg ffprobe melt shotcut python3 node npm
```

---

## 2. Setup Instructions

```bash
cd /home/arslan-tariq/unico

# 1. Copy environment configuration
cp -n .env.example .env

# 2. Create and populate Python virtual environment
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. Install and build Frontend
cd frontend
npm install
npm run build
cd ..
```

---

## 3. Starting the Platform (Single Command)

Run the unified startup script:
```bash
./start.sh
```

This binds FastAPI and the background SQLite worker to `0.0.0.0:8000` and serves the compiled React studio UI at:
- **Local Machine**: `http://127.0.0.1:8000`
- **Local Area Network (LAN)**: `http://192.168.1.67:8000`

---

## 4. LAN Firewall Configuration (Ubuntu UFW)

If Ubuntu's `ufw` firewall is enabled and other devices on the same Wi-Fi/LAN cannot reach port `8000`, allow incoming traffic strictly from your local subnet (`192.168.1.0/24`):

```bash
sudo ufw allow from 192.168.1.0/24 to any port 8000 proto tcp comment "Unico LAN Studio"
```

Do not expose port `8000` on public internet interfaces without a TLS reverse proxy and enabling `UNICO_REQUIRE_AUTH=true` in `.env`.
