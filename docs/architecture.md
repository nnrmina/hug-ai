# YAXIN AI — System Architecture

## 1. High-Level Architecture

YAXIN AI monolit bir AI funksiyası kimi deyil, bir-biri ilə əlaqəli modullar (Modular Monolith) kimi qurulmuşdur:

```text
USER
  |
  v
FLUTTER MOBILE APP
  |
  v
VOICE INPUT
  |
  v
SPEECH-TO-TEXT
  |
  v
FASTAPI BACKEND
  |
  v
AI AGENT ORCHESTRATOR (LangGraph)
  |
  +-------------------+-------------------+
  |                   |                   |
  v                   v                   v
CONTACT             REMINDER            SECURITY
AGENT               AGENT               AGENT
  |                   |                   |
  +---------+---------+-------------------+
            |
            v
     PERMISSION CHECK
            |
            v
    USER CONFIRMATION (Human-in-the-Loop)
            |
            v
        EXECUTION
            |
            v
     RESULT TO USER
```

## 2. Component Responsibilities

| Component | Məsuliyyəti |
|---|---|
| **Flutter** | İstifadəçi interfeysi, səs yazılışı, lokal kontakt axtarışı və bildirişlər |
| **FastAPI** | Backend REST API, validasiya və biznes məntiqi |
| **Speech-to-Text** | Səsi Azərbaycan dilində mətnə çevirmək (Whisper / Android STT) |
| **LLM Adapter** | Niyyəti (intent) və strukturlaşdırılmış parametrləri çıxarmaq |
| **LangGraph** | State-based agent workflow idarəetməsi |
| **PostgreSQL** | İstifadəçi, seçim, xatırlatma və əməliyyat metadata-sı |
| **Local Contacts** | Kontaktların cihaz daxilində icazəli axtarışı və alias uyğunlaşdırılması |
| **Notification Service** | Cihazda planlaşdırılmış xatırlatma bildirişləri |
| **Security Layer** | İcazə, risk səviyyəsi və təsdiq yoxlamaları |

## 3. Local-First Contact Architecture

Kontaktların axtarışı üçün hər dəfə backend-ə kontakt siyahısı göndərilmir:
1. Flutter cihazda kontaktları oxumaq üçün icazə alır.
2. AI istifadəçinin dediyi ad və ya münasibət ifadəsini (`contact_alias`, məs. `"qızım"`) müəyyənləşdirir və `CONTACT_LOOKUP` tələbi qaytarır.
3. Flutter lokal alias və kontakt siyahısında uyğun kontaktı tapır.
4. İstifadəçi təsdiq ekranında təsdiqlədikdən sonra Android dialer (`tel:`) açılır.

