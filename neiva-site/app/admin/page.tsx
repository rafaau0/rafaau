import type { Metadata } from 'next';

import { AdminPanel } from '../../components/admin-panel';

export const metadata: Metadata = {
  title: 'Administração | Vydra',
  description: 'Área administrativa privada do Vydra.',
};

export default function AdminPage() {
  return <AdminPanel />;
}
