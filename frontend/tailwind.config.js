/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: '#1B4F72', light: '#2980B9', dark: '#154360' },
      },
    },
  },
  plugins: [],
}
