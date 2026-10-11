const PASSWORD = 'atelier';
const SESSION_TOKEN = 'f4d65b2483b34a8d50bcf2c9e053077c4dc7c00b65008ce1988ce4eca45741c8';
const PUBLIC_ADMIN = ['/admin/login.html'];

function checkAuth(request) {
  const cookieHeader = request.headers.get('Cookie');
  if (!cookieHeader) return false;
  const cookies = cookieHeader.split(';').map(c => c.trim());
  const sessionCookie = cookies.find(c => c.startsWith('portfolio_admin='));
  if (!sessionCookie) return false;
  const token = sessionCookie.split('=')[1];
  return token === SESSION_TOKEN;
}

export async function onRequest(context) {
  const { request, next } = context;
  const url = new URL(request.url);
  const path = url.pathname;

  // Protect admin routes
  if (path.startsWith('/admin/') && !PUBLIC_ADMIN.includes(path)) {
    if (!checkAuth(request)) {
      return Response.redirect(url.origin + '/admin/login.html', 303);
    }
  }

  return next();
}
