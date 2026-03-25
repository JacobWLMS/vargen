export default defineNuxtConfig({
  devtools: { enabled: false },
  modules: ['@nuxtjs/tailwindcss', '@pinia/nuxt'],
  css: ['~/assets/css/main.css'],

  pages: false,

  components: {
    dirs: [
      { path: '~/components/workspace', pathPrefix: false },
      { path: '~/components/canvas', pathPrefix: false },
      { path: '~/components/shared', pathPrefix: false },
    ],
  },

  app: {
    head: {
      title: 'vargen',
      htmlAttrs: { class: 'dark' },
      meta: [{ name: 'theme-color', content: '#000000' }],
    },
  },

  compatibilityDate: '2025-01-01',
})
