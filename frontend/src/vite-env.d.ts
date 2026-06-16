/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend Socket.IO origin the browser connects to, e.g. http://localhost:8000. */
  readonly VITE_SOCKET_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}