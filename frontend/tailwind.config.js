/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        studio: {
          950: '#090a0f',
          900: '#10121a',
          800: '#181b26',
          700: '#232838',
          accent: '#6366f1',
          cyan: '#06b6d4',
          emerald: '#10b981',
        },
      },
    },
  },
  plugins: [],
};
