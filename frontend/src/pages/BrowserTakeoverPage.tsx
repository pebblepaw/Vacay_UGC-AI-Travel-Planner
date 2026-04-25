import { getBrowserTakeoverSession, type BrowserTakeoverSessionResponse } from '@/lib/api';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

const BrowserTakeoverPage = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const [session, setSession] = useState<BrowserTakeoverSessionResponse | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let disposed = false;

    const load = async () => {
      if (!token) {
        setError('Missing browser takeover token.');
        setLoading(false);
        return;
      }

      try {
        const next = await getBrowserTakeoverSession(token);
        if (!disposed) {
          setSession(next);
        }
      } catch (err: any) {
        if (!disposed) {
          setError(err?.message || 'Could not load the remote browser session.');
        }
      } finally {
        if (!disposed) {
          setLoading(false);
        }
      }
    };

    load();
    return () => {
      disposed = true;
    };
  }, [token]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-6">
        <div className="max-w-xl text-center">
          <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-b-2 border-primary" />
          <h1 className="text-2xl font-semibold text-foreground">Loading remote browser</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            VacayClaw is connecting you to the hosted Trip.com session.
          </p>
        </div>
      </div>
    );
  }

  if (error || !session) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-6">
        <div className="max-w-xl rounded-3xl border border-border bg-card p-8 text-center shadow-sm">
          <h1 className="text-2xl font-semibold text-foreground">Remote browser unavailable</h1>
          <p className="mt-3 text-sm text-muted-foreground">{error || 'The remote browser session is no longer available.'}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border bg-card/80 px-6 py-5 backdrop-blur">
        <h1 className="text-2xl font-semibold">Remote browser</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          The Trip.com traveler page is live on the server. Continue there and stop before payment.
        </p>
        {session.current_url && (
          <p className="mt-2 text-xs text-muted-foreground">
            Current page: {session.current_url}
          </p>
        )}
      </header>

      <main className="p-4">
        <div className="overflow-hidden rounded-3xl border border-border bg-card shadow-sm">
          <iframe
            title="VacayClaw remote browser"
            src={session.embed_url}
            className="h-[calc(100vh-180px)] w-full bg-muted"
          />
        </div>
      </main>
    </div>
  );
};

export default BrowserTakeoverPage;
