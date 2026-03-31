import axios from 'axios';
import { getToken } from '../auth.js';

const api = axios.create({
  baseURL: '/api',
  timeout: 30_000,
});

// Inietta il token in ogni richiesta come header X-Dashboard-Token
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers['X-Dashboard-Token'] = token;
  }
  return config;
});

// ── Dashboard ──────────────────────────────────────────────────────────────
export const fetchKeywords = (hours = 48, limit = 15) =>
  api.get('/dashboard/keywords', { params: { hours, limit } }).then((r) => r.data);

export const fetchAlerts = (hours = 48, limit = 50) =>
  api.get('/dashboard/alerts', { params: { hours, limit } }).then((r) => r.data);

export const fetchConvergences = (hours = 48, min_sources = 2) =>
  api.get('/dashboard/convergences', { params: { hours, min_sources } }).then((r) => r.data);

export const fetchAlertsTimeline = (days = 14) =>
  api.get('/dashboard/alerts-timeline', { params: { days } }).then((r) => r.data);

export const fetchKeywordSources = (hours = 168, limit = 15) =>
  api.get('/dashboard/keyword-sources', { params: { hours, limit } }).then((r) => r.data);

export const fetchHighlights = () =>
  api.get('/dashboard/highlights').then((r) => r.data);

// ── YouTube ────────────────────────────────────────────────────────────────
export const fetchOutperformer = (days = 30, limit = 50) =>
  api.get('/youtube/outperformer', { params: { days, limit } }).then((r) => r.data);

export const fetchCompetitorVideos = (days = 14, limit = 50) =>
  api.get('/youtube/competitor-videos', { params: { days, limit } }).then((r) => r.data);

export const fetchCompetitors = () =>
  api.get('/youtube/competitors').then((r) => r.data);

export const fetchSubscriberSparkline = (days = 10) =>
  api.get('/youtube/subscriber-sparkline', { params: { days } }).then((r) => r.data);

export const fetchCompetitorVideosByKeyword = (days = 7) =>
  api.get('/youtube/competitor-videos/by-keyword', { params: { days } }).then((r) => r.data);

export const fetchCommentKeywords = (hours = 72) =>
  api.get('/youtube/comments/keywords', { params: { hours } }).then((r) => r.data);

export const fetchCommentIntel = (hours = 168) =>
  api.get('/youtube/comments/intel', { params: { hours } }).then((r) => r.data);

export const fetchCommentCategoryStats = (hours = 168) =>
  api.get('/youtube/comments/category-stats', { params: { hours } }).then((r) => r.data);

// ── Social (TikTok / IG) ───────────────────────────────────────────────────
export const fetchSocialProfiles = (platform = null, limit = 50) =>
  api.get('/social/profiles', { params: { platform, limit } }).then((r) => r.data);

export const fetchWatchlist = () =>
  api.get('/social/watchlist').then((r) => r.data);

export const fetchOutperformerVideos = (days = 30, limit = 50) =>
  api.get('/social/outperformer-videos', { params: { days, limit } }).then((r) => r.data);

export const addWatchlistItem = (handle, platform) =>
  api.post('/social/watchlist', { handle, platform }).then((r) => r.data);

export const removeWatchlistItem = (handle, platform) =>
  api.delete('/social/watchlist', { data: { handle, platform } }).then((r) => r.data);

// ── Trends ─────────────────────────────────────────────────────────────────
export const fetchGoogleTrends = (hours = 48) =>
  api.get('/trends/google', { params: { hours } }).then((r) => r.data);

export const fetchRisingQueries = (hours = 48) =>
  api.get('/trends/rising', { params: { hours } }).then((r) => r.data);

export const fetchTrendingRss = (hours = 24) =>
  api.get('/trends/trending-rss', { params: { hours } }).then((r) => r.data);

export const fetchKeywordTimeseries = (keyword, days = 7) =>
  api.get('/trends/keyword-timeseries', { params: { keyword, days } }).then((r) => r.data);

export const fetchKeywordSearch = (keyword, hours = 168) =>
  api.get('/dashboard/keyword-search', { params: { keyword, hours } }).then((r) => r.data);

// ── Pinterest ──────────────────────────────────────────────────────────────
export const fetchPinterestTrends = (hours = 168) =>
  api.get('/pinterest/trends', { params: { hours } }).then((r) => r.data);

export const fetchPinterestAlerts = (hours = 72) =>
  api.get('/pinterest/alerts', { params: { hours } }).then((r) => r.data);

export const fetchPinterestKeywordCounts = (hours = 72) =>
  api.get('/pinterest/keyword-counts', { params: { hours } }).then((r) => r.data);

// ── News & Reddit & Twitter ────────────────────────────────────────────────
export const fetchNewsAlerts = (hours = 48) =>
  api.get('/news/alerts', { params: { hours } }).then((r) => r.data);

export const fetchNewsKeywordCounts = (hours = 48) =>
  api.get('/news/keyword-counts', { params: { hours } }).then((r) => r.data);

export const fetchTwitterCounts = (hours = 48) =>
  api.get('/news/twitter-counts', { params: { hours } }).then((r) => r.data);

export const fetchTwitterAlerts = (hours = 48) =>
  api.get('/news/twitter-alerts', { params: { hours } }).then((r) => r.data);

// ── Config ─────────────────────────────────────────────────────────────────
export const fetchConfigParams = () =>
  api.get('/config/params').then((r) => r.data);

export const updateConfigParam = (key, value) =>
  api.put(`/config/params/${key}`, { value: String(value) }).then((r) => r.data);

export const fetchConfigLists = () =>
  api.get('/config/lists').then((r) => r.data);

export const addConfigListItem = (list_key, value, label = null) =>
  api.post('/config/lists', { list_key, value, label }).then((r) => r.data);

export const removeConfigListItem = (list_key, value) =>
  api.delete('/config/lists', { data: { list_key, value } }).then((r) => r.data);

export const fetchBlacklist = () =>
  api.get('/config/blacklist').then((r) => r.data);

export const addBlacklistItem = (keyword) =>
  api.post('/config/blacklist', { keyword }).then((r) => r.data);

export const removeBlacklistItem = (keyword) =>
  api.delete(`/config/blacklist/${encodeURIComponent(keyword)}`).then((r) => r.data);

// ── System ─────────────────────────────────────────────────────────────────
export const fetchBrief = () =>
  api.get('/system/brief').then((r) => r.data);

export const fetchWeekly = () =>
  api.get('/system/weekly').then((r) => r.data);

export const fetchSystemStatus = () =>
  api.get('/system/status').then((r) => r.data);

export const fetchDbStats = () =>
  api.get('/system/db-stats').then((r) => r.data);

export const fetchSchedule = () =>
  api.get('/system/schedule').then((r) => r.data);

export const triggerRunAll = () =>
  api.post('/system/run-all').then((r) => r.data);

export const triggerRunServices = (services) =>
  api.post('/system/run-services', { services }).then((r) => r.data);

export const fetchLogs = (minutes = 60, level = 'ALL', limit = 200) =>
  api.get('/system/logs', { params: { minutes, level, limit } }).then((r) => r.data);

export const downloadBackup = () =>
  api.get('/system/backup', { responseType: 'blob' }).then((r) => r.data);

export const triggerRestart = () =>
  api.post('/system/restart').then((r) => r.data);

export const fetchTranscript = (videoId) =>
  api.get(`/youtube/transcript/${videoId}`).then((r) => r.data);

export const restoreBackup = (file) => {
  const fd = new FormData();
  fd.append('file', file);
  return api.post('/system/restore', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then((r) => r.data);
};

export default api;
