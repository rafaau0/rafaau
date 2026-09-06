import type { Metadata } from 'next';

import { AdminPanel } from '../../components/admin-panel';

export const metadata: Metadata = {
  title: 'Administração | rafaau',
  description: 'Área administrativa privada do rafaau.',
};

export default function AdminPage() {
  return <AdminPanel />;
}
