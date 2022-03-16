module.exports = {
  content: [
    './isic/*/templates/**/*.html',
  ],
  safelist: [
    // Injected by Django, and may be referenced by CSS rules
    'errorlist',
    {
      // Dynamically set by alpine
      pattern:/^grid-cols-.*/
    }
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
    themes: ["winter"],
    logs: false,
  },
}
