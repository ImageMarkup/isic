module.exports = {
  content: [
    './isic/*/templates/**/*.html',
  ],
  safelist: [
    // Injected by Django, and may be referenced by CSS rules
    'errorlist',
  ],
  theme: {
    fontFamily: {
      'sans': 'Nunito, sans-serif',
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
    require('@tailwindcss/forms'),
    require('daisyui'),
  ],
  daisyui: {
    themes: false,
    logs: false,
  },
}
