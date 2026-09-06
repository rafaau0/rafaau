import { ActivationStatus } from '../components/activation-status';
import { CheckoutButton } from '../components/checkout-button';

const features = [
  {
    number: '01',
    title: 'Calendário editorial',
    text: 'Visualize o mês inteiro, distribua campanhas, posts e entregas antes de o prazo virar urgência.',
    color: 'bg-[#FFF0F2] text-[#FF263D]',
  },
  {
    number: '02',
    title: 'Clientes e demandas',
    text: 'Centralize briefing, status e data de cada conteúdo em uma rotina organizada.',
    color: 'bg-[#EEF5FF] text-[#2563EB]',
  },
  {
    number: '03',
    title: 'Trello conectado',
    text: 'Envie o planejamento para o quadro certo e deixe cada pessoa acompanhar o que acontece.',
    color: 'bg-[#EAF7F1] text-[#168A5B]',
  },
  {
    number: '04',
    title: 'Vídeo e IA rafaau',
    text: 'Transcreva vídeos, encontre trechos promissores e transforme material longo em novas ideias.',
    color: 'bg-[#FFF6E8] text-[#C77A08]',
  },
];

const workflow = [
  [
    'Planeje',
    'Crie pautas, defina clientes, formatos e datas no calendário visual.',
  ],
  [
    'Produza',
    'Organize a produção e abra o DaVinci Resolve diretamente pelo rafaau.',
  ],
  [
    'Distribua',
    'Envie para o Trello e acompanhe o que está pronto, em andamento ou pendente.',
  ],
];

const plans = [
  {
    code: 'free',
    name: 'Grátis',
    price: '0',
    credits: 'Não incluída',
    use: 'Para conhecer o planejamento editorial.',
    features: ['1 cliente e 15 conteúdos por mês', '1 PDF por mês', 'Calendário e dashboard', 'Sem Trello ou integração DaVinci'],
  },
  {
    code: 'essencial',
    name: 'Essencial',
    price: '49,90',
    credits: '20',
    use: 'Para quem analisa alguns vídeos por mês.',
    features: ['Até 10 clientes', 'Conteúdos e PDFs ilimitados', 'Trello e integração DaVinci', 'Uso em até 2 computadores'],
  },
  {
    code: 'pro',
    name: 'Pro',
    price: '89,90',
    credits: '80',
    use: 'Para quem produz para vários clientes ou publica toda semana.',
    features: ['Clientes e conteúdos ilimitados', 'Trello e integração DaVinci', 'Maior volume de IA', 'Uso em até 3 computadores'],
  },
];

const faqs = [
  [
    'O que é um crédito de IA?',
    'Um crédito equivale a uma análise de vídeo pela IA rafaau para encontrar cortes e ideias aproveitáveis. Os créditos são renovados mensalmente conforme o seu plano.',
  ],
  [
    'Como funciona o cancelamento?',
    'Você pode cancelar quando quiser. O acesso permanece disponível até o fim do período já pago, sem multa de cancelamento.',
  ],
  [
    'Em quantos computadores posso usar?',
    'O plano Grátis permite 1 computador, o Essencial permite 2 e o Pro permite até 3 computadores.',
  ],
  [
    'Os dados são compartilhados entre computadores?',
    'Não. Cada conta pode ser usada no número de computadores permitido pelo plano, mas os dados de planejamento ficam armazenados localmente em cada computador e não são sincronizados.',
  ],
];

const DOWNLOAD_URL =
  'https://github.com/rafaau0/rafaau/releases/download/v1.0.0/NeivaPlanner_v1.exe';

function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <span
      className={`inline-flex items-center justify-center rounded-xl bg-[#FF263D] font-black text-white ${compact ? 'size-7 text-sm' : 'size-9 text-lg'}`}
    >
      r
    </span>
  );
}

function ProductPreview() {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-[#DDE1E7] bg-[#17191F] p-3 shadow-2xl shadow-slate-900/10">
      <div className="absolute -left-10 top-10 size-48 rounded-full bg-[#FF263D]/20 blur-3xl" />
      <div className="relative overflow-hidden rounded-xl border border-white/10 bg-[#20232B]">
        <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
          <div className="flex gap-1.5">
            <i className="size-2 rounded-full bg-[#FF5265]" />
            <i className="size-2 rounded-full bg-[#F2B84B]" />
            <i className="size-2 rounded-full bg-[#48B887]" />
          </div>
          <span className="text-[10px] font-bold tracking-[.16em] text-slate-400">
            VISÃO GERAL DO APLICATIVO
          </span>
        </div>
        <div className="grid gap-4 p-5 sm:grid-cols-[124px_1fr]">
          <div className="rounded-lg bg-white/5 p-3 text-xs font-bold text-slate-400">
            <div className="mb-5 flex items-center gap-2 text-white">
              <Logo compact /> rafaau
            </div>
            <p className="rounded-md bg-[#FF263D]/20 px-2 py-2 text-[#FF9AA5]">
              Planejamento
            </p>
            <p className="mt-3 px-2">Conteúdos</p>
            <p className="mt-3 px-2">Vídeos & IA</p>
            <p className="mt-3 px-2">Clientes</p>
          </div>
          <div className="min-w-0">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-slate-400">Passo 01</p>
                <h2 className="mt-1 text-lg font-black text-white">
                  Criar conteúdo
                </h2>
              </div>
              <span className="rounded-full bg-[#FF263D] px-3 py-1 text-[10px] font-bold text-white">
                NOVO POST
              </span>
            </div>
            <div className="mt-4 rounded-lg bg-white p-3 text-xs">
              <div className="flex items-center justify-between">
                <b>Reels: bastidores da marca</b>
                <span className="rounded-full bg-[#FFF6E8] px-2 py-1 text-[#C77A08]">
                  Em produção
                </span>
              </div>
              <div className="mt-3 h-2 rounded-full bg-[#E7EAF0]">
                <div className="h-2 w-2/3 rounded-full bg-[#FF263D]" />
              </div>
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <div className="rounded-lg border border-white/10 p-3">
                <p className="text-[10px] font-bold text-slate-400">PASSO 02</p>
                <p className="mt-2 text-sm font-bold text-white">
                  Mover status
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  Pronto para revisão
                </p>
              </div>
              <div className="rounded-lg bg-[#FF263D] p-3">
                <p className="text-[10px] font-bold text-red-100">
                  PASSO 03 · IA
                </p>
                <p className="mt-2 text-sm font-bold text-white">
                  3 cortes encontrados
                </p>
                <p className="mt-1 text-xs text-red-100">Analisar vídeo</p>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div className="relative mt-3 flex items-center gap-3 px-2 pb-1 text-xs text-slate-300">
        <span className="inline-flex size-7 items-center justify-center rounded-full bg-[#FF263D] text-white">
          ▶
        </span>
        <span>Prévia ilustrativa da interface</span>
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <main className="min-h-screen bg-[#F7F8FA] text-[#17191F]">
      <ActivationStatus />
      <nav className="mx-auto flex h-20 max-w-7xl items-center justify-between px-6">
        <a
          href="#inicio"
          className="flex items-center gap-3 font-black tracking-tight"
        >
          <Logo />
          <span>rafaau</span>
        </a>
        <div className="hidden items-center gap-7 text-sm font-medium text-[#68707D] md:flex">
          <a className="hover:text-[#17191F]" href="#recursos">
            O que entrega
          </a>
          <a className="hover:text-[#17191F]" href="#como-funciona">
            Como funciona
          </a>
          <a className="hover:text-[#17191F]" href="#planos">
            Planos
          </a>
          <a className="hover:text-[#17191F]" href="#download">
            Baixar app
          </a>
        </div>
        <a
          href="#planos"
          className="rounded-lg bg-[#FF263D] px-4 py-2.5 text-sm font-bold text-white shadow-sm transition hover:bg-[#D91E32]"
        >
          Começar agora
        </a>
      </nav>

      <section
        id="inicio"
        className="mx-auto grid max-w-7xl gap-12 px-6 pb-20 pt-12 lg:grid-cols-[.95fr_1.05fr] lg:items-center lg:pt-20"
      >
        <div>
          <p className="mb-6 inline-flex rounded-full bg-[#FFF0F2] px-4 py-2 text-xs font-bold tracking-[.12em] text-[#9F1D2C]">
            PLANEJAMENTO DE CONTEÚDO, SEM IMPROVISO
          </p>
          <h1 className="max-w-3xl text-5xl font-black leading-[.98] tracking-[-.055em] sm:text-6xl lg:text-7xl">
            Você atende vários clientes e ainda se perde entre{' '}
            <span className="text-[#FF263D]">
              WhatsApp, planilhas e anotações?
            </span>
          </h1>
          <p className="mt-7 max-w-2xl text-lg leading-8 text-[#68707D]">
            O rafaau é para criadores, freelancers e pequenas agências que
            precisam transformar demandas soltas em uma operação clara: o que
            criar, para quem, em qual etapa e quando entregar.
          </p>
          <div className="mt-9 flex flex-wrap gap-3">
            <a
              href="#planos"
              className="rounded-lg bg-[#FF263D] px-6 py-4 font-bold text-white shadow-lg shadow-red-200 transition hover:bg-[#D91E32]"
            >
              Quero organizar meu conteúdo
            </a>
            <a
              href="#recursos"
              className="rounded-lg border border-[#DDE1E7] bg-white px-6 py-4 font-bold text-[#17191F] transition hover:bg-[#F0F2F5]"
            >
              Ver o que está incluso
            </a>
          </div>
          <p className="mt-4 text-sm font-medium text-[#68707D]">
            Comece no plano Grátis e faça upgrade quando precisar.
          </p>
          <div className="mt-5 flex flex-wrap gap-x-6 gap-y-2 text-sm font-medium text-[#68707D]">
            <span>✓ Sem organização manual</span>
            <span>✓ Até 2 computadores</span>
          </div>
        </div>
        <div className="relative mx-auto w-full max-w-xl">
          <div className="absolute -left-8 top-14 h-52 w-52 rounded-full bg-[#FF263D]/10 blur-3xl" />
          <ProductPreview />
        </div>
      </section>

      <section className="border-y border-[#DDE1E7] bg-white">
        <div className="mx-auto grid max-w-7xl grid-cols-2 gap-y-5 px-6 py-7 text-sm font-bold text-[#68707D] sm:grid-cols-4">
          <span>PLANEJAMENTO</span>
          <span>CLIENTES</span>
          <span>TRELLO</span>
          <span>VÍDEO + IA</span>
        </div>
      </section>

      <section id="recursos" className="mx-auto max-w-7xl px-6 py-24">
        <div className="max-w-3xl">
          <p className="text-xs font-bold tracking-[.16em] text-[#FF263D]">
            O QUE O RAFAAU ENTREGA
          </p>
          <h2 className="mt-4 text-4xl font-black tracking-[-.04em] sm:text-5xl">
            Pare de gerenciar conteúdo por mensagens, anotações soltas e
            memória.
          </h2>
          <p className="mt-5 text-lg leading-8 text-[#68707D]">
            Tenha uma visão clara da operação e um processo repetível, do
            primeiro briefing até o conteúdo publicado.
          </p>
        </div>
        <div className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {features.map((feature) => (
            <article
              key={feature.title}
              className="rounded-2xl border border-[#DDE1E7] bg-white p-6 transition hover:-translate-y-1 hover:shadow-lg"
            >
              <span
                className={`inline-flex rounded-lg px-3 py-2 text-xs font-black ${feature.color}`}
              >
                {feature.number}
              </span>
              <h3 className="mt-8 text-xl font-black">{feature.title}</h3>
              <p className="mt-3 text-sm leading-6 text-[#68707D]">
                {feature.text}
              </p>
            </article>
          ))}
        </div>
      </section>

      <section
        id="como-funciona"
        className="bg-[#17191F] px-6 py-24 text-white"
      >
        <div className="mx-auto grid max-w-7xl gap-16 lg:grid-cols-[.82fr_1.18fr]">
          <div>
            <p className="text-xs font-bold tracking-[.16em] text-[#FF7C8A]">
              UM FLUXO QUE A EQUIPE ENTENDE
            </p>
            <h2 className="mt-5 text-4xl font-black tracking-[-.04em] sm:text-6xl">
              Da ideia à entrega, sem perder contexto no caminho.
            </h2>
            <p className="mt-6 max-w-md leading-7 text-slate-300">
              Você não compra apenas um calendário. Você ganha uma forma de
              trabalhar que torna prioridades, prazos e produção visíveis.
            </p>
          </div>
          <ol className="divide-y divide-white/15">
            {workflow.map(([title, description], index) => (
              <li key={title} className="flex gap-5 py-7 first:pt-0">
                <span className="text-2xl font-black text-[#FF5265]">
                  0{index + 1}
                </span>
                <div>
                  <h3 className="text-xl font-bold">{title}</h3>
                  <p className="mt-2 max-w-xl leading-7 text-slate-300">
                    {description}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section id="planos" className="mx-auto max-w-7xl px-6 py-24">
        <div className="text-center">
          <p className="text-xs font-bold tracking-[.16em] text-[#FF263D]">
            PLANOS PARA O SEU RITMO
          </p>
          <h2 className="mt-4 text-4xl font-black tracking-[-.04em] sm:text-5xl">
            Comece com o processo que sua operação precisa.
          </h2>
          <p className="mx-auto mt-5 max-w-2xl text-[#68707D]">
            Comece gratuitamente e avance quando precisar de mais clientes,
            automação, vídeo e inteligência artificial.
          </p>
        </div>
        <div className="mx-auto mt-12 grid max-w-6xl gap-5 md:grid-cols-3">
          {plans.map((plan, index) => (
            <article
              key={plan.code}
              className={`relative rounded-2xl border p-8 ${index === 1 ? 'border-[#FF263D] bg-white shadow-xl shadow-red-100' : 'border-[#DDE1E7] bg-white'}`}
            >
              {index === 1 && (
                <span className="absolute -top-3 right-6 rounded-full bg-[#FF263D] px-3 py-1 text-xs font-bold text-white">
                  MAIS ESCOLHIDO
                </span>
              )}
              <p className="text-sm font-bold text-[#68707D]">RAFAAU</p>
              <h3 className="mt-1 text-3xl font-black">{plan.name}</h3>
              <p className="mt-7 text-5xl font-black tracking-tight">
                <small className="text-base">R$</small> {plan.price}
                <small className="text-base font-medium text-[#68707D]">
                  /mês
                </small>
              </p>
              <p className="mt-2 text-sm text-[#68707D]">
                {plan.code === 'free' ? 'Grátis para sempre' : 'Cobrança mensal; cancele quando quiser'}
              </p>
              <div
                className={`mt-6 rounded-xl p-4 ${index === 1 ? 'bg-[#FFF0F2]' : 'bg-[#F0F2F5]'}`}
              >
                <p className="text-xs font-bold tracking-wide text-[#9F1D2C]">
                  CRÉDITOS DE IA
                </p>
                <p className="mt-1 text-3xl font-black">
                  {plan.credits}{' '}
                  {plan.code !== 'free' && <span className="text-sm font-semibold text-[#68707D]">por mês</span>}
                </p>
                <p className="mt-2 text-sm leading-5 text-[#4E5560]">
                  {plan.use} {plan.code !== 'free' && '1 crédito = 1 análise de vídeo para sugerir cortes.'}
                </p>
              </div>
              <CheckoutButton plan={plan.code} featured={index === 1} />
              <ul className="mt-7 space-y-3 border-t border-[#DDE1E7] pt-6 text-sm text-[#4E5560]">
                {plan.features.map((feature) => <li key={feature}>✓ {feature}</li>)}
              </ul>
            </article>
          ))}
        </div>
        <p className="mt-8 text-center text-sm text-[#68707D]">
          O Essencial é a melhor escolha para social medias autônomos. O Pro atende operações de maior volume.
        </p>
      </section>

      <section id="download" className="mx-auto max-w-7xl px-6 py-20">
        <div className="flex flex-col gap-7 rounded-3xl border border-[#DDE1E7] bg-white p-8 shadow-sm sm:p-10 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-bold tracking-[.16em] text-[#FF263D]">
              APLICATIVO PARA WINDOWS
            </p>
            <h2 className="mt-3 text-3xl font-black tracking-[-.04em] sm:text-4xl">
              Já assinou? Baixe o rafaau.
            </h2>
            <p className="mt-3 max-w-2xl leading-7 text-[#68707D]">
              Instale o aplicativo no seu computador e comece a organizar
              clientes, conteúdos e produção. O download é feito pelo release
              oficial do rafaau.
            </p>
          </div>
          <div className="shrink-0">
            <a
              href={DOWNLOAD_URL}
              target="_blank"
              rel="noreferrer"
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-[#17191F] px-6 py-4 font-bold text-white transition hover:bg-[#343841] sm:w-auto"
            >
              <span aria-hidden="true">↓</span> Baixar para Windows
            </a>
            <p className="mt-3 text-center text-xs text-[#68707D]">
              Arquivo .exe • Windows 10 ou superior
            </p>
          </div>
        </div>
      </section>

      <section
        id="faq"
        className="border-y border-[#DDE1E7] bg-white px-6 py-24"
      >
        <div className="mx-auto grid max-w-7xl gap-12 lg:grid-cols-[.7fr_1.3fr]">
          <div>
            <p className="text-xs font-bold tracking-[.16em] text-[#FF263D]">
              PERGUNTAS FREQUENTES
            </p>
            <h2 className="mt-4 text-4xl font-black tracking-[-.04em]">
              Sem letra pequena.
            </h2>
            <p className="mt-5 leading-7 text-[#68707D]">
              Tudo o que você precisa saber antes de começar a organizar sua
              operação.
            </p>
          </div>
          <div className="divide-y divide-[#DDE1E7] border-y border-[#DDE1E7]">
            {faqs.map(([question, answer]) => (
              <details key={question} className="group py-5">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-bold">
                  <span>{question}</span>
                  <span className="text-xl text-[#FF263D] transition group-open:rotate-45">
                    +
                  </span>
                </summary>
                <p className="max-w-2xl pt-3 leading-7 text-[#68707D]">
                  {answer}
                </p>
              </details>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-[#FF263D] px-6 py-20 text-white">
        <div className="mx-auto grid max-w-6xl gap-10 lg:grid-cols-[1.2fr_.8fr] lg:items-center">
          <div>
            <p className="text-xs font-bold tracking-[.16em] text-red-100">
              PRONTO PARA SAIR DO CAOS?
            </p>
            <h2 className="mt-4 text-4xl font-black tracking-[-.04em] sm:text-6xl">
              Seu conteúdo merece um processo que funciona todos os dias.
            </h2>
            <p className="mt-7 max-w-2xl text-lg leading-7 text-red-50">
              Planeje conteúdos, acompanhe o andamento e concentre cada cliente
              em um fluxo local e organizado.
            </p>
          </div>
          <div className="rounded-2xl bg-white/10 p-7 backdrop-blur-sm">
            <p className="text-lg font-bold">Comece pelo plano Grátis.</p>
            <p className="mt-2 text-sm leading-6 text-red-100">
              Conheça o planejamento sem cobrança e escolha um plano pago
              quando precisar de mais recursos.
            </p>
            <a
              href="#planos"
              className="mt-6 block rounded-lg bg-white px-7 py-4 text-center font-bold text-[#9F1D2C] transition hover:bg-[#F7F8FA]"
            >
              Escolher meu plano
            </a>
          </div>
        </div>
      </section>

      <footer className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-10 text-sm text-[#68707D] md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2 font-black text-[#17191F]">
          <Logo /> rafaau
        </div>
        <span>© 2026 rafaau. Conteúdo com direção.</span>
        <span>Termos · Privacidade</span>
      </footer>
    </main>
  );
}
