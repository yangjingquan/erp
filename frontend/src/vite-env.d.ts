/// <reference types="vite/client" />

export {};

declare module "vue" {
  export interface GlobalComponents {
    ClientPagination: typeof import("./components/ClientPagination.vue")["default"];
  }
}

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
