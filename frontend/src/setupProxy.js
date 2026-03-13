const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  // Local dev defaults to localhost; Docker sets API_BACKEND_URL to service name
  const apiTarget = process.env.API_BACKEND_URL || 'http://localhost:8080';

  app.use(
    '/api',
    createProxyMiddleware({
      target: apiTarget,
      changeOrigin: true,
    })
  );
};
