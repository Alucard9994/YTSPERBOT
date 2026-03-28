import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  fetchNewsAlerts,
  fetchNewsKeywordCounts,
  fetchTwitterAlerts,
  fetchTwitterCounts,
} from '../../api/client.js';
import Topbar from '../../components/Topbar.jsx';
import EmptyState from '../../components/EmptyState.jsx';
import InfoTooltip from '../../components/InfoTooltip.jsx';

const VELOCITY_TOOLTIP =
  'Velocity = variazione percentuale delle menzioni di una keyword nelle ultime ore rispetto al periodo precedente.';

export default function NewsPage() {
  const [tab, setTab] = useState('news');

  const { data: newsAlerts = [], isLoading: loadingNA } = useQuery({
    queryKey: ['news-alerts'],
    queryFn: () => fetchNewsAlerts(48),
    staleTime: 5 * 60_000,
  });

  const { data: newsCounts = [], isLoading: loadingNC } = useQuery({
    queryKey: ['news-counts'],
    queryFn: () => fetchNewsKeywordCounts(48),
    staleTime: 5 * 60_000,
  });

  const { data: twitterAlerts = [], isLoading: loadingTA } = useQuery({
    queryKey: ['twitter-alerts'],
    queryFn: () => fetchTwitterAlerts(48),
    staleTime: 5 * 60_000,
  });

  const { data: twitterCounts = [], isLoading: loadingTC } = useQuery({
    queryKey: ['twitter-counts'],
    queryFn: () => fetchTwitterCounts(48),
    staleTime: 5 * 60_000,
  });

  return (
    <>
      <Topbar title="News & Reddit & Twitter" />
      <main className="page-content">
        <div className="tabs">
          {[
            { key: 'news', label: `News (${newsAlerts.length})` },
            { key: 'twitter', label: `Twitter/X (${twitterAlerts.length})` },
            { key: 'reddit', label: 'Reddit' },
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

        {/* ── News ───────────────────────────────────── */}
        {tab === 'news' && (
          <>
            <section className="card">
              <div className="card-header">
                <h2 className="card-title">Keyword più menzionate nelle news (48h)</h2>
              </div>
              {loadingNC ? (
                <p className="muted">Caricamento…</p>
              ) : newsCounts.length === 0 ? (
                <EmptyState icon="📰" message="Nessuna keyword rilevata nelle news." />
              ) : (
                <div className="tag-list">
                  {newsCounts.map((kw) => (
                    <span key={kw.keyword} className="tag">
                      {kw.keyword} <span className="tag-count">{kw.count}</span>
                    </span>
                  ))}
                </div>
              )}
            </section>

            <section className="card">
              <div className="card-header">
                <h2 className="card-title">
                  Alert news (48h) <InfoTooltip text={VELOCITY_TOOLTIP} />
                </h2>
              </div>
              {loadingNA ? (
                <p className="muted">Caricamento…</p>
              ) : newsAlerts.length === 0 ? (
                <EmptyState message="Nessun alert news nelle ultime 48 ore." />
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Keyword</th>
                      <th>Velocity</th>
                      <th>Rilevato</th>
                    </tr>
                  </thead>
                  <tbody>
                    {newsAlerts.map((a) => (
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
          </>
        )}

        {/* ── Twitter ────────────────────────────────── */}
        {tab === 'twitter' && (
          <>
            <section className="card">
              <div className="card-header">
                <h2 className="card-title">Keyword su Twitter/X (48h)</h2>
              </div>
              {loadingTC ? (
                <p className="muted">Caricamento…</p>
              ) : twitterCounts.length === 0 ? (
                <EmptyState icon="🐦" message="Nessuna keyword Twitter nelle ultime 48 ore." />
              ) : (
                <div className="tag-list">
                  {twitterCounts.map((kw) => (
                    <span key={kw.keyword} className="tag">
                      {kw.keyword} <span className="tag-count">{kw.count}</span>
                    </span>
                  ))}
                </div>
              )}
            </section>

            <section className="card">
              <div className="card-header">
                <h2 className="card-title">
                  Alert Twitter/X (48h) <InfoTooltip text={VELOCITY_TOOLTIP} />
                </h2>
              </div>
              {loadingTA ? (
                <p className="muted">Caricamento…</p>
              ) : twitterAlerts.length === 0 ? (
                <EmptyState message="Nessun alert Twitter nelle ultime 48 ore." />
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Keyword</th>
                      <th>Velocity</th>
                      <th>Rilevato</th>
                    </tr>
                  </thead>
                  <tbody>
                    {twitterAlerts.map((a) => (
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
          </>
        )}

        {/* ── Reddit ─────────────────────────────────── */}
        {tab === 'reddit' && (
          <RedditSection />
        )}
      </main>
    </>
  );
}

/** Reddit uses keyword_mentions filtered by source = reddit */
function RedditSection() {
  const { data: alerts = [], isLoading } = useQuery({
    queryKey: ['reddit-alerts'],
    queryFn: () =>
      fetch('/api/dashboard/alerts?hours=72&limit=100')
        .then((r) => r.json())
        .then((data) => data.filter((a) => a.source === 'reddit' || a.alert_type === 'reddit_mention')),
    staleTime: 5 * 60_000,
  });

  return (
    <section className="card">
      <div className="card-header">
        <h2 className="card-title">Alert Reddit (72h)</h2>
      </div>
      {isLoading ? (
        <p className="muted">Caricamento…</p>
      ) : alerts.length === 0 ? (
        <EmptyState icon="🤖" message="Nessun alert Reddit nelle ultime 72 ore." />
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Keyword</th>
              <th>Velocity</th>
              <th>Rilevato</th>
            </tr>
          </thead>
          <tbody>
            {alerts.map((a) => (
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
  );
}
