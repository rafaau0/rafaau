import { ActivationStatus } from '../components/activation-status';
import { CheckoutButton } from '../components/checkout-button';

const DOWNLOAD_URL =
  'https://github.com/rafaau0/rafaau/releases/latest/download/rafaau_v1.exe';

const projects = [
  {
    eyebrow: 'DESIGN QUE VENDE',
    title: 'Flyers de mercado',
    color: '#FFD84D',
    ink: '#181818',
    description:
      'Ofertas organizadas, preços em destaque e peças prontas para chamar atenção no feed, status ou impressão.',
    visual: 'flyer',
    tags: ['Encartes', 'Ofertas', 'Photoshop'],
  },
  {
    eyebrow: 'IDEIA → SISTEMA',
    title: 'Vibe coding & automações',
    color: '#6161FF',
    ink: '#FFFFFF',
    description:
      'Ferramentas sob medida para tirar tarefas repetitivas da frente e colocar a operação para rodar.',
    visual: 'code',
    tags: ['Python', 'IA', 'Automação'],
  },
  {
    eyebrow: 'PRESENÇA DIGITAL',
    title: 'Criação de sites',
    color: '#45D6E8',
    ink: '#101820',
    description:
      'Sites rápidos, claros e responsivos, com uma identidade que não parece saída de um template qualquer.',
    visual: 'site',
    tags: ['UI/UX', 'React', 'Landing pages'],
  },
  {
    eyebrow: 'RITMO & RETENÇÃO',
    title: 'Edição de vídeo',
    color: '#FF7A45',
    ink: '#181818',
    description:
      'Cortes, legendas e movimento para transformar material bruto em conteúdo que segura a atenção.',
    visual: 'video',
    tags: ['Reels', 'Legendas', 'Cortes'],
  },
];

const plans = [
  {
    code: 'free',
    name: 'Grátis',
    price: '0',
    note: 'Para começar',
    features: ['1 cliente', '15 conteúdos/mês', '1 PDF/mês'],
  },
  {
    code: 'essencial',
    name: 'Essencial',
    price: '49,90',
    note: 'Mais escolhido',
    features: ['Até 10 clientes', 'Vídeo + Trello', '20 análises de IA'],
  },
  {
    code: 'pro',
    name: 'Pro',
    price: '89,90',
    note: 'Para maior volume',
    features: ['Clientes ilimitados', 'Todos os recursos', '80 análises de IA'],
  },
];

function Brand() {
  return (
    <span className="inline-flex items-center gap-2.5 text-lg font-extrabold tracking-[-.04em]">
      <i className="grid size-9 place-items-center rounded-xl bg-[#6161FF] not-italic text-white">
        r
      </i>
      rafaau
    </span>
  );
}

function ProjectVisual({ type }: { type: string }) {
  if (type === 'flyer')
    return (
      <div className="relative mx-auto h-52 max-w-sm">
        <div className="absolute left-4 top-4 w-44 -rotate-6 rounded-2xl bg-[#FF4F87] p-4 shadow-xl">
          <p className="text-xs font-black">OFERTA DA SEMANA</p>
          <p className="mt-5 text-4xl font-black">R$ 9,99</p>
          <div className="mt-4 h-10 rounded-lg bg-white/70" />
        </div>
        <div className="absolute right-3 top-8 w-44 rotate-6 rounded-2xl bg-white p-4 text-[#181818] shadow-xl">
          <span className="rounded-full bg-[#FFD84D] px-2 py-1 text-[10px] font-black">
            IMPERDÍVEL
          </span>
          <div className="mt-4 h-20 rounded-xl bg-[#EAEAEA]" />
          <p className="mt-3 text-xl font-black">LEVE 3</p>
        </div>
      </div>
    );
  if (type === 'code')
    return (
      <div className="mx-auto max-w-md rotate-2 overflow-hidden rounded-2xl border border-white/20 bg-[#111] font-mono text-xs shadow-2xl">
        <div className="flex gap-1.5 border-b border-white/10 p-3">
          <i className="size-2 rounded-full bg-[#FF5F57]" />
          <i className="size-2 rounded-full bg-[#FFBD2E]" />
          <i className="size-2 rounded-full bg-[#28C840]" />
        </div>
        <div className="space-y-2 p-5 text-white/70">
          <p>
            <b className="text-[#FF7FD1]">def</b> executar_ideia():
          </p>
          <p className="pl-5">
            <span className="text-[#65E6F4]">processo</span> =
            automatizar(tarefa)
          </p>
          <p className="pl-5">
            <span className="text-[#FFD84D]">return</span> resultado
          </p>
          <p className="pt-3 text-[#73F0A8]">✓ operação pronta para rodar</p>
        </div>
      </div>
    );
  if (type === 'site')
    return (
      <div className="mx-auto max-w-md -rotate-2 overflow-hidden rounded-2xl border-4 border-[#121212] bg-white shadow-2xl">
        <div className="flex items-center gap-2 bg-[#121212] px-3 py-2">
          <i className="size-2 rounded-full bg-[#FF7A45]" />
          <div className="h-3 flex-1 rounded-full bg-white/15" />
        </div>
        <div className="p-5">
          <span className="rounded-full bg-[#6161FF] px-3 py-1 text-[10px] font-bold text-white">
            NOVO SITE
          </span>
          <p className="mt-5 text-3xl font-black leading-none">
            Sua marca,
            <br />
            sem cara de template.
          </p>
          <div className="mt-5 h-3 w-2/3 rounded bg-[#CFF8FB]" />
          <div className="mt-2 h-3 w-1/2 rounded bg-[#E8E8E8]" />
        </div>
      </div>
    );
  return (
    <div className="relative mx-auto h-52 max-w-sm">
      <div className="absolute left-1/2 top-0 h-52 w-32 -translate-x-1/2 rotate-3 rounded-[28px] border-4 border-[#151515] bg-[#252525] p-2 shadow-2xl">
        <div className="grid h-full place-items-center rounded-[20px] bg-gradient-to-b from-[#6161FF] to-[#FF4F87] text-center text-white">
          <span className="px-3 text-lg font-black">
            VOCÊ PRECISA VER ISSO.
          </span>
        </div>
      </div>
      <span className="absolute left-4 top-12 -rotate-6 rounded-xl bg-white px-3 py-2 text-xs font-black shadow-lg">
        LEGENDAS ✓
      </span>
      <span className="absolute bottom-7 right-0 rotate-6 rounded-xl bg-[#FFD84D] px-3 py-2 text-xs font-black shadow-lg">
        CORTE 00:24
      </span>
    </div>
  );
}

export default function Home() {
  return (
    <main className="overflow-hidden bg-white text-[#111]">
      <ActivationStatus />
      <nav className="mx-auto flex h-20 max-w-7xl items-center justify-between px-6">
        <a href="#inicio">
          <Brand />
        </a>
        <div className="hidden items-center gap-8 text-sm font-semibold md:flex">
          <a href="#trabalhos">Trabalhos</a>
          <a href="#sobre">Como eu trabalho</a>
          <a href="#neiva">Neiva Planner</a>
        </div>
        <a
          href="#trabalhos"
          className="rounded-full bg-[#6161FF] px-5 py-3 text-sm font-bold text-white transition hover:scale-105 hover:bg-[#4D4DDE]"
        >
          Ver projetos ↘
        </a>
      </nav>

      <section
        id="inicio"
        className="relative mx-auto min-h-[720px] max-w-7xl px-6 pb-24 pt-20 text-center sm:pt-28"
      >
        <div className="absolute left-[4%] top-24 hidden -rotate-6 rounded-2xl bg-[#FFD84D] p-4 text-left shadow-lg lg:block">
          <p className="text-[10px] font-black">EM PRODUÇÃO</p>
          <p className="mt-1 font-extrabold">Site novo ✦</p>
        </div>
        <div className="absolute right-[5%] top-40 hidden rotate-6 rounded-2xl bg-[#45D6E8] p-4 text-left shadow-lg lg:block">
          <p className="text-[10px] font-black">AUTOMAÇÃO</p>
          <p className="mt-1 font-extrabold">Menos trabalho manual.</p>
        </div>
        <p className="mx-auto mb-7 w-fit rounded-full border border-black/10 px-4 py-2 text-xs font-bold tracking-[.13em]">
          DESIGN · CONTEÚDO · CÓDIGO
        </p>
        <h1 className="mx-auto max-w-5xl text-6xl font-extrabold leading-[.92] tracking-[-.065em] sm:text-7xl lg:text-[108px]">
          Você lidera.
          <br />
          <span className="text-[#6161FF]">Eu executo.</span>
        </h1>
        <p className="mx-auto mt-8 max-w-2xl text-lg leading-8 text-black/60 sm:text-xl">
          Transformo ideias em peças, vídeos, sites e automações que saem do
          papel e entram na rotina.
        </p>
        <a
          href="#trabalhos"
          className="mt-10 inline-flex items-center gap-3 rounded-full bg-[#6161FF] px-8 py-5 text-base font-bold text-white shadow-xl shadow-indigo-200 transition hover:-translate-y-1 hover:bg-[#4D4DDE]"
        >
          Explorar meu trabalho <span>↓</span>
        </a>
        <div className="mx-auto mt-20 flex max-w-3xl flex-wrap items-center justify-center gap-3 text-sm font-bold">
          <span className="rounded-full bg-[#FFE9F1] px-4 py-2">Flyers</span>
          <span className="rounded-full bg-[#EAEAFF] px-4 py-2">
            Automações
          </span>
          <span className="rounded-full bg-[#DDF9FC] px-4 py-2">Sites</span>
          <span className="rounded-full bg-[#FFF0E9] px-4 py-2">Vídeos</span>
        </div>
      </section>

      <section id="trabalhos" className="bg-black px-6 py-28 text-white">
        <div className="mx-auto max-w-7xl">
          <div className="grid gap-8 lg:grid-cols-[.8fr_1.2fr] lg:items-end">
            <p className="text-sm font-bold tracking-[.16em] text-white/50">
              O QUE EU COLOCO DE PÉ
            </p>
            <h2 className="text-5xl font-extrabold leading-[.95] tracking-[-.055em] sm:text-7xl">
              Um repertório.
              <br />
              <span className="text-white/40">Várias entregas.</span>
            </h2>
          </div>
          <div className="mt-16 grid gap-6 lg:grid-cols-2">
            {projects.map((project) => (
              <article
                key={project.title}
                className="group overflow-hidden rounded-[32px] p-7 transition duration-300 hover:-translate-y-2 sm:p-9"
                style={{ backgroundColor: project.color, color: project.ink }}
              >
                <div className="flex items-start justify-between gap-5">
                  <div>
                    <p className="text-[11px] font-black tracking-[.16em] opacity-60">
                      {project.eyebrow}
                    </p>
                    <h3 className="mt-3 text-3xl font-extrabold tracking-[-.04em] sm:text-4xl">
                      {project.title}
                    </h3>
                  </div>
                  <span className="text-3xl transition group-hover:rotate-45">
                    ↗
                  </span>
                </div>
                <p className="mt-4 max-w-lg leading-7 opacity-70">
                  {project.description}
                </p>
                <div className="my-9">
                  <ProjectVisual type={project.visual} />
                </div>
                <div className="flex flex-wrap gap-2">
                  {project.tags.map((tag) => (
                    <span
                      key={tag}
                      className="rounded-full border border-current/20 px-3 py-1.5 text-xs font-bold"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="sobre" className="bg-[#F2F0FF] px-6 py-28">
        <div className="mx-auto grid max-w-7xl gap-16 lg:grid-cols-[1fr_1fr] lg:items-center">
          <div>
            <p className="text-xs font-black tracking-[.16em] text-[#6161FF]">
              DO BRIEFING AO ARQUIVO FINAL
            </p>
            <h2 className="mt-5 text-5xl font-extrabold leading-[.96] tracking-[-.055em] sm:text-7xl">
              Menos conversa solta.
              <br />
              Mais coisa pronta.
            </h2>
            <p className="mt-7 max-w-xl text-lg leading-8 text-black/60">
              Eu junto olhar visual, raciocínio de produto e execução técnica.
              Isso reduz pontas soltas e acelera o caminho entre “seria legal” e
              “está funcionando”.
            </p>
          </div>
          <ol className="space-y-4">
            {[
              ['01', 'Entendo', 'O objetivo, o público e o que precisa mudar.'],
              [
                '02',
                'Construo',
                'A solução com direção visual e lógica clara.',
              ],
              ['03', 'Entrego', 'Tudo organizado, testado e pronto para uso.'],
            ].map(([n, title, text], index) => (
              <li
                key={n}
                className="flex gap-5 rounded-3xl bg-white p-6 shadow-sm"
                style={{
                  transform: `rotate(${index === 1 ? 1 : index === 2 ? -1 : 0}deg)`,
                }}
              >
                <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-[#6161FF] font-black text-white">
                  {n}
                </span>
                <div>
                  <h3 className="text-xl font-extrabold">{title}</h3>
                  <p className="mt-1 text-black/55">{text}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section id="neiva" className="px-6 py-28">
        <div className="mx-auto max-w-7xl">
          <div className="overflow-hidden rounded-[40px] bg-[#111] p-8 text-white sm:p-12 lg:p-16">
            <div className="grid gap-12 lg:grid-cols-[1fr_.9fr] lg:items-center">
              <div>
                <span className="rounded-full bg-[#FF4F87] px-4 py-2 text-xs font-black">
                  PRODUTO PRÓPRIO
                </span>
                <h2 className="mt-7 text-5xl font-extrabold tracking-[-.055em] sm:text-7xl">
                  Neiva
                  <br />
                  <span className="text-[#8E8EFF]">Planner.</span>
                </h2>
                <p className="mt-6 max-w-xl text-lg leading-8 text-white/60">
                  Planejamento editorial, clientes, Trello e produção de vídeos
                  reunidos em um aplicativo para Windows.
                </p>
                <a
                  href={DOWNLOAD_URL}
                  className="mt-8 inline-flex rounded-full bg-white px-6 py-4 font-bold text-black transition hover:bg-[#FFD84D]"
                >
                  Baixar para Windows ↓
                </a>
              </div>
              <div className="rotate-2 rounded-3xl bg-[#F7F7FA] p-4 text-[#111] shadow-2xl">
                <div className="flex items-center gap-2 border-b border-black/10 pb-3">
                  <i className="size-2 rounded-full bg-[#FF4F87]" />
                  <i className="size-2 rounded-full bg-[#FFD84D]" />
                  <i className="size-2 rounded-full bg-[#45D6E8]" />
                  <b className="ml-auto text-xs">NEIVA PLANNER</b>
                </div>
                <div className="mt-4 grid grid-cols-3 gap-3">
                  <div className="rounded-2xl bg-[#EAEAFF] p-4">
                    <small>CLIENTES</small>
                    <strong className="mt-2 block text-3xl">12</strong>
                  </div>
                  <div className="rounded-2xl bg-[#FFF1D0] p-4">
                    <small>CONTEÚDOS</small>
                    <strong className="mt-2 block text-3xl">48</strong>
                  </div>
                  <div className="rounded-2xl bg-[#DDF9FC] p-4">
                    <small>PRONTOS</small>
                    <strong className="mt-2 block text-3xl">31</strong>
                  </div>
                </div>
                <div className="mt-3 h-32 rounded-2xl bg-white p-4">
                  <div className="h-3 w-1/3 rounded bg-black/10" />
                  <div className="mt-5 grid grid-cols-5 gap-2">
                    {[1, 2, 3, 4, 5].map((n) => (
                      <i
                        key={n}
                        className={`h-14 rounded-lg ${n === 3 ? 'bg-[#6161FF]' : 'bg-black/5'}`}
                      />
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div id="planos" className="mt-24 text-center">
            <p className="text-xs font-black tracking-[.16em] text-[#6161FF]">
              PLANOS DO NEIVA
            </p>
            <h2 className="mt-4 text-4xl font-extrabold tracking-[-.05em] sm:text-6xl">
              Escolha o seu ritmo.
            </h2>
          </div>
          <div className="mt-12 grid gap-5 md:grid-cols-3">
            {plans.map((plan, index) => (
              <article
                key={plan.code}
                className={`rounded-[28px] border p-7 ${index === 1 ? 'border-[#6161FF] bg-[#F2F0FF] shadow-xl shadow-indigo-100' : 'border-black/10 bg-white'}`}
              >
                <div className="flex items-start justify-between">
                  <div className="text-left">
                    <p className="text-xs font-black uppercase tracking-widest text-black/40">
                      {plan.note}
                    </p>
                    <h3 className="mt-2 text-3xl font-extrabold">
                      {plan.name}
                    </h3>
                  </div>
                  {index === 1 && (
                    <span className="rounded-full bg-[#6161FF] px-3 py-1 text-[10px] font-black text-white">
                      POPULAR
                    </span>
                  )}
                </div>
                <p className="mt-8 text-left text-5xl font-extrabold">
                  <small className="text-base">R$</small> {plan.price}
                  <small className="text-sm font-medium text-black/40">
                    /mês
                  </small>
                </p>
                <CheckoutButton plan={plan.code} featured={index === 1} />
                <ul className="mt-6 space-y-3 border-t border-black/10 pt-6 text-left text-sm text-black/60">
                  {plan.features.map((feature) => (
                    <li key={feature}>✓ {feature}</li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-[#6161FF] px-6 py-24 text-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-10 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-black tracking-[.16em] text-white/60">
              TEM UMA IDEIA?
            </p>
            <h2 className="mt-5 max-w-4xl text-5xl font-extrabold leading-[.95] tracking-[-.055em] sm:text-7xl">
              Vamos tirar isso
              <br />
              do “um dia”.
            </h2>
          </div>
          <a
            href="mailto:contato@rafaau.site"
            className="shrink-0 rounded-full bg-white px-8 py-5 font-extrabold text-[#3333B8] transition hover:-translate-y-1 hover:bg-[#FFD84D]"
          >
            Fale comigo ↗
          </a>
        </div>
      </section>
      <footer className="bg-black px-6 py-10 text-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <Brand />
          <p className="text-sm text-white/40">
            Design, conteúdo e tecnologia — © 2026
          </p>
          <a href="#inicio" className="text-sm font-bold">
            Voltar ao topo ↑
          </a>
        </div>
      </footer>
    </main>
  );
}
