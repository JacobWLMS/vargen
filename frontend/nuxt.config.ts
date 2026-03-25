export default defineNuxtConfig({
  devtools: { enabled: false },
  modules: ['@nuxtjs/tailwindcss'],
  css: ['~/assets/css/main.css'],

  app: {
    head: {
      title: 'vargen',
      htmlAttrs: { class: 'dark' },
      meta: [{ name: 'theme-color', content: '#000000' }],
    },
  },

  compatibilityDate: '2025-01-01',
})
