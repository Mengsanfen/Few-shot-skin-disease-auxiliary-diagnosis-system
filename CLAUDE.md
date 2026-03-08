# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DreamMed Research (梦医智联) is a Django-based medical AI diagnosis platform. It provides medical imaging analysis, AI-powered diagnosis, and health information services.

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Database migrations
python manage.py makemigrations
python manage.py migrate

# Run development server
python manage.py runserver

# Run on specific port
python manage.py runserver 0.0.0.0:8000
```

## Architecture

### Django Project Structure
- `DM-AI/` - Django project settings (settings.py, urls.py, wsgi.py)
- `app01/` - Main application containing all business logic
- `manage.py` - Django management script

### Key Modules in `app01/`

**Views (`app01/views/`):**
- `agent.py` - AI diagnosis using DeepSeek API with LangChain, integrates medical knowledge base
- `chat.py` - AI chat interface
- `cell.py` - Cell detection using Landing AI object detection API
- `lung.py` - Lung image classification (cancer detection: normal, serrated, adenocarcinoma, adenoma)
- `mask.py` - Mask detection using YOLO
- `screen.py` - Screening dashboard
- `tips.py` - Health tips and medical information

**Models (`app01/models.py`):**
- `MedicalKnowledge` - Stores disease names, symptoms, check items, and advice for knowledge base search

**AI Integrations:**
- `app01/chat/sparkAPI.py` - Xunfei Spark (讯飞星火) WebSocket API client
- `app01/lung/model/` - Siamese network model for lung image analysis
- `app01/yolo/` - YOLOv5 integration for object detection

### External API Configuration

API keys are configured in:
- `DM-AI/settings.py` - Spark API config, object detection API
- `.env` - DeepSeek API key and base URL

**APIs used:**
- DeepSeek (via LangChain) - AI diagnosis chat
- Xunfei Spark (讯飞星火) - Alternative AI chat via WebSocket
- Landing AI - Object detection for cell analysis

### URL Routes

| Route | Feature |
|-------|---------|
| `/` | Entrance page |
| `/index/` | Main dashboard |
| `/agent/` | AI diagnosis with DeepSeek |
| `/ai-chat/` | AI chat interface |
| `/cell/` | Cell detection |
| `/mask/` | Mask/face detection |
| `/lung/` | Lung cancer classification |
| `/medical/` | Medical knowledge |
| `/health/` | Health tips |

### Frontend

- Templates in `app01/templates/`
- Static files in `app01/static/`
- Uses ECharts for data visualization in dashboard

## Database

Default: SQLite (`db.sqlite3`)

To switch to MySQL, update `DATABASES` in `DM-AI/settings.py`.