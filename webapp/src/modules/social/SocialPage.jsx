import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchSocialProfiles,
  fetchWatchlist,
  addWatchlistItem,
  removeWatchlistItem,
} from '../../api/client.js';
import Topbar from '../../components/Topbar.jsx';
import EmptyState from '../../components/EmptyState.jsx';
import Badge from '../../components/Badge.jsx';

function fmtN(n) {
  if (!n && n !== 0) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
}

function platformUrl(platform, handle) {
  if (platform === 'tiktok') return `https://www.tiktok.com/@${handle}`;
  if (platform === 'instagram') return `https://www.instagram.com/${handle}`;
  return '#';
}

export default function SocialPage() {
  const [platform, setPlatform] = useState('all');
  const [newHandle, setNewHandle] = useState('');
  const [newPlatform, setNewPlatform] = useState('tiktok');
  const queryClient = useQueryClient();

  const { data: profiles = [], isLoading } = useQuery({
    queryKey: ['social-profiles', platform],
    queryFn: () => fetchSocialProfiles(platform === 'all' ? null : platform, 100),
    staleTime: 5 * 60_000,
  });

  const { data: watchlist = [] } = useQuery({
    queryKey: ['watchlist'],
    queryFn: fetchWatchlist,
    staleTime: 60_000,
  });

  const addMutation = useMutation({
    mutationFn: () => addWatchlistItem(newHandle.trim(), newPlatform),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchlist'] });
      setNewHandle('');
    },
  });

  const removeMutation = useMutation({
    mutationFn: ({ handle, plat }) => removeWatchlistItem(handle, plat),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['watchlist'] }),
  });

  return (
    <>
      <Topbar title="Social — TikTok & Instagram" />
      <main className="page-content">

        {/* Platform filter */}
        <div className="tabs">
          {['all', 'tiktok', 'instagram'].map((p) => (
            <button
              key={p}
              className={`tab-btn${platform === p ? ' active' : ''}`}
              onClick={() => setPlatform(p)}
            >
              {p === 'all' ? 'Tutti' : p === 'tiktok' ? 'TikTok' : 'Instagram'}
            </button>
          ))}
        </div>

        {/* Profiles table */}
        <section className="card">
          <div className="card-header">
            <h2 className="card-title">Profili monitorati</h2>
          </div>
          {isLoading ? (
            <p className="muted">Caricamento…</p>
          ) : profiles.length === 0 ? (
            <EmptyState icon="📱" message="Nessun profilo social rilevato. Aspetta il prossimo ciclo Apify." />
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Handle</th>
                  <th>Piattaforma</th>
                  <th>Follower</th>
                  <th>Following</th>
                  <th>Post</th>
                  <th>Rilevato</th>
                </tr>
              </thead>
              <tbody>
                {profiles.map((p) => (
                  <tr
                    key={`${p.platform}-${p.handle}`}
                    className="link-item"
                    style={{ cursor: 'pointer' }}
                    onClick={() => window.open(platformUrl(p.platform, p.handle), '_blank')}
                  >
                    <td>
                      <span className="link-title">@{p.handle}</span>
                      <span className="link-icon">↗</span>
                    </td>
                    <td><Badge variant="default">{p.platform}</Badge></td>
                    <td>{fmtN(p.followers)}</td>
                    <td>{fmtN(p.following)}</td>
                    <td>{fmtN(p.post_count)}</td>
                    <td className="muted">{new Date(p.scraped_at).toLocaleDateString('it-IT')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        {/* Watchlist management */}
        <section className="card">
          <div className="card-header">
            <h2 className="card-title">Watchlist profili</h2>
          </div>

          <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
            <input
              className="config-input"
              placeholder="@handle"
              value={newHandle}
              onChange={(e) => setNewHandle(e.target.value)}
              style={{ flex: '1 1 160px' }}
            />
            <select
              className="config-input"
              value={newPlatform}
              onChange={(e) => setNewPlatform(e.target.value)}
              style={{ flex: '0 0 130px' }}
            >
              <option value="tiktok">TikTok</option>
              <option value="instagram">Instagram</option>
            </select>
            <button
              className="btn btn-primary"
              disabled={!newHandle.trim() || addMutation.isPending}
              onClick={() => addMutation.mutate()}
            >
              Aggiungi
            </button>
          </div>

          {watchlist.length === 0 ? (
            <p className="muted">Nessun profilo in watchlist.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr><th>Handle</th><th>Piattaforma</th><th></th></tr>
              </thead>
              <tbody>
                {watchlist.map((w) => (
                  <tr key={`${w.platform}-${w.handle}`}>
                    <td>@{w.handle}</td>
                    <td><Badge variant="default">{w.platform}</Badge></td>
                    <td>
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={() => removeMutation.mutate({ handle: w.handle, plat: w.platform })}
                      >
                        Rimuovi
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

      </main>
    </>
  );
}
