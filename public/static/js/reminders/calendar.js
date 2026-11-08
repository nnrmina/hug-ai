// Month calendar (Monday-first, Asia/Baku) generated from data: today highlight, dots on
// days with reminders, tap a day to filter the list, prev/next month.

export const AZ_MONTHS_TITLE = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "İyun", "İyul", "Avqust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr"];
const WEEKDAYS = ["B.E", "Ç.A", "Ç", "C.A", "C", "Ş", "B"];
const WEEKDAYS_LONG = ["bazar ertəsi", "çərşənbə axşamı", "çərşənbə", "cümə axşamı", "cümə", "şənbə", "bazar"];

export function bakuToday() {
  const b = new Date(Date.now() + 4 * 3600 * 1000);
  return { y: b.getUTCFullYear(), m: b.getUTCMonth(), d: b.getUTCDate() };
}

export const dayKey = (y, m, d) => `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;

/**
 * @param {HTMLElement} root  .calendar-card element
 * @param {{year:number, month:number, selected:string|null, counts:Map<string,number>,
 *          onSelect:(key:string|null)=>void, onMonth:(delta:number)=>void}} opts
 */
export function renderCalendar(root, { year, month, selected, counts, onSelect, onMonth }) {
  const today = bakuToday();
  const todayKey = dayKey(today.y, today.m, today.d);
  root.innerHTML = "";

  const header = document.createElement("div");
  header.className = "calendar-header";
  const prev = navButton("‹", "Əvvəlki ay", () => onMonth(-1));
  const next = navButton("›", "Növbəti ay", () => onMonth(1));
  const title = document.createElement("h3");
  title.className = "cal-month-title";
  title.id = "cal-month-title";
  title.textContent = `${AZ_MONTHS_TITLE[month]} ${year}`;
  header.append(prev, title, next);

  const weekdays = document.createElement("div");
  weekdays.className = "calendar-weekdays";
  weekdays.setAttribute("aria-hidden", "true");
  WEEKDAYS.forEach((w) => {
    const s = document.createElement("span");
    s.textContent = w;
    weekdays.append(s);
  });

  const grid = document.createElement("div");
  grid.className = "calendar-grid";
  grid.setAttribute("role", "grid");
  grid.setAttribute("aria-labelledby", "cal-month-title");

  const first = new Date(Date.UTC(year, month, 1));
  const lead = (first.getUTCDay() + 6) % 7; // Monday = 0
  const daysInMonth = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();

  for (let i = 0; i < lead; i++) {
    const blank = document.createElement("span");
    blank.className = "cal-day dim";
    blank.setAttribute("aria-hidden", "true");
    grid.append(blank);
  }

  for (let d = 1; d <= daysInMonth; d++) {
    const key = dayKey(year, month, d);
    const count = counts.get(key) || 0;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "cal-day";
    btn.dataset.day = key;
    btn.textContent = String(d);
    if (key === todayKey) btn.classList.add("today");
    if (count) btn.classList.add("has-events");
    if (key === selected) btn.classList.add("selected");
    const weekday = WEEKDAYS_LONG[(new Date(Date.UTC(year, month, d)).getUTCDay() + 6) % 7];
    btn.setAttribute("aria-label",
      `${d} ${AZ_MONTHS_TITLE[month].toLocaleLowerCase("az")}, ${weekday}${key === todayKey ? ", bu gün" : ""}${count ? `, ${count} xatırlatma` : ""}`);
    btn.setAttribute("aria-pressed", key === selected ? "true" : "false");
    btn.addEventListener("click", () => onSelect(key === selected ? null : key));
    grid.append(btn);
  }

  root.append(header, weekdays, grid);
}

function navButton(label, aria, onClick) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "cal-nav-btn";
  b.textContent = label;
  b.setAttribute("aria-label", aria);
  b.addEventListener("click", onClick);
  return b;
}
