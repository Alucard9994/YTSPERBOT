/**
 * MODULES_REGISTRY
 *
 * Single source of truth for which modules are active.
 * In a future SaaS, flip `enabled: false` (or drive from server) to hide entire sections.
 *
 * Each entry:
 *   id          – unique key used in routing & API calls
 *   label       – sidebar display name
 *   icon        – emoji icon shown in sidebar
 *   path        – React Router path  (must start with /)
 *   enabled     – whether the tab is shown at all
 *   description – tooltip / meta description
 */
const MODULES_REGISTRY = [
  {
    id: 'dashboard',
    label: 'Dashboard',
    icon: '📊',
    path: '/',
    enabled: true,
    description: 'Panoramica generale: keyword trending, alert recenti, convergenze multi-piattaforma.',
  },
  {
    id: 'youtube',
    label: 'YouTube',
    icon: '▶️',
    path: '/youtube',
    enabled: true,
    description: 'Video outperformer, video competitor, keyword nei commenti.',
  },
  {
    id: 'social',
    label: 'Social (TikTok / IG)',
    icon: '📱',
    path: '/social',
    enabled: true,
    description: 'Profili TikTok e Instagram monitorati via Apify.',
  },
  {
    id: 'trends',
    label: 'Trends',
    icon: '📈',
    path: '/trends',
    enabled: true,
    description: 'Google Trends, Trending RSS, Rising Queries.',
  },
  {
    id: 'pinterest',
    label: 'Pinterest',
    icon: '📌',
    path: '/pinterest',
    enabled: true,
    description: 'Alert Pinterest per keyword monitorate.',
  },
  {
    id: 'news',
    label: 'News, Twitter & Reddit',
    icon: '📰',
    path: '/news',
    enabled: true,
    description: 'Articoli di notizie, alert Reddit e Twitter/X.',
  },
  {
    id: 'config',
    label: 'Config & Sistema',
    icon: '⚙️',
    path: '/config',
    enabled: true,
    description: 'Parametri bot, schedule, liste, backup e stato API keys.',
    section: 'sistema',
  },
];

export default MODULES_REGISTRY;

/** Utility: return only enabled modules */
export const enabledModules = () => MODULES_REGISTRY.filter((m) => m.enabled);

/** Utility: find a module by id */
export const findModule = (id) => MODULES_REGISTRY.find((m) => m.id === id);
