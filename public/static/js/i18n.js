// Screen labels for replies in Russian (the home UI itself stays Azerbaijani).
const RU = {
  "Kontakt tapılmadı": "Контакт не найден",
  "Bunu edə bilmərəm": "Я не могу это сделать",
  "Eşidə bilmədim": "Не расслышала",
  "Bir sualım var": "У меня вопрос",
  "Başa düşmədim": "Не поняла",
  "Təşəkkürlər": "Спасибо",
  "Qeyd edildi ✓": "Записано ✓",
  "Hava proqnozu": "Погода",
  "Sağlamlıq": "Здоровье",
  "Xatırlatma yaradılsın?": "Создать напоминание?",
  "Hər gün xatırladım?": "Напоминать каждый день?",
  "Taksi çağırılsın?": "Вызвать такси?",
  "Bəli, zəng et": "Да, позвонить",
  "Bəli, göndər": "Да, отправить",
  "Bəli, yarat": "Да, создать",
  "Bəli, xatırlat": "Да, напоминать",
  "Bəli, taksi çağır": "Да, вызвать",
  "Bəli, sifariş et": "Да, заказать",
  "Bəli, icra et": "Да, выполнить",
  "Xeyr, ləğv et": "Нет, отменить",
  "“Bəli” və ya “Xeyr” deyin...": "Скажите «да» или «нет»...",
  "🎙️ Eşidirəm... “Bəli” deyin": "🎙️ Слушаю... скажите «да»",
  " Cavab verin": " Ответить",
  " Yenidən danışın": " Сказать ещё",
  "Ana səhifəyə qayıt": "На главную",
  "Növbəti addım": "Следующий шаг",
  "Bəli və ya xeyr deyin.": "Скажите да или нет.",
  "Düyməyə toxunun və ya mikrofona “Bəli” deyin": "Нажмите кнопку или скажите «да»",
  "✓ Səslə təsdiqləndi": "✓ Подтверждено голосом",
  "Təsdiqləyin": "Подтвердите"
};

let lang = "az";
export const setLang = (l) => { lang = l === "ru" ? "ru" : "az"; };
export const getLang = () => lang;
export const tr = (az) => (lang === "ru" && RU[az]) || az;
