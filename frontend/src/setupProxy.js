/**
 * CRA development proxy — picked up automatically by react-scripts.
 * Forwards /api/* → http://localhost:8000/* (strips the /api prefix),
 * mirroring what nginx does in production Docker.
 *
 * No configuration needed: just run `uvicorn backend.main:app --reload`
 * alongside `npm start` and everything works out of the box.
 */
const { createProxyMiddleware } = require("http-proxy-middleware");

module.exports = function (app) {
  app.use(
    "/api",
    createProxyMiddleware({
      target: "http://localhost:8000",
      changeOrigin: true,
      pathRewrite: { "^/api": "" }, // strip /api prefix before forwarding
    })
  );
};
