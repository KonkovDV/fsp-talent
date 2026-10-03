import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // FSP brand palette
        fsp: {
          violet: '#402FFF',
          'violet-dark': '#2E1FCC',
          red: '#EC1D35',
          dark: '#1B1C21',
          gray: '#6B7280',
          'light-bg': '#F8F9FC',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        xl: '1rem',
        '2xl': '1.25rem',
      },
      boxShadow: {
        card: '0 2px 8px rgba(64,47,255,0.08)',
        'card-hover': '0 8px 24px rgba(64,47,255,0.16)',
      },
    },
  },
  plugins: [],
} satisfies Config
