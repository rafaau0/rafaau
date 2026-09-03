'use client';
import { useState } from 'react';
export function CheckoutButton({ plan, featured }: { plan: string; featured?: boolean }) {
  const [loading, setLoading] = useState(false); const [error, setError] = useState('');
  async function checkout(){ setLoading(true); setError(''); try { const response=await fetch('https://neiva-ai-api.onrender.com/v1/billing/checkout',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plan_code:plan})}); const data=await response.json(); if(!response.ok) throw new Error(data.detail||'Não foi possível iniciar o checkout.'); window.location.href=data.checkout_url; } catch(e){setError(e instanceof Error?e.message:'Falha inesperada.');setLoading(false);} }
  return <><button type="button" onClick={checkout} disabled={loading} className={`mt-6 block w-full rounded-full py-4 text-center font-bold ${featured?'bg-violet-500 text-white':'bg-[#17211f] text-white'} disabled:opacity-60`}>{loading?'Abrindo checkout...':'Quero assinar'}</button>{error&&<p className="mt-3 text-center text-xs text-red-600">{error}</p>}</>;
}
