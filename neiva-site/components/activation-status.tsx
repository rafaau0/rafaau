'use client';

import { useEffect, useState } from 'react';

const API_URL = 'https://neiva-ai-api.onrender.com';

export function ActivationStatus() {
  const [message, setMessage] = useState('');

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const order = params.get('order');
    if (params.get('checkout') !== 'success' || !order) return;
    const claim = localStorage.getItem(`neiva-order-${order}`);
    if (!claim) {
      setMessage('Pagamento recebido. Guarde seu e-mail; o codigo de ativacao sera disponibilizado apos a confirmacao.');
      return;
    }
    let cancelled = false;
    let attempts = 0;
    const check = async () => {
      try {
        const response = await fetch(`${API_URL}/v1/billing/orders/${encodeURIComponent(order)}?claim=${encodeURIComponent(claim)}`);
        const data = await response.json();
        if (cancelled) return;
        if (data.activation_code) {
          setMessage(`Pagamento confirmado. Seu codigo de ativacao: ${data.activation_code}`);
          return;
        }
        attempts += 1;
        setMessage('Pagamento enviado. Estamos confirmando sua licenca...');
        if (attempts < 6) window.setTimeout(check, 2500);
      } catch {
        if (!cancelled) setMessage('Pagamento enviado. Aguarde a confirmacao da sua licenca.');
      }
    };
    check();
    return () => { cancelled = true; };
  }, []);

  if (!message) return null;
  return <div className="mx-auto mt-4 max-w-6xl rounded-xl bg-lime-200 px-5 py-4 text-center text-sm font-semibold text-[#17211f]">{message}</div>;
}
