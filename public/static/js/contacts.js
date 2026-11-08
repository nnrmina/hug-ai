// On-device contacts. Privacy by design: this list never leaves the phone — the server only
// returns an alias ("qızım", "Almaz xala") and matching happens here.

export const CONTACTS = [
  {
    id: "sister",
    call_phrase: "Bacıma zəng et",
    aliases: ["bacım", "bacim", "bacı", "baci", "bacıma", "almaz", "almaz xala", "almaza"],
    display_name: "Almaz xala (Bacım)",
    short_name: "Almaz xala",
    relation_title: "Bacınız Almaz xalaya",
    phone_number: "+994 50 456 78 90",
    initial: "A"
  },
  {
    id: "daughter",
    call_phrase: "Qızıma zəng et",
    aliases: ["qızım", "qizim", "qızıma", "qız", "sevinc", "sevincə"],
    display_name: "Sevinc Məmmədova (Qızım)",
    short_name: "Sevinc",
    relation_title: "Qızınız Sevincə",
    phone_number: "+994 50 123 45 67",
    initial: "S"
  },
  {
    id: "mother",
    call_phrase: "Mamama zəng et",
    aliases: ["anam", "ana", "mama", "mamam", "mamama", "anama"],
    display_name: "Anam (Mama)",
    short_name: "Mama",
    relation_title: "Mamanıza",
    phone_number: "+994 55 234 56 78",
    initial: "M"
  },
  {
    id: "son",
    call_phrase: "Oğluma zəng et",
    aliases: ["oğlum", "oglum", "oğul", "oğluma", "murad", "murada"],
    display_name: "Murad (Oğlum)",
    short_name: "Murad",
    relation_title: "Oğlunuz Murada",
    phone_number: "+994 70 345 67 89",
    initial: "M"
  },
  {
    id: "doctor",
    call_phrase: "Həkimə zəng et",
    aliases: ["həkim", "hekim", "həkimə", "nigar", "doktor", "nigar həkim"],
    display_name: "Dr. Nigar Həkim",
    short_name: "Dr. Nigar",
    relation_title: "Dr. Nigar Həkimə",
    phone_number: "+994 50 765 43 21",
    initial: "H"
  }
];

const normalize = (s) => (s || "").toLocaleLowerCase("az").replace(/[.,!?“”"']/g, "").trim();

// Exact alias match first, then whole-word containment ("Almaz xala" ⊃ "almaz").
export function findContact(query) {
  const q = normalize(query);
  if (!q) return null;
  for (const c of CONTACTS) {
    if (c.aliases.includes(q)) return c;
  }
  const words = new Set(q.split(/\s+/));
  for (const c of CONTACTS) {
    if (c.aliases.some((a) => !a.includes(" ") && words.has(a))) return c;
  }
  return null;
}

export const telHref = (contact) => `tel:${contact.phone_number.replace(/\s+/g, "")}`;

export function smsHref(contact, body) {
  const number = contact.phone_number.replace(/\s+/g, "");
  const sep = /iPhone|iPad|iPod/.test(navigator.userAgent) ? "&" : "?";
  return `sms:${number}${body ? `${sep}body=${encodeURIComponent(body)}` : ""}`;
}
