# YAXIN AI

**AI-Powered Voice Assistant & Digital Life Agent (Hackathon MVP)**

**Version:** 1.0 · **Date:** 8 November 2026  
**Primary Language:** Azerbaijani (`az-AZ`)  
**Architecture:** Local-first Contacts · Human-in-the-Loop Confirmation · Modular Monolith (FastAPI + LangGraph + Flutter)

---

## 1. Layihə Haqqında (Project Overview)

**YAXIN AI** — istifadəçinin Azərbaycan dilində verdiyi səsli və ya yazılı əmrləri anlayan, onları strukturlaşdıran və icazə verilən rəqəmsal əməliyyatlara çevirən **AI Agent** sistemidir.

> **Əsas dəyər təklifi:** *"İstifadəçi texnologiyanın necə işlədiyini bilmədən, sadəcə nə etmək istədiyini deyərək nəticə əldə edə bilər."*

### Əsas Arxitektura və Məxfilik Qərarları
- **Minimum İcazə (Least Privilege):** YAXIN AI telefonun bütün məlumatlarına giriş əldə etmir. SMS, WhatsApp, şəkillər, zəng tarixçəsi və GPS oxunmur.
- **Lokal Kontakt Emalı (Local-first Contacts):** Kontakt siyahısı heç vaxt serverə göndərilmir və bazada saxlanılmır. AI yalnız niyyəti və münasibət/ad ifadəsini (`contact_alias`, məs. *"qızım"*, *"anam"*) müəyyən edir, uyğunlaşdırma isə cihaz daxilində aparılır.
- **İnsan Təsdiqi (Human-in-the-loop):** Zəng başlatmaq və ya xatırlatma yaratmaq kimi əməliyyatlar istifadəçinin açıq təsdiqi olmadan icra edilmir.
- **MVP Sərhədləri:** Real Wolt sifarişi və bank əməliyyatları MVP-yə daxil deyil (yalnız simulyasiya və ya gələcək mərhələ kimi nəzərdə tutulur).

---

## 2. MVP Modulları

1. **MVP 01 — Voice Contact Agent:** İstifadəçi danışaraq kontaktı tapır (*"Yaxın, qızıma zəng et"*), cihaz daxilində alias/ad üzrə kontakt tapılır və təsdiqdən sonra Android dialer açılır.
2. **MVP 02 — Smart Reminder Agent:** İstifadəçi danışaraq xatırlatma yaradır (*"Sabah saat 10-da dərmanımı xatırlat"*), tarix/vaxt (`Asia/Baku`) çıxarılır, bazada saxlanılır və lokal bildiriş planlaşdırılır.
3. **MVP 03 — Digital Shield Agent:** İstifadəçi şübhəli SMS və ya mesajı təqdim edir (*"Bank hesabınız bloklanıb..."*), qayda əsaslı baseline + LLM analizi ilə fırıldaqçılıq (scam/phishing) indikatorları və tövsiyələr Azərbaycan dilində izah edilir.

---

## 3. Qovluq Strukturu (Folder Structure)

```text
yaxin-ai/
├── backend/                  # Python + FastAPI + SQLAlchemy + LangGraph
├── mobile/                   # Flutter (Android-first MVP, Riverpod, Clean Architecture)
├── docs/                     # Texniki sənədləşmə (Architecture, API, DB, AI Workflow, Privacy)
├── infrastructure/           # Docker və deployment konfiqurasiyaları
├── .gitignore
├── docker-compose.yml
└── README.md
```

---

## 4. Quraşdırma və İşə Salma (Quick Start)

### 4.1. Database (Docker ilə)
```bash
docker compose up -d db
```

### 4.2. Backend (FastAPI)
```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Swagger UI: `http://127.0.0.1:8000/docs`

> **Qeyd:** Lokal inkişaf və test zamanı PostgreSQL əlçatan olmadıqda, backend avtomatik və ya konfiqurasiya ilə SQLite (`sqlite:///./yaxin_ai.db`) üzərində də işləyə bilir.

### 4.3. Testlərin İşə Salınması
```powershell
cd backend
pytest
```

### 4.4. Mobil Tətbiq (Flutter)
```powershell
cd mobile
flutter pub get
flutter run
```

---

## 5. Sənədləşmə (Documentation)

- [Technical Specification](docs/specification.md)
- [System Architecture](docs/architecture.md)
- [API Specification](docs/api-specification.md)
- [Database Schema](docs/database-schema.md)
- [AI Agent Workflow](docs/ai-workflow.md)
- [Privacy & Security Policy](docs/privacy-policy.md)

