'use client';

import { type FormEvent, useCallback, useEffect, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  CircleDollarSign,
  Laptop,
  LayoutDashboard,
  LogOut,
  Search,
  ShieldCheck,
  UserRoundCog,
  Users,
} from 'lucide-react';

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

type AdminSession = {
  admin: { id: number; email: string };
  csrf_token: string;
};
type Dashboard = {
  total_customers: number;
  active_customers: number;
  suspended_customers: number;
  active_subscriptions: number;
  attention_subscriptions: number;
  pending_orders: number;
  ai_usage_current_month: number;
  period: string;
};
type Customer = {
  id: number;
  name: string;
  email: string | null;
  active: boolean;
  license_active: boolean;
  account_active: boolean | null;
  plan_code: string;
  monthly_limit: number;
  usage_current_month: number;
  device_limit: number;
  active_devices: number;
  subscription_status: string | null;
  current_period_end: string | null;
  created_at: string | null;
  legacy: boolean;
};
type CustomerDetail = Customer & {
  devices: Array<{
    id: number;
    label: string;
    last_seen_at: string | null;
    created_at: string | null;
  }>;
  usage_history: Array<{ period: string; requests_count: number }>;
  subscriptions: Array<{
    id: number;
    provider: string;
    provider_subscription_id: string;
    plan_code: string;
    status: string;
    current_period_end: string | null;
    created_at: string | null;
  }>;
  orders: Array<{
    public_id: string;
    plan_code: string;
    status: string;
    checkout_id: string | null;
    created_at: string | null;
  }>;
};
type CustomersPage = {
  items: Customer[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};
type AuditEntry = {
  id: number;
  admin_email: string;
  action: string;
  target_type: string;
  target_id: string;
  details: { reason?: string };
  created_at: string | null;
};
type PendingAction =
  | { kind: 'save' }
  | { kind: 'revoke-all' }
  | { kind: 'revoke-device'; deviceId: number };

function messageFrom(detail: unknown, fallback: string) {
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const text = detail
      .map((item) =>
        typeof item === 'object' && item && 'msg' in item
          ? String(item.msg)
          : '',
      )
      .filter(Boolean)
      .join(' ');
    if (text) return text;
  }
  return fallback;
}

async function api<T>(
  path: string,
  init: RequestInit = {},
  csrf = '',
): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 20000);
  const headers = new Headers(init.headers);
  if (init.body) headers.set('Content-Type', 'application/json');
  if (csrf && init.method && init.method !== 'GET')
    headers.set('X-Admin-CSRF', csrf);
  try {
    const response = await fetch(
      `/admin-api?path=${encodeURIComponent(path)}`,
      { ...init, headers, credentials: 'include', signal: controller.signal },
    );
    let data: unknown = {};
    try {
      data = await response.json();
    } catch {
      /* resposta vazia */
    }
    if (!response.ok) {
      const detail =
        typeof data === 'object' && data && 'detail' in data
          ? (data as { detail: unknown }).detail
          : undefined;
      throw new Error(
        messageFrom(detail, 'Não foi possível concluir a operação.'),
      );
    }
    return data as T;
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError')
      throw new Error('A operação demorou demais. Tente novamente.');
    throw cause;
  } finally {
    window.clearTimeout(timeout);
  }
}

function formatDate(value: string | null, includeTime = false) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat(
    'pt-BR',
    includeTime
      ? { dateStyle: 'short', timeStyle: 'short' }
      : { dateStyle: 'short' },
  ).format(date);
}

const planName: Record<string, string> = {
  free: 'Grátis',
  essencial: 'Essencial',
  pro: 'Pro',
  legacy: 'Legado',
};
const planDefaults: Record<string, { credits: number; devices: number }> = {
  free: { credits: 0, devices: 1 },
  essencial: { credits: 20, devices: 2 },
  pro: { credits: 80, devices: 3 },
};
const statusName: Record<string, string> = {
  active: 'Ativa',
  pending: 'Pendente',
  pending_cancellation: 'Cancelamento agendado',
  past_due: 'Em atraso',
  suspended: 'Suspensa',
  cancelled: 'Cancelada',
  paid: 'Pago',
};

function Badge({
  active,
  children,
}: {
  active?: boolean;
  children: React.ReactNode;
}) {
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-bold ${active ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'}`}
    >
      {children}
    </span>
  );
}

export function AdminPanel() {
  const [session, setSession] = useState<AdminSession | null>(null);
  const [checking, setChecking] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [customers, setCustomers] = useState<CustomersPage | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [view, setView] = useState<'customers' | 'audit'>('customers');
  const [search, setSearch] = useState('');
  const [plan, setPlan] = useState('');
  const [access, setAccess] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [detail, setDetail] = useState<CustomerDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [editPlan, setEditPlan] = useState('free');
  const [editActive, setEditActive] = useState(true);
  const [editAccountActive, setEditAccountActive] = useState(true);
  const [editMonthlyLimit, setEditMonthlyLimit] = useState('0');
  const [editDeviceLimit, setEditDeviceLimit] = useState('1');
  const [reason, setReason] = useState('');
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(
    null,
  );
  const [actionLoading, setActionLoading] = useState(false);

  const loadCustomers = useCallback(
    async (targetPage = page) => {
      const params = new URLSearchParams({
        page: String(targetPage),
        page_size: '25',
      });
      if (search.trim()) params.set('search', search.trim());
      if (plan) params.set('plan', plan);
      if (access) params.set('access', access);
      const result = await api<CustomersPage>(`/v1/admin/customers?${params}`);
      setCustomers(result);
      setPage(result.page);
    },
    [access, page, plan, search],
  );

  const loadWorkspace = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [summary, clients, history] = await Promise.all([
        api<Dashboard>('/v1/admin/dashboard'),
        api<CustomersPage>('/v1/admin/customers?page=1&page_size=25'),
        api<{ items: AuditEntry[] }>('/v1/admin/audit?page=1&page_size=30'),
      ]);
      setDashboard(summary);
      setCustomers(clients);
      setAudit(history.items);
      setPage(1);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'Não foi possível carregar a administração.',
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    api<AdminSession>('/v1/admin/auth/session')
      .then((value) => {
        setSession(value);
        return loadWorkspace();
      })
      .catch(() => setSession(null))
      .finally(() => setChecking(false));
  }, [loadWorkspace]);

  async function signIn(event: FormEvent) {
    event.preventDefault();
    setLoginLoading(true);
    setLoginError('');
    try {
      const result = await api<AdminSession>('/v1/admin/auth/sign-in', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      setSession(result);
      setPassword('');
      await loadWorkspace();
    } catch (cause) {
      setLoginError(
        cause instanceof Error ? cause.message : 'Não foi possível entrar.',
      );
    } finally {
      setLoginLoading(false);
    }
  }

  async function signOut() {
    if (!session) return;
    try {
      await api(
        '/v1/admin/auth/sign-out',
        { method: 'POST' },
        session.csrf_token,
      );
    } catch {
      /* encerra a tela mesmo se a sessão já expirou */
    }
    setSession(null);
    setDashboard(null);
    setCustomers(null);
    setDetail(null);
  }

  async function openCustomer(id: number) {
    setDetailLoading(true);
    setError('');
    try {
      const result = await api<CustomerDetail>(`/v1/admin/customers/${id}`);
      setDetail(result);
      setEditPlan(result.plan_code === 'legacy' ? 'pro' : result.plan_code);
      setEditActive(result.license_active);
      setEditAccountActive(result.account_active ?? true);
      setEditMonthlyLimit(String(result.monthly_limit));
      setEditDeviceLimit(String(result.device_limit));
      setReason('');
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'Não foi possível abrir o cliente.',
      );
    } finally {
      setDetailLoading(false);
    }
  }

  async function refreshAfterAction(clientId: number) {
    const [summary, updated, list, history] = await Promise.all([
      api<Dashboard>('/v1/admin/dashboard'),
      api<CustomerDetail>(`/v1/admin/customers/${clientId}`),
      loadCustomers(page),
      api<{ items: AuditEntry[] }>('/v1/admin/audit?page=1&page_size=30'),
    ]);
    setDashboard(summary);
    setDetail(updated);
    setAudit(history.items);
  }

  async function executeAction() {
    if (!session || !detail || !pendingAction || reason.trim().length < 3)
      return;
    setActionLoading(true);
    setError('');
    setNotice('');
    try {
      if (pendingAction.kind === 'save') {
        await api(
          `/v1/admin/customers/${detail.id}`,
          {
            method: 'PATCH',
            body: JSON.stringify({
              active: editActive,
              account_active: detail.legacy ? undefined : editAccountActive,
              plan_code: editPlan,
              monthly_limit: Number(editMonthlyLimit),
              device_limit: Number(editDeviceLimit),
              reason: reason.trim(),
            }),
          },
          session.csrf_token,
        );
        setNotice('Dados e acesso atualizados com sucesso.');
      } else if (pendingAction.kind === 'revoke-all') {
        await api(
          `/v1/admin/customers/${detail.id}/revoke-devices?reason=${encodeURIComponent(reason.trim())}`,
          { method: 'POST' },
          session.csrf_token,
        );
        setNotice('Todos os dispositivos foram desconectados.');
      } else {
        await api(
          `/v1/admin/customers/${detail.id}/devices/${pendingAction.deviceId}?reason=${encodeURIComponent(reason.trim())}`,
          { method: 'DELETE' },
          session.csrf_token,
        );
        setNotice('Dispositivo desconectado.');
      }
      await refreshAfterAction(detail.id);
      setReason('');
      setPendingAction(null);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'Não foi possível concluir a ação.',
      );
    } finally {
      setActionLoading(false);
    }
  }

  async function applyFilters(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      await loadCustomers(1);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'Não foi possível buscar os clientes.',
      );
    } finally {
      setLoading(false);
    }
  }

  if (checking)
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#F4F2ED]">
        <p className="text-base font-semibold text-stone-600">
          Verificando acesso…
        </p>
      </main>
    );

  if (!session)
    return (
      <main className="grid min-h-screen place-items-center bg-[#F4F2ED] px-5 py-10">
        <section className="w-full max-w-md overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-xl shadow-stone-900/5">
          <div className="bg-[#191919] px-7 py-6 text-white">
            <p className="text-3xl font-black tracking-tight">
              rafaau<span className="text-[#E23A4A]">.</span>
            </p>
            <p className="mt-1 text-sm text-stone-400">Administração privada</p>
          </div>
          <form onSubmit={signIn} className="space-y-5 p-7">
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-[#181818]">
                Acesso administrativo
              </h1>
              <p className="mt-2 text-base leading-6 text-stone-600">
                Entre com as credenciais exclusivas de administração.
              </p>
            </div>
            <label className="block text-sm font-semibold text-stone-700">
              E-mail
              <Input
                required
                type="email"
                autoComplete="username"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="mt-2 h-11"
              />
            </label>
            <label className="block text-sm font-semibold text-stone-700">
              Senha
              <Input
                required
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="mt-2 h-11"
              />
            </label>
            {loginError && (
              <p
                role="alert"
                className="rounded-lg bg-red-50 px-3 py-2 text-sm font-medium text-red-700"
              >
                {loginError}
              </p>
            )}
            <Button
              type="submit"
              disabled={loginLoading}
              className="h-11 w-full bg-[#E23A4A] text-white hover:bg-[#C92D3C]"
            >
              {loginLoading ? 'Entrando…' : 'ENTRAR'}
            </Button>
            <a
              href="/"
              className="block text-center text-sm font-semibold text-stone-500 hover:text-[#E23A4A]"
            >
              Voltar ao site
            </a>
          </form>
        </section>
      </main>
    );

  const metrics = dashboard
    ? [
        {
          label: 'Clientes',
          value: dashboard.total_customers,
          detail: `${dashboard.active_customers} com acesso`,
          icon: Users,
        },
        {
          label: 'Assinaturas ativas',
          value: dashboard.active_subscriptions,
          detail: `${dashboard.attention_subscriptions} exigem atenção`,
          icon: CircleDollarSign,
        },
        {
          label: 'Acessos suspensos',
          value: dashboard.suspended_customers,
          detail: 'Conta ou licença bloqueada',
          icon: AlertTriangle,
        },
        {
          label: `Uso de IA · ${dashboard.period}`,
          value: dashboard.ai_usage_current_month,
          detail: `${dashboard.pending_orders} pedidos pendentes`,
          icon: Activity,
        },
      ]
    : [];

  return (
    <main className="min-h-screen bg-[#F4F2ED] text-[#181818] lg:grid lg:grid-cols-[240px_1fr]">
      <aside className="flex items-center justify-between bg-[#191919] px-5 py-4 text-white lg:sticky lg:top-0 lg:h-screen lg:flex-col lg:items-stretch lg:px-4 lg:py-6">
        <div>
          <p className="px-2 text-2xl font-black">
            rafaau<span className="text-[#E23A4A]">.</span>
          </p>
          <p className="mt-1 px-2 text-xs font-semibold tracking-widest text-stone-500">
            ADMIN
          </p>
        </div>
        <nav
          aria-label="Administração"
          className="mx-4 flex gap-2 lg:mx-0 lg:mt-10 lg:block lg:flex-1 lg:space-y-2"
        >
          <button
            onClick={() => setView('customers')}
            className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold ${view === 'customers' ? 'bg-[#E23A4A] text-white' : 'text-stone-400 hover:bg-white/10 hover:text-white'}`}
          >
            <LayoutDashboard /> Clientes
          </button>
          <button
            onClick={() => setView('audit')}
            className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold ${view === 'audit' ? 'bg-[#E23A4A] text-white' : 'text-stone-400 hover:bg-white/10 hover:text-white'}`}
          >
            <ShieldCheck /> Auditoria
          </button>
        </nav>
        <div className="hidden border-t border-white/10 pt-4 lg:block">
          <p className="truncate px-2 text-xs text-stone-500">
            {session.admin.email}
          </p>
          <button
            onClick={signOut}
            className="mt-2 flex w-full items-center gap-2 rounded-lg px-2 py-2 text-sm font-semibold text-stone-300 hover:bg-white/10"
          >
            <LogOut /> Sair
          </button>
        </div>
        <button
          onClick={signOut}
          aria-label="Sair"
          className="rounded-lg p-2 text-stone-400 hover:bg-white/10 lg:hidden"
        >
          <LogOut />
        </button>
      </aside>

      <section className="min-w-0 p-5 md:p-8 xl:p-10">
        <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm font-bold uppercase tracking-[0.18em] text-[#E23A4A]">
              Operação
            </p>
            <h1 className="mt-1 text-3xl font-black tracking-tight">
              {view === 'customers'
                ? 'Clientes e acessos'
                : 'Histórico administrativo'}
            </h1>
          </div>
          {loading && (
            <p className="text-sm font-semibold text-stone-500">Atualizando…</p>
          )}
        </header>
        {error && (
          <p
            role="alert"
            className="mb-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700"
          >
            {error}
          </p>
        )}
        {notice && (
          <p className="mb-5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700">
            {notice}
          </p>
        )}

        {view === 'customers' ? (
          <>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {metrics.map(
                ({ label, value, detail: metricDetail, icon: Icon }) => (
                  <article
                    key={label}
                    className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="text-sm font-semibold text-stone-500">
                          {label}
                        </p>
                        <p className="mt-2 text-3xl font-black">{value}</p>
                      </div>
                      <span className="rounded-lg bg-[#FBE8E9] p-2.5 text-[#E23A4A]">
                        <Icon />
                      </span>
                    </div>
                    <p className="mt-3 text-sm text-stone-500">
                      {metricDetail}
                    </p>
                  </article>
                ),
              )}
            </div>
            <section className="mt-6 rounded-xl border border-stone-200 bg-white shadow-sm">
              <form
                onSubmit={applyFilters}
                className="grid gap-3 border-b border-stone-200 p-4 md:grid-cols-[1fr_170px_170px_auto]"
              >
                <label className="relative">
                  <span className="sr-only">Buscar cliente</span>
                  <Search className="absolute left-3 top-2.5 size-5 text-stone-400" />
                  <Input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Nome ou e-mail"
                    className="h-10 pl-10"
                  />
                </label>
                <label>
                  <span className="sr-only">Filtrar por plano</span>
                  <select
                    value={plan}
                    onChange={(event) => setPlan(event.target.value)}
                    className="h-10 w-full rounded-lg border border-stone-200 bg-white px-3 text-sm"
                  >
                    <option value="">Todos os planos</option>
                    <option value="free">Grátis</option>
                    <option value="essencial">Essencial</option>
                    <option value="pro">Pro</option>
                    <option value="legacy">Legado</option>
                  </select>
                </label>
                <label>
                  <span className="sr-only">Filtrar por acesso</span>
                  <select
                    value={access}
                    onChange={(event) => setAccess(event.target.value)}
                    className="h-10 w-full rounded-lg border border-stone-200 bg-white px-3 text-sm"
                  >
                    <option value="">Todos os acessos</option>
                    <option value="active">Ativo</option>
                    <option value="suspended">Suspenso</option>
                  </select>
                </label>
                <Button type="submit" className="h-10 bg-[#191919] text-white">
                  FILTRAR
                </Button>
              </form>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="pl-5">Cliente</TableHead>
                    <TableHead>Plano</TableHead>
                    <TableHead>Acesso</TableHead>
                    <TableHead>Assinatura</TableHead>
                    <TableHead>IA</TableHead>
                    <TableHead>Dispositivos</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {customers?.items.map((customer) => (
                    <TableRow key={customer.id}>
                      <TableCell className="pl-5">
                        <p className="font-bold">{customer.name}</p>
                        <p className="text-xs text-stone-500">
                          {customer.email || 'Licença legada'}
                        </p>
                      </TableCell>
                      <TableCell>
                        {planName[customer.plan_code] || customer.plan_code}
                      </TableCell>
                      <TableCell>
                        <Badge active={customer.active}>
                          {customer.active ? 'Ativo' : 'Suspenso'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {customer.subscription_status
                          ? statusName[customer.subscription_status] ||
                            customer.subscription_status
                          : '—'}
                      </TableCell>
                      <TableCell>
                        {customer.usage_current_month}/{customer.monthly_limit}
                      </TableCell>
                      <TableCell>
                        {customer.active_devices}/{customer.device_limit}
                      </TableCell>
                      <TableCell className="pr-5 text-right">
                        <Button
                          variant="outline"
                          onClick={() => openCustomer(customer.id)}
                          disabled={detailLoading}
                        >
                          Administrar
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                  {!customers?.items.length && (
                    <TableRow>
                      <TableCell
                        colSpan={7}
                        className="h-32 text-center text-stone-500"
                      >
                        Nenhum cliente encontrado.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
              {customers && (
                <div className="flex items-center justify-between border-t border-stone-200 px-5 py-4 text-sm">
                  <p className="text-stone-500">{customers.total} clientes</p>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="icon"
                      disabled={page <= 1 || loading}
                      onClick={() => loadCustomers(page - 1)}
                      aria-label="Página anterior"
                    >
                      <ChevronLeft />
                    </Button>
                    <span className="font-semibold">
                      {page} de {customers.pages}
                    </span>
                    <Button
                      variant="outline"
                      size="icon"
                      disabled={page >= customers.pages || loading}
                      onClick={() => loadCustomers(page + 1)}
                      aria-label="Próxima página"
                    >
                      <ChevronRight />
                    </Button>
                  </div>
                </div>
              )}
            </section>
          </>
        ) : (
          <section className="rounded-xl border border-stone-200 bg-white shadow-sm">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-5">Data</TableHead>
                  <TableHead>Administrador</TableHead>
                  <TableHead>Ação</TableHead>
                  <TableHead>Destino</TableHead>
                  <TableHead>Justificativa</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {audit.map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell className="pl-5">
                      {formatDate(entry.created_at, true)}
                    </TableCell>
                    <TableCell>{entry.admin_email}</TableCell>
                    <TableCell className="font-semibold">
                      {entry.action}
                    </TableCell>
                    <TableCell>
                      {entry.target_type} #{entry.target_id}
                    </TableCell>
                    <TableCell className="max-w-sm whitespace-normal text-stone-600">
                      {entry.details.reason || '—'}
                    </TableCell>
                  </TableRow>
                ))}
                {!audit.length && (
                  <TableRow>
                    <TableCell
                      colSpan={5}
                      className="h-32 text-center text-stone-500"
                    >
                      Nenhuma ação administrativa registrada.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </section>
        )}
      </section>

      <Dialog
        open={Boolean(detail)}
        onOpenChange={(open) => {
          if (!open) setDetail(null);
        }}
      >
        <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle className="text-xl">{detail?.name}</DialogTitle>
            <DialogDescription>
              {detail?.email || 'Licença legada sem conta vinculada'} · cadastro
              em {formatDate(detail?.created_at || null)}
            </DialogDescription>
          </DialogHeader>
          {detail && (
            <div className="space-y-6">
              <div className="grid gap-4 rounded-xl bg-[#F4F2ED] p-4 sm:grid-cols-2">
                <label className="text-sm font-semibold">
                  Plano
                  <select
                    value={editPlan}
                    onChange={(event) => {
                      const value = event.target.value;
                      setEditPlan(value);
                      setEditMonthlyLimit(String(planDefaults[value].credits));
                      setEditDeviceLimit(String(planDefaults[value].devices));
                    }}
                    className="mt-2 h-10 w-full rounded-lg border border-stone-300 bg-white px-3 font-normal"
                  >
                    <option value="free">Grátis</option>
                    <option value="essencial">Essencial</option>
                    <option value="pro">Pro</option>
                  </select>
                </label>
                <label className="text-sm font-semibold">
                  Acesso ao aplicativo
                  <select
                    value={editActive ? 'active' : 'suspended'}
                    onChange={(event) =>
                      setEditActive(event.target.value === 'active')
                    }
                    className="mt-2 h-10 w-full rounded-lg border border-stone-300 bg-white px-3 font-normal"
                  >
                    <option value="active">Ativo</option>
                    <option value="suspended">Suspenso</option>
                  </select>
                </label>
                {!detail.legacy && (
                  <label className="text-sm font-semibold">
                    Conta do site
                    <select
                      value={editAccountActive ? 'active' : 'suspended'}
                      onChange={(event) =>
                        setEditAccountActive(event.target.value === 'active')
                      }
                      className="mt-2 h-10 w-full rounded-lg border border-stone-300 bg-white px-3 font-normal"
                    >
                      <option value="active">Ativa</option>
                      <option value="suspended">Bloqueada</option>
                    </select>
                  </label>
                )}
                <label className="text-sm font-semibold">
                  Créditos de IA
                  <Input
                    type="number"
                    min={0}
                    max={10000}
                    value={editMonthlyLimit}
                    onChange={(event) =>
                      setEditMonthlyLimit(event.target.value)
                    }
                    className="mt-2 h-10 bg-white"
                  />
                </label>
                <label className="text-sm font-semibold">
                  Limite de dispositivos
                  <Input
                    type="number"
                    min={1}
                    max={20}
                    value={editDeviceLimit}
                    onChange={(event) => setEditDeviceLimit(event.target.value)}
                    className="mt-2 h-10 bg-white"
                  />
                </label>
              </div>
              <label className="block text-sm font-semibold">
                Justificativa obrigatória
                <Input
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  placeholder="Ex.: solicitação do titular pelo suporte"
                  className="mt-2 h-10"
                />
              </label>
              <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                Alterações manuais de plano podem ser substituídas pelo próximo
                webhook do Asaas. Confirme primeiro a situação financeira.
              </p>
              <section>
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="font-bold">Dispositivos</h2>
                  {detail.devices.length > 0 && (
                    <Button
                      variant="destructive"
                      onClick={() => setPendingAction({ kind: 'revoke-all' })}
                      disabled={reason.trim().length < 3}
                    >
                      Desconectar todos
                    </Button>
                  )}
                </div>
                <div className="space-y-2">
                  {detail.devices.map((device) => (
                    <div
                      key={device.id}
                      className="flex items-center justify-between rounded-lg border border-stone-200 p-3"
                    >
                      <div className="flex items-center gap-3">
                        <Laptop className="text-stone-400" />
                        <div>
                          <p className="text-sm font-semibold">
                            {device.label}
                          </p>
                          <p className="text-xs text-stone-500">
                            Último acesso:{' '}
                            {formatDate(device.last_seen_at, true)}
                          </p>
                        </div>
                      </div>
                      <Button
                        variant="outline"
                        onClick={() =>
                          setPendingAction({
                            kind: 'revoke-device',
                            deviceId: device.id,
                          })
                        }
                        disabled={reason.trim().length < 3}
                      >
                        Desconectar
                      </Button>
                    </div>
                  ))}
                  {!detail.devices.length && (
                    <p className="text-sm text-stone-500">
                      Nenhum dispositivo conectado.
                    </p>
                  )}
                </div>
              </section>
              <section>
                <h2 className="mb-3 font-bold">Assinaturas</h2>
                {detail.subscriptions.length ? (
                  <div className="space-y-2">
                    {detail.subscriptions.map((subscription) => (
                      <div
                        key={subscription.id}
                        className="grid gap-1 rounded-lg border border-stone-200 p-3 text-sm sm:grid-cols-3"
                      >
                        <strong>
                          {planName[subscription.plan_code] ||
                            subscription.plan_code}
                        </strong>
                        <span>
                          {statusName[subscription.status] ||
                            subscription.status}
                        </span>
                        <span>
                          Até {formatDate(subscription.current_period_end)}
                        </span>
                        <span className="col-span-full text-xs text-stone-500">
                          Asaas: {subscription.provider_subscription_id}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-stone-500">
                    Sem assinatura registrada.
                  </p>
                )}
              </section>
              <section>
                <h2 className="mb-3 font-bold">Pedidos de checkout</h2>
                {detail.orders.length ? (
                  <div className="space-y-2">
                    {detail.orders.map((order) => (
                      <div
                        key={order.public_id}
                        className="grid gap-1 rounded-lg border border-stone-200 p-3 text-sm sm:grid-cols-3"
                      >
                        <strong>
                          {planName[order.plan_code] || order.plan_code}
                        </strong>
                        <span>{statusName[order.status] || order.status}</span>
                        <span>{formatDate(order.created_at, true)}</span>
                        <span className="col-span-full text-xs text-stone-500">
                          Pedido: {order.public_id}
                          {order.checkout_id
                            ? ` · Checkout Asaas: ${order.checkout_id}`
                            : ''}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-stone-500">
                    Nenhum pedido encontrado.
                  </p>
                )}
              </section>
              <section>
                <h2 className="mb-3 font-bold">Uso recente de IA</h2>
                <div className="flex flex-wrap gap-2">
                  {detail.usage_history.map((usage) => (
                    <span
                      key={usage.period}
                      className="rounded-lg bg-stone-100 px-3 py-2 text-sm"
                    >
                      <strong>{usage.period}</strong> · {usage.requests_count}
                    </span>
                  ))}
                  {!detail.usage_history.length && (
                    <p className="text-sm text-stone-500">
                      Nenhum consumo registrado.
                    </p>
                  )}
                </div>
              </section>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDetail(null)}>
              Fechar
            </Button>
            <Button
              className="bg-[#E23A4A] text-white hover:bg-[#C92D3C]"
              disabled={!detail || reason.trim().length < 3}
              onClick={() => setPendingAction({ kind: 'save' })}
            >
              <UserRoundCog /> Salvar alterações
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={Boolean(pendingAction)}
        onOpenChange={(open) => {
          if (!open && !actionLoading) setPendingAction(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirmar ação administrativa?</AlertDialogTitle>
            <AlertDialogDescription>
              Esta operação afeta o acesso do cliente e ficará registrada com
              sua justificativa.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={actionLoading}>
              Cancelar
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={actionLoading || reason.trim().length < 3}
              onClick={executeAction}
            >
              {actionLoading ? 'Processando…' : 'Confirmar'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </main>
  );
}
