import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchSocialProfiles,
  fetchWatchlist,
  fetchOutperformerVideos,
  fetchConfigLists,
  addWatchlistItem,
  removeWatchlistItem,
  addConfigListItem,
  removeConfigListItem,
} from '../../api/client.js';
import InlineListManager from '../../components/InlineListManager.jsx';
import Topbar from '../../components/Topbar.jsx';
import EmptyState from '../../components/EmptyState.jsx';
import Badge from '../../components/Badge.jsx';
import MultBreakdown from '../../components/MultBreakdown.jsx';

// ── helpers ────────────────────────────────────────────────────────────────

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

function avatarInitial(handle) {
  const h = String(handle || '?').replace(/^@/, '');
  return h[0]?.toUpperCase() ?? '?';
}

// ── sub-components ─────────────────────────────────────────────────────────

function ProfileCard({ profile, pinned, onWatchlist, onRemove, gradient }) {
  const handle = profile.handle ?? profile.name ?? '?';
  const platform = profile.platform ?? '—';
  const followers = profile.followers ?? profile.followersCount ?? null;
  const lastPost = profile.scraped_at
    ? new Date(profile.scraped_at).toLocaleDateString('it-IT')
    : profile.lastPost ?? null;

  return (
    <div
      className="profile-card link-item"
      style={{ borderRadius: 6, padding: '10px 6px' }}
      onClick={() => window.open(platformUrl(platform, handle), '_blank')}
    >
      <div
        className="avatar"
        style={{
          background:
            gradient ??
            (platform === 'tiktok'
              ? 'linear-gradient(135deg,#a855f7,#e94560)'
              : 'linear-gradient(135deg,#e94560,#eab308)'),
        }}
      >
        {avatarInitial(handle)}
      </div>

      <div style={{ flex: 1 }}>
        <div className="profile-name" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span className="link-title">@{handle.replace(/^@/, '')}</span>
          <span className="link-icon">↗</span>
          {pinned && <span className="badge badge-purple">📌 pinned</span>}
        </div>
        <div className="profile-meta">
          {lastPost ? `${fmtN(followers)} follower · ${lastPost}` : `${platform} · ${fmtN(followers)} follower`}
        </div>
      </div>

      {(profile.mult_avg != null || profile.mult_subs != null) && (
        <MultBreakdown multAvg={profile.mult_avg} multSubs={profile.mult_subs} />
      )}

      {onWatchlist && (
        <button
          className="btn btn-primary btn-sm"
          style={{ marginLeft: 'auto' }}
          onClick={(e) => { e.stopPropagation(); onWatchlist(handle, platform); }}
        >
          📌 Watchlist
        </button>
      )}

      {onRemove && (
        <button
          className="btn btn-ghost btn-sm"
          style={{ marginLeft: 8 }}
          onClick={(e) => { e.stopPropagation(); onRemove(handle, platform); }}
        >
          Rimuovi
        </button>
      )}
    </div>
  );
}

// ── Video card ─────────────────────────────────────────────────────────────

function videoUrl(platform, url, video_id) {
  if (url) return url;
  if (platform === 'tiktok') return `https://www.tiktok.com/@unknown/video/${video_id}`;
  if (platform === 'instagram') return `https://www.instagram.com/p/${video_id}/`;
  return '#';
}

function VideoCard({ video }) {
  const url = videoUrl(video.platform, video.url, video.video_id);
  return (
    <div
      className="social-video-card link-item"
      onClick={() => url !== '#' && window.open(url, '_blank')}
    >
      <div className="social-video-body">
        <div className="social-video-title">{video.title || 'Nessuna didascalia'}</div>
        <div className="social-video-meta">
          @{video.username} · {fmtN(video.views)} views
        </div>
      </div>
      <div className="social-video-mult">
        <span className="social-mult-badge">{video.multiplier?.toFixed(1)}×</span>
        <span className="link-icon" style={{ fontSize: 11 }}>↗</span>
      </div>
    </div>
  );
}

// ── Outperformer tab ───────────────────────────────────────────────────────

function OutperformerTab({ profiles, videos }) {
  const tiktok    = profiles.filter((p) => p.platform === 'tiktok');
  const instagram = profiles.filter((p) => p.platform === 'instagram');

  const tiktokVideos    = videos.filter((v) => v.platform === 'tiktok');
  const instagramVideos = videos.filter((v) => v.platform === 'instagram');

  const platforms = [
    { key: 'tiktok',    label: 'TikTok',    icon: '🎵', gradient: 'linear-gradient(135deg,#a855f7,#e94560)', list: tiktok,    vids: tiktokVideos },
    { key: 'instagram', label: 'Instagram', icon: '📷', gradient: 'linear-gradient(135deg,#e94560,#eab308)', list: instagram, vids: instagramVideos },
  ];

  return (
    <div className="grid-2">
      {platforms.map(({ key, label, icon, gradient, list, vids }) => (
        <section className="card" key={key}>
          <div className="card-header">
            <h2 className="card-title">{icon} {label} Outperformer</h2>
          </div>
          {list.length === 0 ? (
            <EmptyState icon={icon} message={`Nessun profilo ${label} rilevato.`} />
          ) : (
            list.map((p) => (
              <ProfileCard
                key={`${p.platform}-${p.handle}`}
                profile={p}
                gradient={gradient}
              />
            ))
          )}
          {vids.length > 0 && (
            <div style={{ marginTop: 12, borderTop: '1px solid var(--border)', paddingTop: 10 }}>
              <div className="trends-card-title" style={{ fontSize: 11, marginBottom: 8 }}>
                🎬 VIDEO OUTPERFORMER (30 GIORNI)
              </div>
              {vids.slice(0, 5).map((v) => (
                <VideoCard key={v.video_id} video={v} />
              ))}
            </div>
          )}
        </section>
      ))}
    </div>
  );
}

// ── Watchlist tab ──────────────────────────────────────────────────────────

function WatchlistTab({ watchlist, onRemove, onAdd }) {
  const [newHandle, setNewHandle]     = useState('');
  const [newPlatform, setNewPlatform] = useState('tiktok');

  return (
    <section className="card">
      <div style={{ marginBottom: 14, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <span className="muted" style={{ fontSize: 13 }}>
          Profili monitorati permanentemente (senza filtri follower)
        </span>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            className="config-input"
            placeholder="@handle"
            value={newHandle}
            onChange={(e) => setNewHandle(e.target.value)}
            style={{ width: 160 }}
          />
          <select
            className="config-input"
            value={newPlatform}
            onChange={(e) => setNewPlatform(e.target.value)}
          >
            <option value="tiktok">TikTok</option>
            <option value="instagram">Instagram</option>
          </select>
          <button
            className="btn btn-primary btn-sm"
            disabled={!newHandle.trim()}
            onClick={() => { onAdd(newHandle.trim(), newPlatform); setNewHandle(''); }}
          >
            + Aggiungi profilo
          </button>
        </div>
      </div>

      {watchlist.length === 0 ? (
        <EmptyState icon="📌" message="Nessun profilo in watchlist." />
      ) : (
        watchlist.map((w) => (
          <ProfileCard
            key={`${w.platform}-${w.handle}`}
            profile={{ ...w, mult_avg: w.mult_avg, mult_subs: w.mult_subs }}
            pinned
            onRemove={(handle, platform) => onRemove(handle, platform)}
          />
        ))
      )}
    </section>
  );
}

// ── Discovery tab ──────────────────────────────────────────────────────────

function DiscoveryTab({ profiles, onWatchlist, tiktokHashtags, igHashtags, onAddHashtag, onRemoveHashtag, hashPending }) {
  const recent = profiles
    .slice()
    .sort((a, b) => new Date(b.scraped_at ?? 0) - new Date(a.scraped_at ?? 0))
    .slice(0, 10);

  return (
    <>
      <section className="card">
        <p className="muted" style={{ fontSize: 13, marginBottom: 12 }}>
          Profili scoperti via hashtag nelle ultime 24h (max 5/piattaforma)
        </p>
        {recent.length === 0 ? (
          <EmptyState icon="🔍" message="Nessun nuovo profilo scoperto di recente." />
        ) : (
          recent.map((p) => (
            <ProfileCard
              key={`${p.platform}-${p.handle}`}
              profile={p}
              gradient="linear-gradient(135deg,#22c55e,#3b82f6)"
              onWatchlist={onWatchlist}
            />
          ))
        )}
      </section>

      {/* ── Hashtag managers ── */}
      <div className="grid-2" style={{ marginTop: 14 }}>
        <div className="card">
          <div className="trends-card-title" style={{ marginBottom: 10 }}>🎵 HASHTAG TIKTOK MONITORATI</div>
          <InlineListManager
            listKey="tiktok_hashtags"
            items={tiktokHashtags}
            onAdd={onAddHashtag}
            onRemove={onRemoveHashtag}
            placeholder="#hashtag"
            isPending={hashPending}
          />
        </div>
        <div className="card">
          <div className="trends-card-title" style={{ marginBottom: 10 }}>📷 HASHTAG INSTAGRAM MONITORATI</div>
          <InlineListManager
            listKey="instagram_hashtags"
            items={igHashtags}
            onAdd={onAddHashtag}
            onRemove={onRemoveHashtag}
            placeholder="#hashtag"
            isPending={hashPending}
          />
        </div>
      </div>
    </>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────

const TABS = [
  { key: 'outperformer', label: '🚀 Outperformer' },
  { key: 'watchlist',    label: '📌 Watchlist'    },
  { key: 'discovery',   label: '🔍 Discovery'    },
];

export default function SocialPage() {
  const [tab, setTab] = useState('outperformer');
  const queryClient   = useQueryClient();

  /* ── queries ─────────────────────────────────────────────── */
  const { data: profiles = [], isLoading: profLoading } = useQuery({
    queryKey: ['social-profiles', 'all'],
    queryFn: () => fetchSocialProfiles(null, 200),
    staleTime: 5 * 60_000,
  });

  const { data: watchlist = [], isLoading: watchLoading } = useQuery({
    queryKey: ['watchlist'],
    queryFn: fetchWatchlist,
    staleTime: 60_000,
  });

  const { data: outVideos = [] } = useQuery({
    queryKey: ['outperformer-videos'],
    queryFn: () => fetchOutperformerVideos(30, 50),
    staleTime: 5 * 60_000,
  });

  const { data: configLists = {} } = useQuery({
    queryKey: ['config-lists'],
    queryFn: fetchConfigLists,
    staleTime: 30_000,
  });
  const tiktokHashtags = configLists.tiktok_hashtags ?? [];
  const igHashtags     = configLists.instagram_hashtags ?? [];

  const addHashtagMutation = useMutation({
    mutationFn: ({ listKey, value }) => addConfigListItem(listKey, value),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['config-lists'] }),
  });
  const removeHashtagMutation = useMutation({
    mutationFn: ({ listKey, value }) => removeConfigListItem(listKey, value),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['config-lists'] }),
  });

  /* ── mutations ───────────────────────────────────────────── */
  const addMutation = useMutation({
    mutationFn: ({ handle, platform }) => addWatchlistItem(handle, platform),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['watchlist'] }),
  });

  const removeMutation = useMutation({
    mutationFn: ({ handle, platform }) => removeWatchlistItem(handle, platform),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['watchlist'] }),
  });

  /* ── stat cards ──────────────────────────────────────────── */
  const tiktokCount    = profiles.filter((p) => p.platform === 'tiktok').length;
  const instagramCount = profiles.filter((p) => p.platform === 'instagram').length;
  const pinnedCount    = watchlist.length;

  const statCards = [
    { icon: '📱', label: 'Profili monitorati', value: profiles.length,
      sub: `TikTok: ${tiktokCount} · Instagram: ${instagramCount}` },
    { icon: '📌', label: 'Profili pinned',     value: pinnedCount,
      sub: 'Analizzati ad ogni run' },
    { icon: '🚀', label: 'Outperformer oggi',  value: profiles.filter((p) => p.mult_avg > 3).length,
      sub: 'Moltiplicatore > 3×' },
  ];

  return (
    <>
      <Topbar title="Social — TikTok & Instagram" />
      <main className="page-content">

        {/* Stat cards */}
        <div className="stats-grid" style={{ marginBottom: 20 }}>
          {statCards.map((c) => (
            <div className="stat-card" key={c.label}>
              <div className="stat-value">{profLoading ? '…' : c.value}</div>
              <div className="stat-label">{c.icon} {c.label}</div>
              <div className="stat-sub">{c.sub}</div>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <div className="tabs">
          {TABS.map(({ key, label }) => (
            <button
              key={key}
              className={`tab-btn${tab === key ? ' active' : ''}`}
              onClick={() => setTab(key)}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {(profLoading || watchLoading) ? (
          <p className="muted">Caricamento…</p>
        ) : (
          <>
            {tab === 'outperformer' && <OutperformerTab profiles={profiles} videos={outVideos} />}

            {tab === 'watchlist' && (
              <WatchlistTab
                watchlist={watchlist}
                onAdd={(handle, platform) => addMutation.mutate({ handle, platform })}
                onRemove={(handle, platform) => removeMutation.mutate({ handle, platform })}
              />
            )}

            {tab === 'discovery' && (
              <DiscoveryTab
                profiles={profiles}
                onWatchlist={(handle, platform) => addMutation.mutate({ handle, platform })}
                tiktokHashtags={tiktokHashtags}
                igHashtags={igHashtags}
                onAddHashtag={(lk, v) => addHashtagMutation.mutate({ listKey: lk, value: v })}
                onRemoveHashtag={(lk, v) => removeHashtagMutation.mutate({ listKey: lk, value: v })}
                hashPending={addHashtagMutation.isPending || removeHashtagMutation.isPending}
              />
            )}
          </>
        )}

      </main>
    </>
  );
}
