import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: ['selector', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        // Semantic tokens backed by CSS variables (oklch)
        brand: {
          DEFAULT: 'oklch(var(--brand) / <alpha-value>)',
          dim:    'oklch(var(--brand-dim) / <alpha-value>)',
          bright: 'oklch(var(--brand-bright) / <alpha-value>)',
        },
        surface: {
          0: 'oklch(var(--surface-0) / <alpha-value>)',
          1: 'oklch(var(--surface-1) / <alpha-value>)',
          2: 'oklch(var(--surface-2) / <alpha-value>)',
          3: 'oklch(var(--surface-3) / <alpha-value>)',
        },
        text: {
          primary:   'oklch(var(--text-primary) / <alpha-value>)',
          secondary: 'oklch(var(--text-secondary) / <alpha-value>)',
          muted:     'oklch(var(--text-muted) / <alpha-value>)',
        },
        border: {
          DEFAULT: 'oklch(var(--border) / <alpha-value>)',
          strong:  'oklch(var(--border-strong) / <alpha-value>)',
        },
        // ── ФСП Official Brand Palette ──────────────────────────────────
        fsp: {
          navy:     '#0A1F5C',   // Deep navy — headers, hero backgrounds
          blue:     '#1B3FA0',   // Primary brand blue — main interactive
          electric: '#1D82F5',   // Electric blue — highlights, active states
          red:      '#D42330',   // Patriotic red — primary CTA, danger, awards
          gold:     '#F0A500',   // Medal gold — scores, achievements, МС/КМС
          silver:   '#A0AEBF',   // Silver — secondary text, borders
          light:    '#E8EDF8',   // Light blue-grey — light surfaces
          // Legacy aliases (backward compat)
          violet:   '#1B3FA0',
          'violet-dark': '#0A1F5C',
          dark:     '#0A1F5C',
          gray:     '#6B7280',
          'light-bg': '#F4F7FE',
        },
        // Score colours — ФСП gold/blue palette
        score: {
          high:   '#1D82F5',   // Electric blue — высокий скор
          medium: '#F0A500',   // Gold — средний скор
          low:    '#D42330',   // Red — низкий скор
        },
      },
      fontFamily: {
        sans:     ['Inter', 'system-ui', 'sans-serif'],
        heading:  ['Montserrat', 'Inter', 'system-ui', 'sans-serif'],
        mono:     ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        '2xs': ['clamp(0.625rem, 0.5rem + 0.3vw, 0.75rem)', { lineHeight: '1.4' }],
        xs:    ['clamp(0.75rem, 0.65rem + 0.3vw, 0.875rem)', { lineHeight: '1.5' }],
        sm:    ['clamp(0.875rem, 0.75rem + 0.35vw, 1rem)',   { lineHeight: '1.5' }],
        base:  ['clamp(1rem, 0.9rem + 0.4vw, 1.125rem)',    { lineHeight: '1.6' }],
        lg:    ['clamp(1.125rem, 1rem + 0.5vw, 1.25rem)',   { lineHeight: '1.5' }],
        xl:    ['clamp(1.25rem, 1.1rem + 0.6vw, 1.5rem)',   { lineHeight: '1.4' }],
        '2xl': ['clamp(1.5rem, 1.25rem + 1vw, 2rem)',       { lineHeight: '1.3' }],
        '3xl': ['clamp(1.875rem, 1.5rem + 1.5vw, 2.5rem)',  { lineHeight: '1.2' }],
        '4xl': ['clamp(2.25rem, 1.75rem + 2vw, 3.5rem)',    { lineHeight: '1.1' }],
        '5xl': ['clamp(3rem, 2rem + 3vw, 4.5rem)',           { lineHeight: '1.05' }],
      },
      borderRadius: {
        sm:    '0.25rem',
        DEFAULT: '0.375rem',
        md:    '0.5rem',
        lg:    '0.75rem',
        xl:    '1rem',
        '2xl': '1.25rem',
        '3xl': '1.5rem',
      },
      boxShadow: {
        card:         '0 1px 3px rgba(0,0,0,0.25), 0 0 0 1px rgba(255,255,255,0.04)',
        'card-hover': '0 8px 32px rgba(10,31,92,0.35), 0 0 0 1px rgba(29,130,245,0.15)',
        'glow-brand': '0 0 24px rgba(27,63,160,0.55)',
        'glow-red':   '0 0 20px rgba(212,35,48,0.45)',
        'glow-gold':  '0 0 16px rgba(240,165,0,0.45)',
        'glow-score': '0 0 16px rgba(29,130,245,0.4)',
        nav:          '0 2px 16px rgba(10,31,92,0.4)',
      },
      backgroundImage: {
        'grid-dark':   'linear-gradient(rgba(255,255,255,0.04) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,0.04) 1px,transparent 1px)',
        'hero-glow':   'radial-gradient(ellipse 80% 50% at 50% -10%, rgba(29,130,245,0.22), transparent)',
        'fsp-gradient':'linear-gradient(135deg, #0A1F5C 0%, #1B3FA0 60%, #1D82F5 100%)',
        'fsp-diagonal':'linear-gradient(150deg, #0A1F5C 0%, #1B3FA0 55%, #1D82F5 100%)',
        'gold-gradient':'linear-gradient(90deg, #F0A500, #FFD04A)',
        'score-mu':    'linear-gradient(90deg, #F0A500, #FFD04A)',
        'score-lcb':   'linear-gradient(90deg, #1B3FA0, #1D82F5)',
      },
      animation: {
        'fade-up':  'fadeUp 0.45s cubic-bezier(0.16,1,0.3,1) both',
        'fade-in':  'fadeIn 0.3s ease both',
        shimmer:    'shimmer 2s infinite',
        float:      'float 6s ease-in-out infinite',
        pulse:      'pulse 2s cubic-bezier(0.4,0,0.6,1) infinite',
        'slide-in': 'slideIn 0.5s cubic-bezier(0.16,1,0.3,1) both',
      },
      keyframes: {
        fadeUp:   { from: { opacity: '0', transform: 'translateY(20px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        fadeIn:   { from: { opacity: '0' }, to: { opacity: '1' } },
        shimmer:  { '0%': { backgroundPosition: '-200% 0' }, '100%': { backgroundPosition: '200% 0' } },
        float:    { '0%,100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-8px)' } },
        slideIn:  { from: { opacity: '0', transform: 'translateX(-24px)' }, to: { opacity: '1', transform: 'translateX(0)' } },
      },
      transitionTimingFunction: {
        spring: 'cubic-bezier(0.34,1.56,0.64,1)',
      },
    },
  },
  plugins: [],
} satisfies Config
