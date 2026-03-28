import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  fetchGoogleTrends,
  fetchRisingQueries,
  fetchTrendingRss,
} from '../../api/client.js';
import Topbar from '../../components/Topbar.jsx';
import EmptyState from '../../components/EmptyState.jsx';
import InfoTooltip from '../../components/InfoTooltip.jsx';
import Badge from '../../components/Badge.jsx';

const VELOCITY_TOOLTIP =
  'Velocity = variazione percentuale delle menzioni di una keyword nelle ultime ore rispetto al periodo precedente. Più alta, più la keyword sta crescendo rapidamente.';

const RISING_TOOLTIP =
  'Rising Query = query correlate a una keyword principale che stanno crescendo rapidamente su Google. "Breakout" indica una crescita superiore al 5000% (query nuova o virale).';

export default function TrendsPage() {
  const [tab, setTab] = useState('google');

  const { data: googleTrends = [], isLoading: loadingG } = useQuery({
    queryKey: ['google-trends'],
    queryFn: () => fetchGoogleTrends(48),
    staleTime: 5 * 60_000,
  });

  const { data: rising = [], isLoading: loadingR } = useQuery({
    queryKey: ['rising-queries'],
    queryFn: () => fetchRisingQueries(48),
    staleTime: 5 * 60_000,
  });

  const { data: trendingRss = [], isLoading: loadingT } = useQuery({
    queryKey: ['trending-rss'],
    queryFn: () => fetchTrendingRss(24),
    staleTime: 5 * 60_000,
  });

  return (
    <>
      <Topbar title="Trends" />
      <main className="page-content">
        <div className="tabs">
          {[
            { key: 'google', label: `Google Trends (${googleTrends.length})` },
            { key: 'rising', label: `Rising Queries (${rising.length})` },
            { key: 'trending', label: `Trending RSS (${trendingRss.length})` },
          ].map((t) => (
            <button
              key={t.key}
              className={`tab-btn${tab === t.key ? ' active' : ''}`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* ── Google Trends ──────────────────────────── */}
        {tab === 'google' && (
          <section className="card">
            <div className="card-header">
              <h2 className="card-title">
                Alert Google Trends (48h){' '}
                <InfoTooltip text={VELOCITY_TOOLTIP} />
              </h2>
            </div>
            {loadingG ? (
              <p className="muted">Caricamento…</p>
            ) : googleTrends.length === 0 ? (
              <EmptyState icon="📈" message="Nessun alert Google Trends nelle ultime 48 ore." />
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Keyword</th>
                    <th>Velocity</th>
                    <th>Rilevata</th>
                  </tr>
                </thead>
                <tbody>
                  {googleTrends.map((a) => (
                    <tr key={a.id}>
                      <td><strong>{a.keyword}</strong></td>
                      <td>
                        {a.velocity_pct != null
                          ? `+${Math.round(a.velocity_pct)}%`
                          : <span className="muted">—</span>}
                      </td>
                      <td className="muted">{new Date(a.sent_at).toLocaleString('it-IT')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        )}

        {/* ── Rising Queries ─────────────────────────── */}
        {tab === 'rising' && (
          <section className="card">
            <div className="card-header">
              <h2 className="card-title">
                Rising Queries (48h){' '}
                <InfoTooltip text={RISING_TOOLTIP} />
              </h2>
            </div>
            {loadingR ? (
              <p className="muted">Caricamento…</p>
            ) : rising.length === 0 ? (
              <EmptyState icon="🚀" message="Nessuna rising query nelle ultime 48 ore." />
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Query</th>
                    <th>Keyword padre</th>
                    <th>Crescita</th>
                    <th>Rilevata</th>
                  </tr>
                </thead>
                <tbody>
                  {rising.map((a) => {
                    let extra = {};
                    try { extra = JSON.parse(a.extra_json ?? '{}'); } catch {}
                    return (
                      <tr key={a.id}>
                        <td><strong>{a.keyword}</strong></td>
                        <td className="muted">{extra.parent_keyword ?? '—'}</td>
                        <td>
                          {extra.breakout
                            ? <Badge variant="high">BREAKOUT</Badge>
                            : a.velocity_pct != null
                              ? `+${Math.round(a.velocity_pct)}%`
                              : <span className="muted">—</span>}
                        </td>
                        <td className="muted">{new Date(a.sent_at).toLocaleString('it-IT')}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </section>
        )}

        {/* ── Trending RSS ───────────────────────────── */}
        {tab === 'trending' && (
          <section className="card">
            <div className="card-header">
              <h2 className="card-title">Trending RSS Google (24h)</h2>
            </div>
            {loadingT ? (
              <p className="muted">Caricamento…</p>
            ) : trendingRss.length === 0 ? (
              <EmptyState icon="📡" message="Nessun trend RSS nelle ultime 24 ore." />
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Termine</th>
                    <th>Area geografica</th>
                    <th>Traffico</th>
                    <th>Rilevato</th>
                  </tr>
                </thead>
                <tbody>
                  {trendingRss.map((a) => {
                    let extra = {};
                    try { extra = JSON.parse(a.extra_json ?? '{}'); } catch {}
                    return (
                      <tr key={a.id}>
                        <td><strong>{a.keyword}</strong></td>
                        <td className="muted">{extra.geo ?? '—'}</td>
                        <td>{extra.traffic ?? '—'}</td>
                        <td className="muted">{new Date(a.sent_at).toLocaleString('it-IT')}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </section>
        )}
      </main>
    </>
  );
}
