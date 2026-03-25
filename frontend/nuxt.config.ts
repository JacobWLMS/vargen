export default defineNuxtConfig({
  devtools: { enabled: true },
  modules: ['@nuxtjs/tailwindcss', '@nuxtjs/color-mode'],

  colorMode: {
    preference: 'dark',
    fallback: 'dark',
    classSuffix: '',
  },

  runtimeConfig: {
    public: {
      apiBase: process.env.API_BASE || 'http://localhost:8188',
    },
  },

  app: {
    head: {
      title: 'vargen',
      meta: [
        { name: 'description', content: 'AI-native image generation pipelines' },
      ],
    },
  },

  compatibilityDate: '2025-01-01',
})
