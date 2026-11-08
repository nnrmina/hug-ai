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
hug-ai/
├── public/                   # Web tətbiqi (PWA) — YEGANƏ frontend mənbəyi (Vercel + FastAPI)
├── backend/                  # Python + FastAPI + SQLAlchemy + LangGraph agent
├── api/index.py              # Vercel serverless giriş nöqtəsi (backend tətbiqini idxal edir)
├── hug-ml/                   # Eksperimental scikit-learn niyyət təsnifatçısı (backend-ə qoşulmayıb)
├── mobile/                   # Flutter skeleti (Android-first)
├── scripts/                  # Köməkçi skriptlər (səs faylları generasiyası)
└── docs/                     # Texniki sənədləşmə
```

---

## 4. Quraşdırma və İşə Salma (Quick Start)

### 4.1. Backend + Web tətbiqi
```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # GEMINI_API_KEY əlavə edin (opsional)
.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
- Web tətbiqi: `http://127.0.0.1:8000/`
- Swagger UI: `http://127.0.0.1:8000/docs`

Heç bir açar olmadan da işləyir: SQLite, qayda əsaslı niyyət analizi və pulsuz neural səs (edge-tts) standartdır.

**Gemini (tövsiyə olunur, pulsuz):** [aistudio.google.com/apikey](https://aistudio.google.com/apikey) ünvanından açar alın və `backend/.env` faylına yazın:
```bash
GEMINI_API_KEY=...
```
Server yenidən başladıqda ana səhifədə **✦ Gemini AI** nişanı görünəcək: səs birbaşa Gemini-yə göndərilir, Azərbaycan dilində transkripsiya + niyyət + parametrlər bir sorğuda çıxarılır. Gemini əlçatan olmadıqda (limit, şəbəkə) sistem avtomatik qayda əsaslı rejimə keçir.

**Web tətbiqi (PWA):** `public/` qovluğu yeganə frontend mənbəyidir (ES modulları, build addımı yoxdur). Telefonda “Ana ekrana əlavə et” ilə tətbiq kimi quraşdırıla bilər.

### 4.2. Docker
```bash
docker build -f backend/Dockerfile -t hug-ai .
docker run -p 8000:8000 --env-file backend/.env hug-ai
```

### 4.3. Testlər
```bash
cd backend && .venv/bin/pytest
```

### 4.4. Mobil Tətbiq (Flutter)
```bash
cd mobile && flutter pub get && flutter run
```

---

## 5. Sənədləşmə (Documentation)

- [Technical Specification](docs/specification.md)
- [System Architecture](docs/architecture.md)
- [API Specification](docs/api-specification.md)
- [Database Schema](docs/database-schema.md)
- [AI Agent Workflow](docs/ai-workflow.md)
- [Privacy & Security Policy](docs/privacy-policy.md)

