const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  // Docker 환경에서는 서비스 이름으로 접근
  const apiTarget = process.env.API_BACKEND_URL || 'http://api-backend:8080';

  app.use(
    '/api',
    createProxyMiddleware({
      target: apiTarget,
      changeOrigin: true,
    })
  );
};
