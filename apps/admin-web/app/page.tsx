import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col items-start justify-center gap-6 px-6">
      <div className="space-y-2">
        <p className="text-sm text-slate-500">Oficina Pro</p>
        <h1 className="text-4xl font-bold tracking-tight">Painel Interno</h1>
        <p className="text-slate-700">Base Next.js + TypeScript + Tailwind + componentes UI.</p>
      </div>
      <Button>Acessar</Button>
    </main>
  );
}
