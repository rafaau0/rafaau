'use client';

import { type SyntheticEvent, useState } from 'react';

type ApiResponse = {
  access_token?: string;
  detail?: string;
  order_id?: string;
  claim_token?: string;
  checkout_url?: string;
};

const isPreview = typeof window !== 'undefined' && window.location.hostname.endsWith('-neiva-planner-site.rafaau0.workers.dev');
const API_URL = isPreview ? 'https://neiva-ai-api-staging.onrender.com' : 'https://neiva-ai-api.onrender.com';

export function CheckoutButton({ plan, featured }: { plan: string; featured?: boolean }) {
  const [open, setOpen] = useState(false);
  const [existingAccount, setExistingAccount] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const buttonClass = `block w-full rounded-lg py-4 text-center font-bold ${featured ? 'bg-[#FF263D] text-white hover:bg-[#D91E32]' : 'bg-[#17191F] text-white hover:bg-[#343841]'} transition disabled:opacity-60`;

  async function checkout(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!existingAccount && password !== confirmPassword) { setError('As senhas precisam ser iguais.'); return; }
    setLoading(true); setError('');
    try {
      const endpoint = existingAccount ? '/v1/auth/sign-in' : '/v1/auth/register';
      const body = existingAccount ? { email, password } : { name, email, password };
      const authResponse = await fetch(`${API_URL}${endpoint}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const authData = await authResponse.json() as ApiResponse;
      if (!authResponse.ok) {
        if (authResponse.status === 409 && !existingAccount) {
          setExistingAccount(true);
          setError('Esta conta ja existe. Informe a senha abaixo para entrar e continuar.');
          setLoading(false);
          return;
        }
        throw new Error(authData.detail || 'Nao foi possivel acessar sua conta.');
      }
      if (plan === 'free') {
        setSuccess(true);
        setLoading(false);
        return;
      }
      if (!authData.access_token) throw new Error('A API não retornou uma sessão válida.');
      const response = await fetch(`${API_URL}/v1/billing/checkout`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${authData.access_token}` }, body: JSON.stringify({ plan_code: plan }),
      });
      const data = await response.json() as ApiResponse;
      if (!response.ok) throw new Error(data.detail || 'Nao foi possivel iniciar o checkout.');
      if (!data.order_id || !data.claim_token || !data.checkout_url) throw new Error('O checkout retornou dados incompletos.');
      localStorage.setItem(`neiva-order-${data.order_id}`, data.claim_token);
      window.location.href = data.checkout_url;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Falha inesperada.'); setLoading(false);
    }
  }

  if (!open) return <button type="button" onClick={() => setOpen(true)} className={`mt-6 ${buttonClass}`}>{plan === 'free' ? 'Começar grátis' : 'Quero assinar'}</button>;
  if (success) return <div className="mt-6 rounded-xl bg-emerald-50 p-4 text-sm text-emerald-800"><strong>Conta gratuita criada!</strong><br />Baixe o aplicativo e entre com este e-mail e senha.</div>;
  return <form className="mt-6 space-y-3" onSubmit={checkout}>
    <p className="text-sm font-semibold text-[#17191F]">{existingAccount ? 'Entre para continuar' : plan === 'free' ? 'Crie sua conta gratuita' : 'Crie sua conta para continuar'}</p>
    {!existingAccount && <label className="block text-sm font-semibold">Seu nome<input required value={name} onChange={(event) => setName(event.target.value)} className="mt-1 w-full rounded-xl border border-stone-300 bg-white px-3 py-2 font-normal" autoComplete="name" /></label>}
    <label className="block text-sm font-semibold">Seu e-mail<input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} className="mt-1 w-full rounded-xl border border-stone-300 bg-white px-3 py-2 font-normal" autoComplete="email" /></label>
    <label className="block text-sm font-semibold">{existingAccount ? 'Sua senha' : 'Crie uma senha'}<input required minLength={8} type="password" value={password} onChange={(event) => setPassword(event.target.value)} className="mt-1 w-full rounded-xl border border-stone-300 bg-white px-3 py-2 font-normal" autoComplete={existingAccount ? 'current-password' : 'new-password'} /></label>
    {!existingAccount && <label className="block text-sm font-semibold">Confirme sua senha<input required minLength={8} type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} className="mt-1 w-full rounded-xl border border-stone-300 bg-white px-3 py-2 font-normal" autoComplete="new-password" /></label>}
    <button type="submit" disabled={loading} className={buttonClass}>{loading ? (plan === 'free' ? 'Criando conta...' : 'Abrindo checkout...') : (plan === 'free' ? 'Criar conta grátis' : 'Continuar para pagamento')}</button>
    <button type="button" onClick={() => { setExistingAccount(!existingAccount); setError(''); }} className="w-full text-center text-xs font-semibold text-[#D91E32] hover:underline">{existingAccount ? 'Ainda nao tenho conta' : 'Ja tenho uma conta'}</button>
    <p className="text-xs text-slate-500">{plan === 'free' ? 'Não é necessário cartão de crédito.' : 'A licença será vinculada a esta conta após a aprovação do pagamento.'}</p>
    {error && <p className="text-center text-xs text-red-600">{error}</p>}
  </form>;
}
