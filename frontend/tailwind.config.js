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
        },
        // Theme-aware colors using CSS variables
        t: {
          'bg-primary': 'var(--bg-primary)',
          'bg-secondary': 'var(--bg-secondary)',
          'bg-tertiary': 'var(--bg-tertiary)',
          'border': 'var(--border)',
          'text-primary': 'var(--text-primary)',
          'text-secondary': 'var(--text-secondary)',
          'accent': 'var(--accent)',
          'accent-hover': 'var(--accent-hover)',
          'positive': 'var(--positive)',
          'negative': 'var(--negative)',
          'sidebar': 'var(--sidebar-bg)',
          'header': 'var(--header-bg)',
        }
      },
      backgroundImage: {
        'gradient-card': 'linear-gradient(135deg, var(--card-gradient-from) 0%, var(--card-gradient-to) 100%)',
        'gradient-accent': 'linear-gradient(135deg, var(--accent) 0%, var(--accent-secondary) 100%)',
        'gradient-sidebar': 'linear-gradient(180deg, var(--sidebar-gradient-from) 0%, var(--sidebar-gradient-to) 100%)',
      },
      borderColor: {
        't': 'var(--border)',
      }
    },
  },
  plugins: [],
}
