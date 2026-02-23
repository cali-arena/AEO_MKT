import Link from "next/link";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-2xl font-bold">AI MKT Dashboard</h1>
      <div className="flex gap-3">
        <Link
          href="/login"
          className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
        >
          Log in
        </Link>
        <Link
          href="/health"
          className="rounded border border-gray-300 px-4 py-2 text-gray-700 hover:bg-gray-50"
        >
          Health check
        </Link>
      </div>
    </main>
  );
}
