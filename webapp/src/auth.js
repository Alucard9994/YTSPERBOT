/**
 * Gestione token di autenticazione dashboard.
 *
 * Il token viene letto (in ordine di priorità):
 *  1. Query param ?token= nell'URL (primo accesso via link Telegram)
 *  2. localStorage "dashboard_token"
 *
 * Dopo averlo salvato in localStorage il param viene rimosso dall'URL
 * per non lasciarlo esposto nella barra del browser.
 */

const STORAGE_KEY = 'dashboard_token';

/** Restituisce il token corrente (localStorage) o null. */
export function getToken() {
  return localStorage.getItem(STORAGE_KEY) || null;
}

/** Salva il token in localStorage. */
export function setToken(token) {
  localStorage.setItem(STORAGE_KEY, token);
}

/** Rimuove il token (logout). */
export function clearToken() {
  localStorage.removeItem(STORAGE_KEY);
}

/**
 * All'avvio dell'app, se c'è un ?token= nell'URL lo salva in localStorage
 * e pulisce la URL (history.replaceState) per non lasciarlo visibile.
 * Restituisce il token finale (da URL o da storage).
 */
export function bootstrapToken() {
  const params = new URLSearchParams(window.location.search);
  const urlToken = params.get('token');

  if (urlToken) {
    setToken(urlToken);
    // Rimuovi il param dall'URL senza ricaricare la pagina
    params.delete('token');
    const newSearch = params.toString();
    const newUrl = window.location.pathname + (newSearch ? `?${newSearch}` : '') + window.location.hash;
    window.history.replaceState(null, '', newUrl);
    return urlToken;
  }

  return getToken();
}
