import { type NextRequest, NextResponse } from 'next/server';

function upstreamFor(request: NextRequest) {
  const hostname = new URL(request.url).hostname;
  if (hostname === 'localhost' || hostname === '127.0.0.1')
    return 'http://localhost:8000';
  if (hostname.endsWith('-neiva-planner-site.rafaau0.workers.dev'))
    return 'https://neiva-ai-api-staging.onrender.com';
  return 'https://neiva-ai-api.onrender.com';
}

async function proxy(request: NextRequest) {
  const path = new URL(request.url).searchParams.get('path') || '';
  if (!path.startsWith('/v1/admin/') || path.includes('://')) {
    return NextResponse.json(
      { detail: 'Destino administrativo inválido.' },
      { status: 400 },
    );
  }
  const upstream = upstreamFor(request);
  const target = new URL(path, upstream);
  if (target.origin !== upstream || !target.pathname.startsWith('/v1/admin/')) {
    return NextResponse.json(
      { detail: 'Destino administrativo inválido.' },
      { status: 400 },
    );
  }
  const headers = new Headers();
  for (const name of ['content-type', 'cookie', 'x-admin-csrf']) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const method = request.method.toUpperCase();
  let response: Response;
  try {
    response = await fetch(target, {
      method,
      headers,
      body:
        method === 'GET' || method === 'HEAD'
          ? undefined
          : await request.arrayBuffer(),
      redirect: 'manual',
      signal: AbortSignal.timeout(20_000),
    });
  } catch {
    return NextResponse.json(
      { detail: 'O serviço administrativo não respondeu. Tente novamente.' },
      { status: 502, headers: { 'Cache-Control': 'no-store' } },
    );
  }
  const responseHeaders = new Headers();
  for (const name of ['content-type', 'set-cookie', 'cache-control']) {
    const value = response.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  responseHeaders.set('Cache-Control', 'no-store');
  return new NextResponse(response.body, {
    status: response.status,
    headers: responseHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
