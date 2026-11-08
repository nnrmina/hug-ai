# YAXIN AI — API Specification

**Base URL:** `/api/v1`

---

## 1. Health & Root

### `GET /`
Returns welcome message.
```json
{
  "message": "Welcome to YAXIN AI"
}
```

### `GET /health` və `GET /api/v1/health`
Returns service health status.
```json
{
  "status": "healthy"
}
```

---

## 2. Assistant API

| Method | Endpoint | Məqsəd |
|---|---|---|
| `POST` | `/api/v1/assistant/message` | Mətn əmri qəbul etmək və AI Agent workflow başlatmaq |
| `POST` | `/api/v1/assistant/voice` | Audio fayl və ya transkript qəbul etmək |
| `GET` | `/api/v1/assistant/status/{id}` | Əməliyyatın cari statusunu yoxlamaq |
| `POST` | `/api/v1/assistant/confirm/{id}` | Gözləyən əməliyyatı təsdiqləmək (Human-in-the-loop) |
| `POST` | `/api/v1/assistant/cancel/{id}` | Gözləyən əməliyyatı ləğv etmək |

### `POST /api/v1/assistant/message`
**Request:**
```json
{
  "message": "Sabah saat 10-da mənə qızıma zəng etməyi xatırlat",
  "user_id": "00000000-0000-0000-0000-000000000001"
}
```
**Response:**
```json
{
  "intent": "CREATE_REMINDER",
  "response": "\"Qızıma zəng et\" üçün 09.11.2026 saat 10:00 vaxtına xatırlatma yaradılsın?",
  "status": "needs_confirmation",
  "action_id": "a1b2c3d4-...",
  "action_data": {
    "action_type": "CREATE_REMINDER",
    "title": "Qızıma zəng et",
    "scheduled_at": "2026-11-09T10:00:00+04:00",
    "timezone": "Asia/Baku"
  }
}
```

---

## 3. Reminder API

| Method | Endpoint | Məqsəd |
|---|---|---|
| `POST` | `/api/v1/reminders` | Yeni xatırlatma yaratmaq |
| `GET` | `/api/v1/reminders` | İstifadəçinin xatırlatmalarını siyahılamaq |
| `GET` | `/api/v1/reminders/{id}` | Конkret xatırlatmanı göstərmək |
| `PATCH` | `/api/v1/reminders/{id}` | Xatırlatmanı yeniləmək (vaxt, başlıq, status) |
| `DELETE` | `/api/v1/reminders/{id}` | Xatırlatmanı silmək |

---

## 4. Security API (Digital Shield)

| Method | Endpoint | Məqsəd |
|---|---|---|
| `POST` | `/api/v1/security/analyze` | Şübhəli SMS və ya mesajı analiz etmək |
| `GET` | `/api/v1/security/result/{id}` | Analiz nəticəsini əldə etmək |

### `POST /api/v1/security/analyze`
**Request:**
```json
{
  "message": "Bank hesabınız bloklanıb. Təcili linkə daxil olun və kart məlumatlarını yazın: http://bit.ly/fake-bank"
}
```
**Response:**
```json
{
  "analysis_id": "f47ac10b-...",
  "risk_level": "high",
  "risk_score": 85,
  "indicators": [
    "urgency",
    "credential_request",
    "suspicious_link",
    "bank_impersonation"
  ],
  "explanation": "Bu mesajda yüksək dələduzluq (fırıldaqçılıq) əlamətləri aşkar edildi: təcili hərəkət tələbi, bank adından istifadə, şübhəli keçid və kart məlumatlarının istənilməsi.",
  "recommendation": "Keçidə (linkə) daxil olmayın və kart/şifrə məlumatlarınızı heç kimlə paylaşmayın."
}
```

---

## 5. User API

| Method | Endpoint | Məqsəd |
|---|---|---|
| `GET` | `/api/v1/users/me` | Cari istifadəçi və seçim məlumatları |
| `PATCH` | `/api/v1/users/preferences` | İstifadəçi seçimlərini (`voice_speed`, `voice_response`, `theme`, `language`) yeniləmək |

