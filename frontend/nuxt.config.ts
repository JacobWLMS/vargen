export default defineNuxtConfig({
  devtools: { enabled: false },
  modules: ['@nuxtjs/tailwindcss'],
  css: ['~/assets/css/main.css'],

  tailwindcss: {
    config: {
      darkMode: 'class',
      theme: { extend: {} },
      content: [],
    },
  },

  runtimeConfig: {
    public: {
      apiBase: process.env.API_BASE || 'http://localhost:8188',
    },
  },

  app: {
    head: {
      title: 'vargen',
      htmlAttrs: { class: 'dark' },
      meta: [
        { name: 'theme-color', content: '#000000' },
      ],
    },
  },

  compatibilityDate: '2025-01-01',
})
