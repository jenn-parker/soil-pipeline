const localApiKey = import.meta.env.VITE_API_KEY?.trim()

function csrfToken(): string | undefined {
  return document.cookie
    .split('; ')
    .find((cookie) => cookie.startsWith('soil_csrf_token='))
    ?.split('=')[1]
}

/**
 * Call the API using either the local development key or the Cognito cookie.
 *
 * VITE_API_KEY is intentionally a development convenience, not a secret: Vite
 * embeds it in the browser bundle. Do not configure it for a deployed build.
 */
function send(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  if (localApiKey && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${localApiKey}`)
  }
  const csrf = csrfToken()
  if (csrf && !headers.has('X-CSRF-Token')) {
    headers.set('X-CSRF-Token', decodeURIComponent(csrf))
  }

  return fetch(input, {
    ...init,
    credentials: 'same-origin',
    headers,
  })
}

export async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const response = await send(input, init)
  if (response.status !== 401 || localApiKey || String(input).startsWith('/auth/refresh')) {
    return response
  }

  const refreshed = await send('/auth/refresh', { method: 'POST' })
  return refreshed.ok ? send(input, init) : response
}

export const isLocalApiKeyMode = Boolean(localApiKey)
