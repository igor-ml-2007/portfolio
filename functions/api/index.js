const PASSWORD = 'atelier';
// Pre-computed SHA-256 hash of "atelier"
const SESSION_TOKEN = 'f4d65b2483b34a8d50bcf2c9e053077c4dc7c00b65008ce1988ce4eca45741c8';

function checkAuth(request) {
  const cookieHeader = request.headers.get('Cookie');
  if (!cookieHeader) return false;
  const cookies = cookieHeader.split(';').map(c => c.trim());
  const sessionCookie = cookies.find(c => c.startsWith('portfolio_admin='));
  if (!sessionCookie) return false;
  const token = sessionCookie.split('=')[1];
  return token === SESSION_TOKEN;
}

function setAuthCookie(response) {
  response.headers.set('Set-Cookie', `portfolio_admin=${SESSION_TOKEN}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000`);
}

function clearAuthCookie(response) {
  response.headers.set('Set-Cookie', 'portfolio_admin=; Path=/; Max-Age=0');
}

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const path = url.pathname;

  // Handle CORS preflight
  if (request.method === 'OPTIONS') {
    return new Response(null, {
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
      },
    });
  }

  // GET /api/gallery - load gallery from KV
  if (path === '/api/gallery' && request.method === 'GET') {
    try {
      const data = await env.GALLERY.get('gallery', { type: 'json' });
      if (!data) {
        return new Response(JSON.stringify({ works: [], heroImage: '', artistImage: '' }), {
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response(JSON.stringify(data), {
        headers: { 'Content-Type': 'application/json' },
      });
    } catch (error) {
      return new Response(JSON.stringify({ works: [], heroImage: '', artistImage: '' }), {
        headers: { 'Content-Type': 'application/json' },
      });
    }
  }

  // POST /api/login - authentication
  if (path === '/api/login' && request.method === 'POST') {
    const formData = await request.formData();
    const password = formData.get('password');

    if (password === PASSWORD) {
      const response = new Response(null, {
        status: 303,
        headers: { Location: '/admin/' },
      });
      setAuthCookie(response);
      return response;
    }

    return new Response(null, {
      status: 303,
      headers: { Location: '/admin/login.html?error=1' },
    });
  }

  // GET /admin/logout - logout
  if (path === '/admin/logout' && request.method === 'GET') {
    const response = new Response(null, {
      status: 303,
      headers: { Location: '/admin/login.html' },
    });
    clearAuthCookie(response);
    return response;
  }

  // POST /api/gallery - save gallery to KV (requires auth)
  if (path === '/api/gallery' && request.method === 'POST') {
    if (!checkAuth(request)) {
      return new Response(JSON.stringify({ error: 'Нужна авторизация' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    try {
      const data = await request.json();
      await env.GALLERY.put('gallery', JSON.stringify(data));
      return new Response(JSON.stringify({ ok: true }), {
        headers: { 'Content-Type': 'application/json' },
      });
    } catch (error) {
      return new Response(JSON.stringify({ error: 'Ошибка сохранения' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    }
  }

  // POST /api/upload - upload image to R2 (requires auth)
  if (path === '/api/upload' && request.method === 'POST') {
    if (!checkAuth(request)) {
      return new Response(JSON.stringify({ error: 'Нужна авторизация' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    try {
      const formData = await request.formData();
      const file = formData.get('image');

      if (!file) {
        return new Response(JSON.stringify({ error: 'Файл не получен' }), {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        });
      }

      const extension = file.name.split('.').pop().toLowerCase();
      const allowedExtensions = ['jpg', 'jpeg', 'png', 'webp', 'gif'];
      if (!allowedExtensions.includes(extension)) {
        return new Response(JSON.stringify({ error: 'Поддерживаются JPG, PNG, WEBP и GIF' }), {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        });
      }

      const timestamp = Date.now();
      const random = Math.random().toString(36).substring(2, 10);
      const filename = `work-${timestamp}-${random}.${extension}`;

      await env.PHOTOS.put(filename, file);

      return new Response(JSON.stringify({ path: `/photos/${filename}` }), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      });
    } catch (error) {
      return new Response(JSON.stringify({ error: 'Ошибка загрузки' }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      });
    }
  }

  // Serve photos from R2
  if (path.startsWith('/photos/') && request.method === 'GET') {
    const filename = path.replace('/photos/', '');
    try {
      const object = await env.PHOTOS.get(filename);
      if (!object) {
        return new Response('Not Found', { status: 404 });
      }
      const headers = new Headers();
      object.writeHttpMetadata(headers);
      headers.set('etag', object.httpEtag);
      return new Response(object.body, { headers });
    } catch (error) {
      return new Response('Not Found', { status: 404 });
    }
  }

  return new Response('Not Found', { status: 404 });
}
