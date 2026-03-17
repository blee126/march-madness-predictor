import Link from 'next/link';

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col">
      <header className="bg-ncaa-blue text-white px-4 py-6 shadow-lg">
        <h1 className="font-display text-3xl md:text-4xl font-bold tracking-tight">
          March Madness AI
        </h1>
        <p className="mt-2 text-ncaa-cream/90 text-sm md:text-base">
          Predict the bracket with AI • Build yours • Export & share
        </p>
      </header>

      <div className="flex-1 px-4 py-8 max-w-lg mx-auto w-full">
        <div className="space-y-6">
          <Link
            href="/bracket"
            className="block w-full bg-ncaa-orange hover:bg-ncaa-orange/90 text-white font-display font-semibold text-lg py-4 px-6 rounded-xl shadow-md active:scale-[0.98] transition"
          >
            Build my bracket
          </Link>
          <p className="text-sm text-ncaa-dark/80">
            Use the AI model to fill your bracket or pick game-by-game. Export your
            predictions as JSON or print.
          </p>

          <section className="pt-6 border-t border-ncaa-dark/10">
            <h2 className="font-display font-semibold text-lg text-ncaa-blue mb-2">
              How it works
            </h2>
            <ul className="space-y-2 text-sm text-ncaa-dark/80">
              <li>• Model uses team stats (seed, efficiency, tempo) + round</li>
              <li>• One tap: &quot;Fill with AI&quot; or pick each game yourself</li>
              <li>• Export bracket as JSON or image for sharing</li>
            </ul>
          </section>
        </div>
      </div>

      <footer className="py-4 px-4 text-center text-xs text-ncaa-dark/60">
        Data: seed teams included. Add your own CSVs for real stats.
      </footer>
    </main>
  );
}
