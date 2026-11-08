# YAXIN AI — Privacy & Security Policy

## 1. Əsas Prinsiplər (Core Security Principles)

1. **Least Privilege (Minimum İcazə):** Tətbiq yalnız funksiyası üçün lazım olan icazələri (mikrofon, icazə verildikdə kontaktlar və bildirişlər) alır.
2. **Explicit Consent (Açıq Razılıq):** İstifadəçinin açıq razılığı olmadan heç bir xarici əməliyyat icra edilmir.
3. **Data Minimization (Məlumatların Minimumlaşdırılması):** Lazım olmayan şəxsi məlumatlar toplanmır. SMS, WhatsApp, şəkillər, zəng tarixçəsi və GPS oxunmur.
4. **Human-in-the-Loop (İnsan Təsdiqi):** Zəng başlatmaq, mesaj göndərmək və xatırlatma qeydə almaq kimi əməliyyatlarda insan təsdiqi tələb olunur.
5. **Local-First Contacts (Cihaz Daxilində Kontakt Emalı):** Kontakt siyahısı heç vaxt serverə göndərilmir və verilənlər bazasında saxlanılmır.

## 2. Əməliyyat Risk Səviyyələri (Action Risk Levels)

| Əməliyyat | Risk | Qayda |
|---|---|---|
| Sadə sual (`GENERAL_QUESTION`) | Low | Birbaşa cavab |
| Xatırlatma yaratmaq (`CREATE_REMINDER`) | Low/Medium | Məlumatı göstərib təsdiqləmək |
| Kontakt tapmaq (`CONTACT_LOOKUP`) | Medium | Kontaktı cihazda tapıb göstərmək |
| Zəng başlatmaq (`MAKE_CALL`) | Medium | Açıq istifadəçi təsdiqi |
| Səsli mesaj (`SEND_VOICE_MESSAGE`) | Medium/High | Mesaj və alıcı təsdiqi |
| Pul köçürmək | High | MVP-də dəstəklənmir (bloklanır) |
| Məhsul sifariş etmək (Wolt və s.) | High | MVP-də yalnız simulyasiya olunur |

## 3. Verilənlərin Saxlanması (Data Retention)

- `agent_events` cədvəlində yalnız əməliyyatın növü (`intent`), statusu (`status`) və vaxtı saxlanılır.
- Tam səs yazıları, kontakt siyahısı və istifadəçinin yoxlamaq üçün göndərdiyi həssas mesaj məzmunları daimi olaraq bazada saxlanılmır.

