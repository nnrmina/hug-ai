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

### 4.3. Konfiqurasiya və təhlükəsizlik

| Dəyişən | Məqsəd |
|---|---|
| `ENVIRONMENT` | `production` olduqda server SQLite, `JWT_SECRET`-siz və ya `ALLOWED_ORIGINS=*` ilə **başlamır**. |
| `DATABASE_URL` | PostgreSQL (`postgres://…` və `postgresql://…` avtomatik `psycopg`-a çevrilir). Postgres əlçatmazdırsa server xəta verir — SQLite-a səssiz keçid yoxdur. |
| `JWT_SECRET` | Token imzası üçün (≥32 simvol). Development-də boş qala bilər (lokal `.dev_jwt_secret` yaranır, git-ə düşmür). |
| `ALLOW_SQLITE_FALLBACK` | Yalnız development: Postgres yoxdursa açıq şəkildə SQLite-a keçməyə icazə (default `false`). |
| `API_KEY` | Təyin edilərsə, `/api/v1/*` sorğuları `X-API-Key` header-i tələb edir (mobil tətbiq üçün). Veb səhifəyə qoyulan açar gizli deyil. |
| `ALLOWED_ORIGINS` | CORS üçün icazəli domenlər (vergüllə). |
| `STT_PROVIDER` | `none` (default — brauzer/telefon özü tanıyır), `openai` (server Whisper), `mock` (testlər). |
| `OPENAI_API_KEY` | Yalnız `STT_PROVIDER=openai` olduqda. **Heç vaxt brauzerə və ya mobil koda qoyulmur.** |
| `HUG_ML_URL` | İstəyə bağlı hug-ml klassifikatoru (məs. `http://localhost:8001`). Qaydalar `UNKNOWN` qaytaranda istifadə olunur. |

- **Autentifikasiya:** cihaz `POST /api/v1/auth/device` ilə anonim hesab və imzalı JWT alır; bütün digər endpoint-lər `Authorization: Bearer` tələb edir və istifadəçini yalnız tokendən götürür (sorğudakı `user_id` nəzərə alınmır). Token bitəndə cihaz `device_secret` ilə eyni hesaba yeni token alır.
- Xatırlatma, əməliyyat (`action_id`) və təhlükəsizlik analizi (`analysis_id`) yalnız sahibinə görünür; başqasınınkı 404 qaytarır.
- Bazaya migration: `cd backend && alembic upgrade head`. `init_db` ilə yaradılmış mövcud baza üçün əvvəlcə `alembic stamp 0002_pending_actions`, sonra `alembic upgrade head` (və ya server özü çatışmayan cədvəlləri yaradır — mövcud məlumat silinmir).
- Təsdiq gözləyən əməliyyatlar bazada saxlanılır, 10 dəqiqəyə bitir və yalnız bir dəfə təsdiqlənə bilər. Rədd edilmiş əməliyyat təsdiqlənə bilməz (409).
- Veb interfeysin yeganə mənbəyi `public/` qovluğudur (backend də onu təqdim edir). Docker: `docker build -f backend/Dockerfile .`
- Wolt/taksi ekranları **demo**dur — real sifariş verilmir. Kontakt nömrələri veb versiyada istifadəçi tərəfindən Tənzimləmələrdə daxil edilir və yalnız cihazda saxlanılır.
- Bu MVP-də tam istifadəçi autentifikasiyası (login) yoxdur; real istifadəçilərlə işə salmazdan əvvəl əlavə edilməlidir.

### 4.4. Testlərin İşə Salınması
```powershell
cd backend
pytest
```

### 4.5. Mobil Tətbiq (Flutter)
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

