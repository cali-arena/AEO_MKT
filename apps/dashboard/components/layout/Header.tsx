interface HeaderProps {
  tenantId: string;
}

export function Header({ tenantId }: HeaderProps) {
  return (
    <header className="border-b border-gray-200 bg-white px-6 py-4">
      <h1 className="text-lg font-semibold text-gray-900">{tenantId}</h1>
    </header>
  );
}
