/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Outfit', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        serif: ['"Noto Serif Devanagari"', 'Georgia', 'Cambria', '"Times New Roman"', 'Times', 'serif'],
      },
      colors: {
        danger: { DEFAULT: '#ef4444', light: '#fef2f2' },
        success: { DEFAULT: '#22c55e', light: '#f0fdf4' },
        orange: {
          50: '#fff7ed',
          100: '#ffedd5',
          200: '#fed7aa',
          300: '#fdba74',
          400: '#fb923c',
          500: '#f97316',
          600: '#ea580c',
          700: '#c2410c',
          800: '#9a3412',
          900: '#7c2d12',
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
