import React from 'react';

/**
 * ErrorBoundary — React render xatosida butun ilovani oq ekranga
 * tushib qoldirmasligi uchun.
 *
 * Nima uchun kerak: bitta komponentdagi kichik xato (masalan
 * `null.toLocaleString()`) butun ekranni oq qilib qoldirardi —
 * foydalanuvchi hech narsani ko'ra olmasdi va tabga o'ta olmasdi.
 * Endi xato bo'lsa faqat shu bo'lim ko'rsatiladi, qolgani ishlaydi.
 */
interface Props {
  children: React.ReactNode;
  /** Ko'rsatiladigan bo'lim nomi */
  label?: string;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[ErrorBoundary]', this.props.label || '', error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div className="max-w-md md:max-w-4xl mx-auto mt-6 p-5 rounded-[26px] bg-[#12151d] border border-white/10
                    text-center space-y-3 shadow-xl">
        <div className="text-3xl">😕</div>
        <h3 className="text-sm font-bold text-white">
          Bu bo&apos;limda xatolik yuz berdi
        </h3>
        <p className="text-xs text-neutral-300 leading-relaxed">
          {this.props.label ? `"${this.props.label}" ` : ''}
          bo‘limi vaqtincha to‘xtadi. Boshqa bo‘limlardan foydalanishingiz mumkin.
        </p>
        <code className="block text-[10px] text-neutral-400 font-mono break-all">
          {String(this.state.error?.message || this.state.error).slice(0, 160)}
        </code>
        <button
          onClick={() => this.setState({ error: null })}
          className="w-full py-3 rounded-[16px] text-xs font-bold apple-spring cursor-pointer
                     bg-white text-black"
        >
          Qayta urinish
        </button>
      </div>
    );
  }
}

export default ErrorBoundary;