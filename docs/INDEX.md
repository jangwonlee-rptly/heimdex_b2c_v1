# Heimdex B2C - Documentation Index

## 📖 Quick Navigation

### Getting Started (Read These First)
1. **[README.md](../README.md)** - Project overview, architecture, tech stack
2. **[guides/QUICKSTART.md](guides/QUICKSTART.md)** - One-command setup & implementation guide
3. **[reference/QUICK_REFERENCE.txt](reference/QUICK_REFERENCE.txt)** - Command cheatsheet

### Setup & Operations
- **[guides/SETUP_COMPLETE.md](guides/SETUP_COMPLETE.md)** - What's automated, how it works
- **[guides/TROUBLESHOOTING.md](guides/TROUBLESHOOTING.md)** - Common issues & solutions
- **[guides/FINAL_SUMMARY.md](guides/FINAL_SUMMARY.md)** - Post-setup summary

### Technical Reference
- **[AUTH_SUMMARY.md](AUTH_SUMMARY.md)** - Authentication quick reference ⭐ NEW
- **[models.md](models.md)** - ML models, licenses, download instructions
- **[reference/PROJECT_STATUS.md](reference/PROJECT_STATUS.md)** - Implementation progress (~35%)

### Development Logs
- **[../devlogs/2511102122.txt](../devlogs/2511102122.txt)** - Session 1: Initial setup
- **[../devlogs/2511102225.txt](../devlogs/2511102225.txt)** - Session 2: Automation & fixes
- **[../devlogs/2511110001.txt](../devlogs/2511110001.txt)** - Session 3: Supabase authentication ⭐ NEW
- **[DEVLOG_2025-11-11_supabase_integration.md](DEVLOG_2025-11-11_supabase_integration.md)** - Detailed Supabase integration guide

---

## 📚 Documentation Structure

```
heimdex_b2c/
├── README.md                    # Start here!
├── docs/
│   ├── INDEX.md                 # This file
│   │
│   ├── guides/                  # How-to guides
│   │   ├── QUICKSTART.md        # Getting started
│   │   ├── SETUP_COMPLETE.md    # Automation guide
│   │   ├── TROUBLESHOOTING.md   # Problem solving
│   │   └── FINAL_SUMMARY.md     # Post-setup summary
│   │
│   ├── reference/               # Reference material
│   │   ├── PROJECT_STATUS.md    # Progress tracking
│   │   └── QUICK_REFERENCE.txt  # Command cheatsheet
│   │
│   └── models.md                # ML models documentation
│
└── devlogs/                     # Session logs
    ├── 2511102122.txt           # Session 1
    └── 2511102225.txt           # Session 2
```

---

## 🎯 Documentation by Use Case

### "I want to start developing"
1. Read: [README.md](../README.md)
2. Run: `./start.sh` (see [QUICKSTART.md](guides/QUICKSTART.md))
3. Implement: Follow [QUICKSTART.md](guides/QUICKSTART.md) sections 4-5

### "Something broke"
1. Check: [TROUBLESHOOTING.md](guides/TROUBLESHOOTING.md)
2. View logs: `docker compose logs -f <service>`
3. Reset: `docker compose down -v && ./start.sh`

### "I want to deploy to production"
1. Read: [SETUP_COMPLETE.md](guides/SETUP_COMPLETE.md) deployment section
2. Run: `./deploy-gcp.sh`
3. Monitor: Check Cloud Run console

### "I want to understand the ML models"
1. Read: [models.md](models.md)
2. Download: `./scripts/download_models.sh`
3. Configure: Edit `.env.local` model settings

### "I want to see what's been done"
1. Read: [PROJECT_STATUS.md](reference/PROJECT_STATUS.md) (~25% complete)
2. Check: [devlogs/](../devlogs/) for detailed session logs
3. Review: Git commits (when available)

### "I need quick commands"
1. Print: `cat docs/reference/QUICK_REFERENCE.txt`
2. Bookmark: Common commands at bottom of this file

---

## 📋 Documentation Standards

All documentation follows these principles:

1. **Progressive Disclosure**
   - Quick start → Detailed guides → Reference
   - Newcomers get simple instructions
   - Experts get complete details

2. **Searchable by Symptom**
   - Troubleshooting organized by error message
   - Not "how to fix X" but "error: X"

3. **Code Examples**
   - Every guide has copy-paste examples
   - Real commands, not placeholders

4. **Maintained in Code**
   - Documentation as code
   - Updated with features
   - Version controlled

---

## 🔗 External Resources

- **Heimdex B2C Repository**: (when public)
- **Claude Code Docs**: https://docs.claude.com/en/docs/claude-code
- **Docker Compose Docs**: https://docs.docker.com/compose/
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **Next.js Docs**: https://nextjs.org/docs
- **Terraform Docs**: https://www.terraform.io/docs

---

## 📌 Quick Commands Reference

```bash
# Setup
./start.sh                          # Start everything (first run: 20-25 min)
docker compose ps                   # Check status
docker compose logs -f api          # View API logs

# Development
docker compose restart api          # Restart service
docker compose exec api bash        # Shell into container
docker compose exec db psql -U heimdex  # Database shell

# Troubleshooting
docker compose down                 # Stop all
docker compose down -v              # Stop and delete data
docker compose logs --tail=100 api  # Recent logs

# Deployment
./deploy-gcp.sh                     # Deploy to GCP

# Testing
curl http://localhost:8000/health   # Check API health
open http://localhost:8000/docs     # API documentation
```

---

## 📝 Contributing to Documentation

When adding documentation:

1. **Place Correctly**
   - Guides → `docs/guides/`
   - Reference → `docs/reference/`
   - Technical → `docs/`

2. **Update Index**
   - Add entry to this file
   - Update structure diagram

3. **Follow Format**
   - Markdown for text
   - Plain text for cheatsheets
   - Use tables, code blocks, emojis

4. **Keep Concise**
   - Aim for scannable content
   - Use headings liberally
   - Link don't duplicate

---

Last updated: 2025-11-10 22:25
