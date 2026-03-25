export default defineNuxtConfig({
  devtools: { enabled: false },
  modules: ['@nuxtjs/tailwindcss', '@pinia/nuxt'],
  css: ['~/assets/css/main.css'],

  // Single page workspace — disable file-based routing
  pages: false,

  app: {
    head: {
      title: 'vargen',
      htmlAttrs: { class: 'dark' },
      meta: [{ name: 'theme-color', content: '#000000' }],
    },
  },

  compatibilityDate: '2025-01-01',
})
