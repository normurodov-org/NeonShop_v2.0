/**
 * Telegram HTML matnini WebApp uchun toza matnga aylantiradi.
 *
 * Nima uchun kerak: server.ts xabarlarni Telegram HTML formatida
 * yuboradi (`<b>`, `<i>`, `<code>`), lekin WebApp toast oddiy matn
 * sifatida ko'rsatadi — shuning uchun foydalanuvchi xom teglarni
 * ko'radi: "<b>Buyurtmangiz qabul qilindi!</b>".
 *
 * Yechim: teglar oddiy matnga aylantiriladi.
 */
export function telegramToPlain(html: string | null | undefined): string {
  if (!html) return '';
  let t = String(html);

  // &lt; style kodlarni avval ochamiz
  t = t
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&#x27;/gi, "'");

  // Teglarni olib tashlaymiz (kontent saqlanadi)
  t = t.replace(/<\/?[a-zA-Z][^>]*>/g, '');

  // Raqamli kodlar (masalan 2 000 → 2&#44;000)
  t = t.replace(/&#(\d+);/g, (_, n) => String.fromCharCode(Number(n)));
  t = t.replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCharCode(parseInt(n, 16)));
  t = t.replace(/&amp;/g, '&');

  return t.trim();
}

/** Toast uchun qisqa matn (uzun bo'lsa qisqartiradi). */
export function toastText(html: string | null | undefined, max = 180): string {
  const t = telegramToPlain(html).replace(/\s*\n+\s*/g, ' • ').replace(/\s{2,}/g, ' ');
  return t.length > max ? `${t.slice(0, max - 1).trimEnd()}…` : t;
}
