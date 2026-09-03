'use client';

import { FormEvent, useState } from 'react';

const isPreview = typeof window !== 'undefined'
  && window.location.hostname.endsWith('-neiva-planner-site.rafaau0.workers.dev');
const API_URL = isPreview
  ? 'https://neiva-ai-api-staging.onrender.com'
  : 'https://neiva-ai-api.onrender.com';

export function CheckoutButton({ plan, featured }: { plan: string; featured?: boolean }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function checkout(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      const response = await fetch(`${API_URL}/v1/billing/checkout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan_code: plan, customer_name: name, customer_email: email }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Nao foi possivel iniciar o checkout.');
      localStorage.setItem(`neiva-order-${data.order_id}`, data.claim_token);
      window.location.href = data.checkout_url;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Falha inesperada.');
      setLoading(false);
    }
  }

  if (!open) {
    return <button type="button" onClick={() => setOpen(true)} className={`mt-6 block w-full rounded-full py-4 text-center font-bold ${featured ? 'bg-violet-500 text-white' : 'bg-[#17211f] text-white'}`}>Quero assinar</button>;
  }

  return <form className="mt-6 space-y-3" onSubmit={checkout}>
    <label className="block text-sm font-semibold">Seu nome
      <input required value={name} onChange={(event) => setName(event.target.value)} className="mt-1 w-full rounded-xl border border-stone-300 bg-white px-3 py-2 font-normal" autoComplete="name" />
    </label>
    <label className="block text-sm font-semibold">Seu e-mail
      <input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} className="mt-1 w-full rounded-xl border border-stone-300 bg-white px-3 py-2 font-normal" autoComplete="email" />
    </label>
    <button type="submit" disabled={loading} className={`block w-full rounded-full py-4 text-center font-bold ${featured ? 'bg-violet-500 text-white' : 'bg-[#17211f] text-white'} disabled:opacity-60`}>{loading ? 'Abrindo checkout...' : 'Continuar para pagamento'}</button>
    <p className="text-xs text-slate-500">Usaremos seu e-mail para identificar sua licenca.</p>
    {error && <p className="text-center text-xs text-red-600">{error}</p>}
  </form>;
}
