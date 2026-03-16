/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          900: '#0a0a0f',
          800: '#12121a',
          700: '#1a1a25',
          600: '#222230',
          500: '#2a2a3a',
        },
        accent: {
          orange: '#f97316',
          pink: '#ec4899',
          purple: '#a855f7',
          green: '#22c55e',
          red: '#ef4444',
        }
      },
      backgroundImage: {
        'gradient-card': 'linear-gradient(135deg, #1a1a25 0%, #222230 100%)',
        'gradient-accent': 'linear-gradient(135deg, #f97316 0%, #ec4899 50%, #a855f7 100%)',
        'gradient-sidebar': 'linear-gradient(180deg, #12121a 0%, #0a0a0f 100%)',
      }
    },
  },
  plugins: [],
}
