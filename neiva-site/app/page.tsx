import { ActivationStatus } from '../components/activation-status';
import { CheckoutButton } from '../components/checkout-button';

const plans = [
  {
    code: 'free',
    name: 'Grátis',
    price: '0',
    credits: 'Sem créditos de IA',
    note: 'Para organizar o primeiro cliente.',
    features: [
      '1 cliente e 15 conteúdos por mês',
      '1 PDF por mês',
      'Calendário e dashboard',
      '1 computador',
    ],
  },
  {
    code: 'essencial',
    name: 'Essencial',
    price: '49,90',
    credits: '20 créditos de IA / mês',
    note: 'Para uma rotina criativa constante.',
    features: [
      'Até 10 clientes',
      'Conteúdos e PDFs ilimitados',
      'Trello e integração DaVinci',
      'Até 2 computadores',
    ],
  },
  {
    code: 'pro',
    name: 'Pro',
    price: '89,90',
    credits: '80 créditos de IA / mês',
    note: 'Para quem trabalha em maior volume.',
    features: [
      'Clientes e conteúdos ilimitados',
      'Trello e integração DaVinci',
      'Maior volume de IA',
      'Até 3 computadores',
    ],
  },
];

const faqs = [
  [
    'O que é um crédito de IA?',
    'Um crédito equivale a uma análise de vídeo pela IA do Vydra para encontrar cortes e ideias aproveitáveis. Os créditos são renovados mensalmente conforme o seu plano.',
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
      className={`inline-flex items-center gap-2.5 font-black tracking-[-.04em] ${compact ? 'text-sm' : 'text-xl'}`}
    >
      <svg
        className={compact ? 'size-6' : 'size-8'}
        viewBox="0 0 32 32"
        aria-hidden="true"
      >
        <path d="M4 5h6l6 15L22 5h6L17.8 27h-4.1L4 5Z" fill="#6C5CE7" />
        <path d="m11.5 5 4.6 11L20.5 5h-9Z" fill="#18181F" />
      </svg>
      {!compact && <span>Vydra</span>}
    </span>
  );
}

function ProductPreview() {
  return (
    <div className="border border-[#E7E7EE] bg-white shadow-[0_24px_60px_rgba(24,24,31,.08)]">
      <div className="flex h-10 items-center justify-between border-b border-[#E7E7EE] px-4">
        <div className="flex items-center gap-2">
          <Logo compact />
          <span className="text-xs font-bold">Vydra</span>
        </div>
        <span className="text-[11px] text-[#6E6E7A]">
          Setembro · visão editorial
        </span>
      </div>
      <div className="grid grid-cols-[82px_1fr] sm:grid-cols-[132px_1fr]">
        <aside className="border-r border-[#E7E7EE] p-3 text-[11px] text-[#6E6E7A] sm:p-4">
          <p className="border-l-2 border-[#6C5CE7] py-1 pl-2 font-semibold text-[#18181F]">
            Visão geral
          </p>
          <p className="mt-4 pl-2">Clientes</p>
          <p className="mt-4 pl-2">Planejamento</p>
          <p className="mt-4 pl-2">Vídeo</p>
        </aside>
        <div className="min-w-0 p-4 sm:p-6">
          <div className="flex items-end justify-between border-b border-[#E7E7EE] pb-4">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[.16em] text-[#6C5CE7]">
                Semana 36
              </p>
              <p className="mt-1 text-lg font-semibold">
                O trabalho em movimento
              </p>
            </div>
            <span className="hidden bg-[#EEEAFE] px-3 py-1.5 text-[10px] font-semibold text-[#5848D6] sm:block">
              + Novo conteúdo
            </span>
          </div>
          <div className="mt-4 grid grid-cols-3 border-y border-[#E7E7EE] text-[10px] sm:text-xs">
            {[
              ['12', 'entregas'],
              ['04', 'clientes'],
              ['09', 'concluídas'],
            ].map(([value, label]) => (
              <div
                key={label}
                className="border-r border-[#E7E7EE] px-2 py-3 last:border-r-0"
              >
                <b className="block text-lg">{value}</b>
                <span className="text-[#6E6E7A]">{label}</span>
              </div>
            ))}
          </div>
          <div className="mt-4 space-y-2 text-[10px] sm:text-xs">
            {[
              ['Identidade visual · Aurora', 'Hoje', 'Em revisão'],
              ['Carrossel lançamento · Noma', 'Qua, 09', 'Em produção'],
              ['Calendário editorial · Lume', 'Sex, 11', 'Aprovado'],
            ].map(([title, date, status], index) => (
              <div
                key={title}
                className="grid grid-cols-[1fr_auto] items-center border-b border-[#E7E7EE] py-2.5"
              >
                <div>
                  <p className="font-semibold">{title}</p>
                  <p className="mt-1 text-[#6E6E7A]">{date}</p>
                </div>
                <span
                  className={
                    index === 2
                      ? 'text-[#22C55E]'
                      : index === 0
                        ? 'text-[#6C5CE7]'
                        : 'text-[#6E6E7A]'
                  }
                >
                  ● {status}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function ClientWorkspace() {
  return (
    <div className="border-y border-[#E7E7EE] bg-white">
      <div className="flex items-center justify-between border-b border-[#E7E7EE] px-5 py-4">
        <div>
          <p className="text-xs text-[#6E6E7A]">Cliente selecionado</p>
          <p className="mt-1 font-semibold">Estúdio Aurora</p>
        </div>
        <span className="text-xs font-medium text-[#22C55E]">
          ● Contrato ativo
        </span>
      </div>
      <div className="grid sm:grid-cols-[1fr_1.15fr]">
        <div className="border-b border-[#E7E7EE] p-5 sm:border-b-0 sm:border-r">
          <p className="text-xs font-semibold uppercase tracking-[.15em] text-[#6E6E7A]">
            Contato
          </p>
          <dl className="mt-5 space-y-4 text-sm">
            <div>
              <dt className="text-[#6E6E7A]">Responsável</dt>
              <dd className="mt-1 font-medium">Marina Costa</dd>
            </div>
            <div>
              <dt className="text-[#6E6E7A]">Próxima entrega</dt>
              <dd className="mt-1 font-medium">12 de setembro</dd>
            </div>
            <div>
              <dt className="text-[#6E6E7A]">Valor mensal</dt>
              <dd className="mt-1 font-medium">R$ 2.400,00</dd>
            </div>
          </dl>
        </div>
        <div className="p-5">
          <p className="text-xs font-semibold uppercase tracking-[.15em] text-[#6E6E7A]">
            Este mês
          </p>
          <div className="mt-5 space-y-3 text-sm">
            {[
              ['Direção criativa', 'Concluído'],
              ['Kit de lançamento', 'Em revisão'],
              ['6 peças sociais', 'Em produção'],
            ].map(([task, status], index) => (
              <div
                key={task}
                className="flex items-center justify-between border-b border-[#E7E7EE] pb-3"
              >
                <span>{task}</span>
                <span
                  className={
                    index === 0
                      ? 'text-[#22C55E]'
                      : index === 1
                        ? 'text-[#6C5CE7]'
                        : 'text-[#6E6E7A]'
                  }
                >
                  {status}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function VideoTimeline() {
  return (
    <div className="border border-[#E7E7EE] bg-[#18181F] p-5 text-white sm:p-7">
      <div className="flex items-center justify-between border-b border-white/15 pb-4 text-xs">
        <span>DaVinci Resolve</span>
        <span className="text-[#A8A8B3]">Integração local</span>
      </div>
      <div className="mt-8 flex h-28 items-center justify-center border border-white/10 bg-[#202029]">
        <span className="inline-flex size-10 items-center justify-center rounded-full border border-white/30">
          ▶
        </span>
      </div>
      <div className="mt-5 flex h-12 gap-1 border-y border-white/15 py-2">
        {[2, 1, 3, 2, 4, 1, 2, 3, 1, 2].map((width, index) => (
          <span
            key={index}
            style={{ flex: width }}
            className={
              index === 4 || index === 5 ? 'bg-[#6C5CE7]' : 'bg-white/20'
            }
          />
        ))}
      </div>
      <div className="mt-4 flex justify-between gap-4 text-xs text-[#A8A8B3]">
        <span>Silêncios identificados</span>
        <span className="text-right text-white">
          Legenda preparada localmente
        </span>
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <main className="min-h-screen bg-[#F8F8FB] text-[#18181F]">
      <ActivationStatus />
      <nav
        className="mx-auto flex h-20 max-w-[1180px] items-center justify-between border-b border-[#E7E7EE] px-5 sm:px-8"
        aria-label="Navegação principal"
      >
        <a href="#inicio" aria-label="Vydra, início">
          <Logo />
        </a>
        <div className="hidden items-center gap-7 text-sm text-[#6E6E7A] md:flex">
          <a className="transition hover:text-[#18181F]" href="#produto">
            Produto
          </a>
          <a className="transition hover:text-[#18181F]" href="#fluxo">
            Como funciona
          </a>
          <a className="transition hover:text-[#18181F]" href="#planos">
            Planos
          </a>
          <a className="transition hover:text-[#18181F]" href="#download">
            Dawnload
          </a>
        </div>
        <a
          href="#planos"
          className="bg-[#6C5CE7] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#5848D6]"
        >
          Começar agora
        </a>
      </nav>

      <section
        id="inicio"
        className="mx-auto grid max-w-[1180px] gap-12 px-5 pb-24 pt-12 sm:px-8 lg:grid-cols-[.78fr_1.22fr] lg:items-center lg:pt-20"
      >
        <div>
          <p className="mb-8 border-l-2 border-[#6C5CE7] pl-3 text-xs font-semibold uppercase tracking-[.18em] text-[#6E6E7A]">
            Ferramenta de trabalho para criativos
          </p>
          <h1 className="max-w-xl text-4xl font-semibold leading-[1.02] tracking-[-.05em] sm:text-5xl lg:text-[4rem]">
            Menos abas abertas. Mais trabalho concluído.
          </h1>
          <p className="mt-7 max-w-lg text-lg leading-8 text-[#6E6E7A]">
            O Vydra organiza clientes, contratos, conteúdo e produção em um só
            lugar — para quem cria no computador todos os dias.
          </p>
          <div className="mt-9 flex flex-wrap gap-3">
            <a
              href="#planos"
              className="bg-[#6C5CE7] px-6 py-3.5 font-semibold text-white transition hover:bg-[#5848D6]"
            >
              Começar com o Vydra
            </a>
            <a
              href="#produto"
              className="border border-[#E7E7EE] bg-white px-6 py-3.5 font-semibold transition hover:border-[#6C5CE7] hover:text-[#5848D6]"
            >
              Conhecer a ferramenta
            </a>
          </div>
          <p className="mt-5 max-w-sm border-t border-[#E7E7EE] pt-4 text-sm text-[#6E6E7A]">
            Plano gratuito disponível · aplicativo para Windows
          </p>
        </div>
        <div className="relative mx-auto w-full max-w-2xl lg:translate-y-6">
          <ProductPreview />
          <p className="mt-3 text-right text-xs text-[#6E6E7A]">
            01 / Controle sem ruído visual
          </p>
        </div>
      </section>

      <section className="border-y border-[#E7E7EE] bg-white">
        <div className="mx-auto grid max-w-[1180px] grid-cols-2 divide-x divide-y divide-[#E7E7EE] px-5 sm:px-8 md:grid-cols-4 md:divide-y-0">
          {[
            'Planejamento editorial',
            'Gestão de clientes',
            'Trello conectado',
            'Vídeo no DaVinci',
          ].map((item, index) => (
            <p
              key={item}
              className="py-5 pl-4 text-xs font-semibold uppercase tracking-[.12em] text-[#6E6E7A] first:pl-0 md:text-center"
            >
              0{index + 1} · {item}
            </p>
          ))}
        </div>
      </section>

      <section
        id="produto"
        className="mx-auto max-w-[1180px] px-5 py-24 sm:px-8 lg:py-32"
      >
        <div className="grid gap-12 lg:grid-cols-[.7fr_1.3fr] lg:items-start">
          <div className="lg:sticky lg:top-12">
            <p className="text-xs font-semibold uppercase tracking-[.18em] text-[#6C5CE7]">
              Clientes sem improviso
            </p>
            <h2 className="mt-5 max-w-md text-3xl font-semibold leading-tight tracking-[-.04em] sm:text-5xl">
              A relação inteira com o cliente, não apenas a próxima tarefa.
            </h2>
            <p className="mt-6 max-w-md leading-7 text-[#6E6E7A]">
              Cadastro, contato, contrato e produção permanecem próximos. Você
              enxerga o que foi combinado e o que precisa acontecer sem procurar
              em cinco lugares.
            </p>
          </div>
          <div>
            <ClientWorkspace />
            <div className="mt-8 grid gap-8 border-t border-[#E7E7EE] pt-8 sm:grid-cols-2">
              <div>
                <span className="text-3xl font-semibold">30 dias</span>
                <p className="mt-2 text-sm leading-6 text-[#6E6E7A]">
                  Aviso claro para contratos próximos do vencimento.
                </p>
              </div>
              <div>
                <span className="text-3xl font-semibold">1 visão</span>
                <p className="mt-2 text-sm leading-6 text-[#6E6E7A]">
                  Receita contratada, clientes ativos e entregas no dashboard.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="fluxo" className="border-y border-[#E7E7EE] bg-white">
        <div className="mx-auto grid max-w-[1180px] gap-14 px-5 py-24 sm:px-8 lg:grid-cols-[1.2fr_.8fr] lg:items-center lg:py-32">
          <VideoTimeline />
          <div>
            <p className="text-xs font-semibold uppercase tracking-[.18em] text-[#6C5CE7]">
              Do plano ao corte
            </p>
            <h2 className="mt-5 text-3xl font-semibold leading-tight tracking-[-.04em] sm:text-5xl">
              O Vydra acompanha seu fluxo. Não tenta substituí-lo.
            </h2>
            <ol className="mt-10 border-t border-[#E7E7EE]">
              {[
                [
                  '01',
                  'Planeje',
                  'Organize pautas, formatos e datas em um calendário mensal.',
                ],
                [
                  '02',
                  'Produza',
                  'Abra o DaVinci Resolve e prepare cortes e legendas a partir da timeline.',
                ],
                [
                  '03',
                  'Compartilhe',
                  'Envie o planejamento ao quadro do Trello que seu cliente já acompanha.',
                ],
              ].map(([number, title, text]) => (
                <li
                  key={title}
                  className="grid grid-cols-[2.5rem_1fr] gap-3 border-b border-[#E7E7EE] py-5"
                >
                  <span className="text-xs text-[#6C5CE7]">{number}</span>
                  <div>
                    <h3 className="font-semibold">{title}</h3>
                    <p className="mt-2 text-sm leading-6 text-[#6E6E7A]">
                      {text}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>

      <section
        id="planos"
        className="mx-auto max-w-[1180px] px-5 py-24 sm:px-8 lg:py-32"
      >
        <div className="grid gap-8 border-b border-[#E7E7EE] pb-10 md:grid-cols-[.8fr_1.2fr] md:items-end">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[.18em] text-[#6C5CE7]">
              Planos
            </p>
            <h2 className="mt-5 text-4xl font-semibold tracking-[-.04em] sm:text-5xl">
              Escolha pelo seu ritmo.
            </h2>
          </div>
          <p className="max-w-xl leading-7 text-[#6E6E7A] md:justify-self-end">
            Comece gratuitamente. Quando o volume aumentar, avance sem mudar sua
            forma de trabalhar.
          </p>
        </div>
        <div className="grid md:grid-cols-3">
          {plans.map((plan, index) => (
            <article
              key={plan.code}
              className={`relative border-b border-[#E7E7EE] px-1 py-10 md:border-b-0 md:border-r md:px-7 ${index === 0 ? 'md:pl-0' : ''} ${index === 2 ? 'md:border-r-0 md:pr-0' : ''}`}
            >
              {index === 1 && (
                <span className="absolute inset-x-7 top-0 h-0.5 bg-[#6C5CE7]" />
              )}
              <p className="text-xs font-semibold uppercase tracking-[.16em] text-[#6E6E7A]">
                Vydra {plan.name}
              </p>
              <p className="mt-6 text-4xl font-semibold tracking-[-.04em]">
                <small className="text-base font-normal">R$</small> {plan.price}
                <small className="text-sm font-normal text-[#6E6E7A]">
                  {' '}
                  / mês
                </small>
              </p>
              <p className="mt-3 min-h-12 text-sm leading-6 text-[#6E6E7A]">
                {plan.note}
              </p>
              <p className="mt-5 border-y border-[#E7E7EE] py-4 text-sm font-semibold text-[#5848D6]">
                {plan.credits}
              </p>
              <CheckoutButton plan={plan.code} featured={index === 1} />
              <ul className="mt-7 space-y-3 text-sm text-[#6E6E7A]">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex gap-2">
                    <span className="text-[#22C55E]">✓</span>
                    {feature}
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
        <p className="mt-8 text-sm text-[#6E6E7A]">
          1 crédito de IA equivale a uma análise de vídeo para sugerir cortes.
        </p>
      </section>

      <section id="download" className="bg-[#18181F] text-white">
        <div className="mx-auto grid max-w-[1180px] gap-10 px-5 py-20 sm:px-8 md:grid-cols-[1fr_auto] md:items-end lg:py-24">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[.18em] text-[#A49BEA]">
              Aplicativo para Windows
            </p>
            <h2 className="mt-5 max-w-2xl text-3xl font-semibold leading-tight tracking-[-.04em] sm:text-5xl">
              Seu espaço de trabalho, instalado onde você trabalha.
            </h2>
            <p className="mt-5 max-w-xl leading-7 text-[#B4B4C0]">
              Baixe o aplicativo, entre com sua conta e mantenha clientes,
              conteúdo e produção organizados localmente.
            </p>
          </div>
          <div>
            <a
              href={DOWNLOAD_URL}
              target="_blank"
              rel="noreferrer"
              className="inline-flex w-full items-center justify-center bg-[#6C5CE7] px-7 py-4 font-semibold transition hover:bg-[#5848D6] sm:w-auto"
            >
              Baixar Vydra para Windows{' '}
              <span className="ml-3" aria-hidden="true">
                ↓
              </span>
            </a>
            <p className="mt-3 text-center text-xs text-[#A8A8B3]">
              Arquivo .exe · Windows 10 ou superior
            </p>
          </div>
        </div>
      </section>

      <section
        id="faq"
        className="mx-auto grid max-w-[1180px] gap-12 px-5 py-24 sm:px-8 lg:grid-cols-[.55fr_1.45fr] lg:py-32"
      >
        <div>
          <p className="text-xs font-semibold uppercase tracking-[.18em] text-[#6C5CE7]">
            Antes de começar
          </p>
          <h2 className="mt-5 text-3xl font-semibold tracking-[-.04em]">
            Perguntas diretas.
          </h2>
        </div>
        <div className="border-t border-[#E7E7EE]">
          {faqs.map(([question, answer]) => (
            <details
              key={question}
              className="group border-b border-[#E7E7EE] py-6"
            >
              <summary className="flex cursor-pointer list-none items-center justify-between gap-5 text-lg font-semibold">
                <span>{question}</span>
                <span
                  className="text-[#6C5CE7] transition group-open:rotate-45"
                  aria-hidden="true"
                >
                  ＋
                </span>
              </summary>
              <p className="max-w-2xl pt-4 leading-7 text-[#6E6E7A]">
                {answer}
              </p>
            </details>
          ))}
        </div>
      </section>

      <footer className="border-t border-[#E7E7EE] bg-white">
        <div className="mx-auto flex max-w-[1180px] flex-col gap-5 px-5 py-10 text-sm text-[#6E6E7A] sm:px-8 md:flex-row md:items-center md:justify-between">
          <Logo />
          <span>© 2026 Vydra. Trabalho criativo em ordem.</span>
          <span>Termos · Privacidade</span>
        </div>
      </footer>
    </main>
  );
}
