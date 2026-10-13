/// <reference types="vite/client" />

// Bot nomi — Railway ENV da `VITE_BOT_USERNAME` sifatida beriladi.
// Kiritish ekranida "Botga o'tish" havolasi uchun ishlatiladi.
interface ImportMetaEnv {
  readonly VITE_BOT_USERNAME?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
