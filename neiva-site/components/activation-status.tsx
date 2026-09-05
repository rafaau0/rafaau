'use client';

import { useEffect, useState } from 'react';

const isPreview = typeof window !== 'undefined' && window.location.hostname.endsWith('-neiva-planner-site.rafaau0.workers.dev');
const API_URL = isPreview ? 'https://neiva-ai-api-staging.onrender.com' : 'https://neiva-ai-api.onrender.com';

export function ActivationStatus() {
  const [message, setMessage] = useState('');
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const order = params.get('order');
    if (params.get('checkout') !== 'success' || !order) return;
    const claim = localStorage.getItem(`neiva-order-${order}`);
    if (!claim) {
      window.setTimeout(() => setMessage('Pagamento enviado. Assim que for aprovado, entre no aplicativo com seu e-mail e senha.'), 0);
      return;
    }
    let cancelled = false;
    let attempts = 0;
    const check = async () => {
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 10000);
      try {
        const response = await fetch(`${API_URL}/v1/billing/orders/${encodeURIComponent(order)}?claim=${encodeURIComponent(claim)}`, { signal: controller.signal });
        const data = await response.json().catch(() => ({})) as { license_active?: boolean };
        if (cancelled) return;
        if (!response.ok) throw new Error('status');
        if (data.license_active) { setMessage('Pagamento confirmado. Sua licenca esta ativa: abra o rafaau e entre com seu e-mail e senha.'); return; }
        attempts += 1;
        setMessage('Pagamento enviado. Estamos confirmando sua licenca...');
        if (attempts < 6) window.setTimeout(check, 2500);
      } catch {
        attempts += 1;
        if (!cancelled) {
          setMessage('Pagamento enviado. Nao foi possivel consultar a confirmacao agora; tente entrar no aplicativo em alguns instantes.');
          if (attempts < 3) window.setTimeout(check, 4000);
        }
      } finally {
        window.clearTimeout(timeout);
      }
    };
    void check();
    return () => { cancelled = true; };
  }, []);
  if (!message) return null;
  return <div className="mx-auto mt-4 max-w-6xl rounded-xl bg-lime-200 px-5 py-4 text-center text-sm font-semibold text-[#17211f]">{message}</div>;
}
