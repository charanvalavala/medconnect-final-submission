let token = sessionStorage.getItem('medconnect-token');

export function setToken(value) {
  token = value;
  if (value) sessionStorage.setItem('medconnect-token', value);
  else sessionStorage.removeItem('medconnect-token');
}

export function hasToken() { return Boolean(token); }

export async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && !path.includes('/auth/login')) {
      setToken(null);
      window.dispatchEvent(new Event('session-expired'));
    }
    const message = Array.isArray(body.detail)
      ? body.detail.map(item => `${item.loc.slice(1).join(' ')}: ${item.msg}`).join('; ')
      : body.detail || 'Unable to connect. Please try again.';
    throw new Error(message);
  }
  return body;
}

export function send(path, method, data) {
  return api(path, { method, ...(data === undefined ? {} : { body: JSON.stringify(data) }) });
}
