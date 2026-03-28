import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  fetchOutperformer,
  fetchCompetitorVideos,
  fetchCommentKeywords,
} from '../../api/client.js';
import Topbar from '../../components/Topbar.jsx';
import Badge from '../../components/Badge.jsx';
import EmptyState from '../../components/EmptyState.jsx';
import InfoTooltip from '../../components/InfoTooltip.jsx';

const MULT_TOOLTIP =
  'Moltiplicatore vs avg views = views del video ÷ media views del canale. Moltiplicatore vs iscritti = views del video ÷ iscritti del canale × 100. Entrambi indicano quanto il video sta sovraperformando rispetto al canale.';

function fmtN(n) {
  if (!n && n !== 0) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
}

function VideoCard({ v }) {
  const isShort = v.video_type === 'short';
  const ytUrl = `https://www.youtube.com/watch?v=${v.video_id}`;

  return (
    <div className="card link-item" onClick={() => window.open(ytUrl, '_blank')} style={{ cursor: 'pointer' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
            <Badge variant={isShort ? 'short' : 'long'}>{isShort ? 'SHORT' : 'LONG'}</Badge>
            <span className="link-title">{v.title}</span>
            <span className="link-icon">↗</span>
          </div>
          <div className="muted" style={{ fontSize: '0.85rem', marginBottom: 8 }}>
            {v.channel_name} · {v.published_at ? new Date(v.published_at).toLocaleDateString('it-IT') : '—'}
          </div>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: '0.9rem' }}>
            <span>👁 {fmtN(v.views)}</span>
            <span>👤 {fmtN(v.subscribers)} iscritti</span>
            {v.multiplier_avg != null && (
              <span title="vs media views canale">
                <strong>{v.multiplier_avg.toFixed(1)}×</strong> avg views
              </span>
            )}
            {v.multiplier_subs != null && (
              <span title="vs iscritti canale">
                <strong>{v.multiplier_subs.toFixed(1)}×</strong> iscritti
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function YouTubePage() {
  const [tab, setTab] = useState('outperformer');

  const { data: outperformer = [], isLoading: loadingOut } = useQuery({
    queryKey: ['outperformer'],
    queryFn: () => fetchOutperformer(30, 50),
    staleTime: 5 * 60_000,
  });

  const { data: competitorVideos = [], isLoading: loadingComp } = useQuery({
    queryKey: ['competitor-videos'],
    queryFn: () => fetchCompetitorVideos(14, 50),
    staleTime: 5 * 60_000,
  });

  const { data: commentKeywords = [], isLoading: loadingCom } = useQuery({
    queryKey: ['comment-keywords'],
    queryFn: () => fetchCommentKeywords(72),
    staleTime: 5 * 60_000,
  });

  const shorts = outperformer.filter((v) => v.video_type === 'short');
  const longs = outperformer.filter((v) => v.video_type !== 'short');

  return (
    <>
      <Topbar title="YouTube" />
      <main className="page-content">
        <div className="tabs">
          {[
            { key: 'outperformer', label: `Outperformer (${outperformer.length})` },
            { key: 'competitor', label: `Video Competitor (${competitorVideos.length})` },
            { key: 'comments', label: `Commenti (${commentKeywords.length})` },
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

        {/* ── Outperformer ───────────────────────────── */}
        {tab === 'outperformer' && (
          <>
            <div style={{ marginBottom: 8, color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              Moltiplicatori <InfoTooltip text={MULT_TOOLTIP} />
            </div>

            {loadingOut ? (
              <p className="muted">Caricamento…</p>
            ) : outperformer.length === 0 ? (
              <EmptyState icon="▶️" message="Nessun video outperformer rilevato negli ultimi 30 giorni." />
            ) : (
              <>
                {longs.length > 0 && (
                  <section className="card">
                    <div className="card-header">
                      <h2 className="card-title">Video lunghi ({longs.length})</h2>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                      {longs.map((v) => <VideoCard key={v.video_id} v={v} />)}
                    </div>
                  </section>
                )}

                {shorts.length > 0 && (
                  <section className="card" style={{ marginTop: 16 }}>
                    <div className="card-header">
                      <h2 className="card-title">Shorts ({shorts.length})</h2>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                      {shorts.map((v) => <VideoCard key={v.video_id} v={v} />)}
                    </div>
                  </section>
                )}
              </>
            )}
          </>
        )}

        {/* ── Competitor Videos ──────────────────────── */}
        {tab === 'competitor' && (
          <section className="card">
            {loadingComp ? (
              <p className="muted">Caricamento…</p>
            ) : competitorVideos.length === 0 ? (
              <EmptyState icon="👥" message="Nessun video competitor rilevato negli ultimi 14 giorni." />
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Titolo</th>
                    <th>Canale</th>
                    <th>Keyword</th>
                    <th>Pubblicato</th>
                    <th>Rilevato</th>
                  </tr>
                </thead>
                <tbody>
                  {competitorVideos.map((v) => (
                    <tr
                      key={v.video_id}
                      className="link-item"
                      style={{ cursor: 'pointer' }}
                      onClick={() => window.open(`https://www.youtube.com/watch?v=${v.video_id}`, '_blank')}
                    >
                      <td>
                        <span className="link-title">{v.title}</span>
                        <span className="link-icon">↗</span>
                      </td>
                      <td className="muted">{v.channel_name}</td>
                      <td>{v.matched_keyword ? <span className="tag">{v.matched_keyword}</span> : <span className="muted">—</span>}</td>
                      <td className="muted">{v.published_at ? new Date(v.published_at).toLocaleDateString('it-IT') : '—'}</td>
                      <td className="muted">{new Date(v.detected_at).toLocaleString('it-IT')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        )}

        {/* ── Comments ───────────────────────────────── */}
        {tab === 'comments' && (
          <section className="card">
            <div className="card-header">
              <h2 className="card-title">Keyword rilevate nei commenti (72h)</h2>
            </div>
            {loadingCom ? (
              <p className="muted">Caricamento…</p>
            ) : commentKeywords.length === 0 ? (
              <EmptyState icon="💬" message="Nessuna keyword rilevata nei commenti nelle ultime 72 ore." />
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Keyword</th>
                    <th>Menzioni</th>
                    <th>Ultimo rilevamento</th>
                  </tr>
                </thead>
                <tbody>
                  {commentKeywords.map((kw) => (
                    <tr key={kw.keyword}>
                      <td><strong>{kw.keyword}</strong></td>
                      <td>{kw.count}</td>
                      <td className="muted">{new Date(kw.last_seen).toLocaleString('it-IT')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        )}
      </main>
    </>
  );
}
