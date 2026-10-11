/**
 * AEmoji — animatsiyalangan emoji.
 *
 * Telegram'dagi kabi "premium" ko'rinish WebApp (brauzer) da bo'lmaydi:
 * Telegram custom emoji faqat Telegram ilovalarida chiziladi. Shuning uchun
 * biz shu effektni o'zimiz yaratamiz:
 *
 *   1) Twemoji SVG — Telegram'dagi emoji bilan BIR XIL ko'rinish
 *      (jsDelivr orqali, keshlashga tayyor)
 *   2) CSS animatsiya — suzish, pulsatsiya, yaltirash, tebranish
 *   3) Zaxira — rasm yuklanmasa oddiy emoji matni ko'rsatiladi
 *      (internet yo'q holatda ham bo'sh joy qolmaydi)
 *
 * Ishlatish:
 *   <AEmoji char="⭐" size={22} anim="shine" />
 */
import React, { useMemo, useState } from 'react';

const TWEMOJI_CDN = 'https://cdn.jsdelivr.net/gh/jdecked/twemoji@main/assets/svg';

export type EmojiAnim = 'float' | 'pulse' | 'shine' | 'bounce' | 'spin' | 'swing' | 'none';

interface Props {
  char: string;
  size?: number;
  anim?: EmojiAnim;
  className?: string;
  /** Ekranda o'qiladigan matn (maxsus holat uchun) */
  label?: string;
}

/** Emoji belgisini Twemoji kod nuqtasi formatiga aylantiradi. */
function toCodepoint(char: string): string {
  // Variation Selector (FE0F) va zero-width joiner Twemoji yo'li bilan mos kelmaydi
  const cleaned = (char || '')
    .replace(/[\uFE0E\uFE0F]/g, '')
    .replace(/\u200D/g, '')
    .replace(/\s+/g, '');
  return [...cleaned]
    .map((c) => (c.codePointAt(0) ?? 0).toString(16))
    .join('-');
}

const cache = new Map<string, string>();

export default function AEmoji({
  char,
  size = 20,
  anim = 'float',
  className = '',
  label,
}: Props) {
  const [failed, setFailed] = useState(false);

  const url = useMemo(() => {
    const cp = toCodepoint(char);
    if (!cp || !/^[0-9a-f]+(-[0-9a-f]+)*$/.test(cp)) return null;
    if (!cache.has(cp)) cache.set(cp, `${TWEMOJI_CDN}/${cp}.svg`);
    return cache.get(cp) ?? null;
  }, [char]);

  const box = {
    width: size,
    height: size,
    lineHeight: `${size}px`,
    fontSize: `${size}px`,
  };

  // Zaxira: rasm yuklanmasa yoki belgi topilmasa — oddiy emoji
  if (!url || failed) {
    return (
      <span
        className={`aemoji aemoji--fallback ${className}`}
        style={box}
        role="img"
        aria-label={label ?? char}
        title={label ?? char}
      >
        {char}
      </span>
    );
  }

  return (
    <img
      src={url}
      alt={label ?? char}
      title={label ?? char}
      loading="lazy"
      decoding="async"
      draggable={false}
      onError={() => setFailed(true)}
      className={`aemoji aemoji--img aemoji--${anim} ${className}`}
      style={{ ...box, fontSize: 0 }}
    />
  );
}