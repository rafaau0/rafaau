import { ActivationStatus } from '../components/activation-status';
import { CheckoutButton } from '../components/checkout-button';

const features = [
  { number: '01', title: 'Calendário de conteúdo', text: 'Visualize o mês inteiro, distribua campanhas, posts e entregas antes de o prazo virar urgência.', color: 'bg-[#FFF0F2] text-[#FF263D]' },
  { number: '02', title: 'Clientes e demandas', text: 'Centralize briefing, responsável, status e data de cada conteúdo em uma rotina organizada.', color: 'bg-[#EEF5FF] text-[#2563EB]' },
  { number: '03', title: 'Trello conectado', text: 'Envie seu planejamento para o quadro certo e deixe a equipe acompanhar o que acontece.', color: 'bg-[#EAF7F1] text-[#168A5B]' },
  { number: '04', title: 'Vídeo e IA Neiva', text: 'Transcreva vídeos, encontre trechos promissores e transforme material longo em novas ideias.', color: 'bg-[#FFF6E8] text-[#C77A08]' },
];

const workflow = [
  ['Planeje', 'Crie pautas, defina clientes, formatos e datas no calendário visual.'],
  ['Produza', 'Organize a produção e use o estúdio para trabalhar seus vídeos e legendas.'],
  ['Distribua', 'Envie para o Trello e acompanhe o que está pronto, em andamento ou pendente.'],
];

const plans = [
  { code: 'essencial', name: 'Essencial', price: '49,90', annual: '39,90', credits: '20 créditos de IA por mês' },
  { code: 'pro', name: 'Pro', price: '89,90', annual: '69,90', credits: '80 créditos de IA por mês' },
];

function Logo() {
  return <span className="inline-flex size-9 items-center justify-center rounded-xl bg-[#FF263D] text-lg font-black text-white">N</span>;
}

export default function Home() {
  return <main className="min-h-screen bg-[#F7F8FA] text-[#17191F]">
    <ActivationStatus />

    <nav className="mx-auto flex h-20 max-w-7xl items-center justify-between px-6">
      <a href="#inicio" className="flex items-center gap-3 font-bold tracking-tight"><Logo /> <span>Neiva Planner</span></a>
      <div className="hidden items-center gap-7 text-sm font-medium text-[#68707D] md:flex">
        <a className="hover:text-[#17191F]" href="#recursos">O que entrega</a>
        <a className="hover:text-[#17191F]" href="#como-funciona">Como funciona</a>
        <a className="hover:text-[#17191F]" href="#planos">Planos</a>
      </div>
      <a href="#planos" className="rounded-lg bg-[#FF263D] px-4 py-2.5 text-sm font-bold text-white shadow-sm transition hover:bg-[#D91E32]">Começar agora</a>
    </nav>

    <section id="inicio" className="mx-auto grid max-w-7xl gap-12 px-6 pb-20 pt-12 lg:grid-cols-[1.04fr_.96fr] lg:items-center lg:pt-20">
      <div>
        <p className="mb-6 inline-flex rounded-full bg-[#FFF0F2] px-4 py-2 text-xs font-bold tracking-[.12em] text-[#9F1D2C]">PLANEJAMENTO DE CONTEÚDO, SEM IMPROVISO</p>
        <h1 className="max-w-3xl text-5xl font-black leading-[.98] tracking-[-.055em] sm:text-6xl lg:text-7xl">A sua operação de conteúdo <span className="text-[#FF263D]">organizada</span> em um só lugar.</h1>
        <p className="mt-7 max-w-2xl text-lg leading-8 text-[#68707D]">O Neiva Planner reúne calendário, clientes, produção de vídeo, IA e Trello para você saber exatamente o que criar, quando entregar e qual é o próximo passo.</p>
        <div className="mt-9 flex flex-wrap gap-3">
          <a href="#planos" className="rounded-lg bg-[#FF263D] px-6 py-4 font-bold text-white shadow-lg shadow-red-200 transition hover:bg-[#D91E32]">Quero organizar meu conteúdo</a>
          <a href="#recursos" className="rounded-lg border border-[#DDE1E7] bg-white px-6 py-4 font-bold text-[#17191F] transition hover:bg-[#F0F2F5]">Ver o que está incluso</a>
        </div>
        <div className="mt-7 flex flex-wrap gap-x-6 gap-y-2 text-sm font-medium text-[#68707D]"><span>✓ 7 dias para conhecer</span><span>✓ Cancele quando quiser</span><span>✓ Use em até 2 computadores</span></div>
      </div>

      <div className="relative mx-auto w-full max-w-xl">
        <div className="absolute -left-8 top-14 h-52 w-52 rounded-full bg-[#FF263D]/10 blur-3xl" />
        <div className="relative overflow-hidden rounded-2xl border border-[#DDE1E7] bg-white shadow-2xl shadow-slate-900/10">
          <div className="flex items-center justify-between border-b border-[#DDE1E7] px-5 py-4"><div className="flex gap-1.5"><i className="size-2.5 rounded-full bg-[#FF263D]" /><i className="size-2.5 rounded-full bg-[#F2B84B]" /><i className="size-2.5 rounded-full bg-[#168A5B]" /></div><span className="text-xs font-bold text-[#68707D]">NEIVA PLANNER</span><span className="size-4" /></div>
          <div className="grid grid-cols-[108px_1fr] bg-[#F7F8FA]">
            <aside className="min-h-[330px] border-r border-[#DDE1E7] bg-white p-4 text-[10px] font-bold text-[#68707D]"><div className="mb-7 flex items-center gap-2 text-[#17191F]"><Logo /> <span className="hidden sm:inline">Neiva</span></div><p className="rounded-md bg-[#FFF0F2] px-2 py-2 text-[#9F1D2C]">Planejamento</p><p className="mt-3 px-2">Conteúdos</p><p className="mt-3 px-2">Vídeos & IA</p><p className="mt-3 px-2">Clientes</p><p className="mt-3 px-2">Configurações</p></aside>
            <div className="p-5"><div className="flex items-start justify-between"><div><p className="text-xs text-[#68707D]">Visão geral</p><h2 className="mt-1 text-lg font-black">Planejamento de setembro</h2></div><button className="rounded-md bg-[#FF263D] px-3 py-2 text-[10px] font-bold text-white">+ NOVO CONTEÚDO</button></div>
              <div className="mt-5 grid grid-cols-4 gap-2"><div className="rounded-lg border border-[#DDE1E7] bg-white p-2"><b className="text-sm">12</b><p className="mt-1 text-[9px] text-[#68707D]">Conteúdos</p></div><div className="rounded-lg border border-[#DDE1E7] bg-white p-2"><b className="text-sm text-[#2563EB]">04</b><p className="mt-1 text-[9px] text-[#68707D]">Em produção</p></div><div className="rounded-lg border border-[#DDE1E7] bg-white p-2"><b className="text-sm text-[#C77A08]">03</b><p className="mt-1 text-[9px] text-[#68707D]">Pendentes</p></div><div className="rounded-lg border border-[#DDE1E7] bg-white p-2"><b className="text-sm text-[#168A5B]">05</b><p className="mt-1 text-[9px] text-[#68707D]">Concluídos</p></div></div>
              <div className="mt-4 rounded-xl border border-[#DDE1E7] bg-white p-4"><div className="mb-3 flex justify-between text-[10px] font-bold text-[#68707D]"><span>SEG</span><span>TER</span><span>QUA</span><span>QUI</span><span>SEX</span></div><div className="grid grid-cols-5 gap-2">{['', 'Post institucional', '', 'Reels: bastidores', '', 'Carrossel de dicas', '', 'Vídeo do cliente', '', ''].map((post, index) => <div key={index} className={`h-12 rounded-md p-1 text-[8px] font-bold ${post ? index === 3 ? 'bg-[#EAF7F1] text-[#168A5B]' : index === 6 ? 'bg-[#EEF5FF] text-[#2563EB]' : 'bg-[#FFF0F2] text-[#9F1D2C]' : 'bg-[#F0F2F5]'}`}>{post}</div>)}</div></div>
              <div className="mt-4 flex items-center gap-3 rounded-lg bg-[#17191F] p-3 text-xs text-white"><span className="inline-flex size-6 items-center justify-center rounded bg-[#FF263D] font-black">N</span><span><b>IA Neiva</b> encontrou 3 cortes com potencial.</span></div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section className="border-y border-[#DDE1E7] bg-white"><div className="mx-auto grid max-w-7xl grid-cols-2 gap-y-5 px-6 py-7 text-sm font-bold text-[#68707D] sm:grid-cols-4"><span>PLANEJAMENTO</span><span>CLIENTES</span><span>TRELLO</span><span>VÍDEO + IA</span></div></section>

    <section id="recursos" className="mx-auto max-w-7xl px-6 py-24">
      <div className="max-w-3xl"><p className="text-xs font-bold tracking-[.16em] text-[#FF263D]">O QUE VOCÊ ENTREGA COM O NEIVA</p><h2 className="mt-4 text-4xl font-black tracking-[-.04em] sm:text-5xl">Pare de gerenciar conteúdo por mensagens, anotações soltas e memória.</h2><p className="mt-5 text-lg leading-8 text-[#68707D]">Tenha uma visão clara da operação e um processo repetível, do primeiro briefing até o conteúdo publicado.</p></div>
      <div className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-4">{features.map((feature) => <article key={feature.title} className="rounded-2xl border border-[#DDE1E7] bg-white p-6 transition hover:-translate-y-1 hover:shadow-lg"><span className={`inline-flex rounded-lg px-3 py-2 text-xs font-black ${feature.color}`}>{feature.number}</span><h3 className="mt-8 text-xl font-black">{feature.title}</h3><p className="mt-3 text-sm leading-6 text-[#68707D]">{feature.text}</p></article>)}</div>
    </section>

    <section id="como-funciona" className="bg-[#17191F] px-6 py-24 text-white"><div className="mx-auto grid max-w-7xl gap-16 lg:grid-cols-[.82fr_1.18fr]"><div><p className="text-xs font-bold tracking-[.16em] text-[#FF7C8A]">UM FLUXO QUE A EQUIPE ENTENDE</p><h2 className="mt-5 text-4xl font-black tracking-[-.04em] sm:text-6xl">Da ideia à entrega, sem perder contexto no caminho.</h2><p className="mt-6 max-w-md leading-7 text-slate-300">Você não compra apenas um calendário. Você ganha uma forma de trabalhar que torna prioridades, prazos e produção visíveis.</p></div><ol className="divide-y divide-white/15">{workflow.map(([title, description], index) => <li key={title} className="flex gap-5 py-7 first:pt-0"><span className="text-2xl font-black text-[#FF5265]">0{index + 1}</span><div><h3 className="text-xl font-bold">{title}</h3><p className="mt-2 max-w-xl leading-7 text-slate-300">{description}</p></div></li>)}</ol></div></section>

    <section id="planos" className="mx-auto max-w-7xl px-6 py-24"><div className="text-center"><p className="text-xs font-bold tracking-[.16em] text-[#FF263D]">PLANOS PARA O SEU RITMO</p><h2 className="mt-4 text-4xl font-black tracking-[-.04em] sm:text-5xl">Comece com o processo que sua operação precisa.</h2><p className="mx-auto mt-5 max-w-2xl text-[#68707D]">Todos os planos incluem o planner, clientes, calendário, Trello, estúdio de vídeo e uso em até dois computadores.</p></div><div className="mx-auto mt-12 grid max-w-4xl gap-5 md:grid-cols-2">{plans.map((plan, index) => <article key={plan.code} className={`relative rounded-2xl border p-8 ${index === 1 ? 'border-[#FF263D] bg-white shadow-xl shadow-red-100' : 'border-[#DDE1E7] bg-white'}`}>{index === 1 && <span className="absolute -top-3 right-6 rounded-full bg-[#FF263D] px-3 py-1 text-xs font-bold text-white">MAIS ESCOLHIDO</span>}<p className="text-sm font-bold text-[#68707D]">NEIVA</p><h3 className="mt-1 text-3xl font-black">{plan.name}</h3><p className="mt-7 text-5xl font-black tracking-tight"><small className="text-base">R$</small> {plan.price}<small className="text-base font-medium text-[#68707D]">/mês</small></p><p className="mt-2 text-sm text-[#68707D]">R$ {plan.annual}/mês no plano anual</p><CheckoutButton plan={plan.code} featured={index === 1} /><ul className="mt-7 space-y-3 border-t border-[#DDE1E7] pt-6 text-sm text-[#4E5560]"><li>✓ Planner e calendário completos</li><li>✓ Gestão de clientes e conteúdos</li><li>✓ Integração com Trello</li><li>✓ Estúdio de vídeo e legendas</li><li>✓ {plan.credits}</li></ul></article>)}</div><p className="mt-8 text-center text-sm text-[#68707D]">Créditos adicionais de IA podem ser comprados quando você precisar.</p></section>

    <section className="bg-[#FF263D] px-6 py-20 text-center text-white"><h2 className="mx-auto max-w-4xl text-4xl font-black tracking-[-.04em] sm:text-6xl">Seu conteúdo merece um processo que funciona todos os dias.</h2><p className="mx-auto mt-5 max-w-2xl text-lg text-red-100">Comece organizando o próximo conteúdo. O Neiva Planner ajuda com o resto.</p><a href="#planos" className="mt-8 inline-block rounded-lg bg-white px-7 py-4 font-bold text-[#9F1D2C] transition hover:bg-[#F7F8FA]">Escolher meu plano</a></section>

    <footer className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-10 text-sm text-[#68707D] md:flex-row md:items-center md:justify-between"><div className="flex items-center gap-2 font-bold text-[#17191F]"><Logo /> Neiva Planner</div><span>© 2026 Neiva Planner. Conteúdo com direção.</span><span>Termos · Privacidade</span></footer>
  </main>;
}
