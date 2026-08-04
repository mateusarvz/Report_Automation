const defaultHeaders = {
  'Content-Type': 'application/json',
}

async function apiRequest(path, method = 'GET', data = null) {
  const init = {
    method,
    headers: defaultHeaders,
    credentials: 'include',
  }
  if (data !== null) {
    init.body = JSON.stringify(data)
  }

  const res = await fetch(path, init)
  const text = await res.text()
  const contentType = res.headers.get('content-type') || ''
  let body = null
  if (text) {
    if (contentType.includes('application/json')) {
      body = JSON.parse(text)
    } else {
      body = text
    }
  }

  if (!res.ok) {
    const errorMessage = body?.detail || body?.error || body?.message || body || `HTTP ${res.status}`
    throw new Error(errorMessage)
  }

  return body
}

export const apiGet = (path) => apiRequest(path, 'GET')
export const apiPost = (path, data) => apiRequest(path, 'POST', data)
export const apiPatch = (path, data) => apiRequest(path, 'PATCH', data)
