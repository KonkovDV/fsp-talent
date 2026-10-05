import type { Config } from 'tailwindcss'

const v = (name: string) => `rgb(var(--${name}) / <alpha-value>)`

/**
 * ФСП Талант — design tokens.
 * Light theme is the default (HR people read cards for a long time); dark follows the system or the toggle.
 * Brand colours from the FSP brandbook: #402FFF, #EC1D35, #EDEDED, #C8C9CA, #1B1C21; typeface JetBrains Mono.
 * Red is reserved for the invitation and the brand stripe, gold only for sport ranks (МС, КМС).
 */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: ['selector', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        paper: v('paper'),
        panel: v('panel'),
        sunken: v('sunken'),
        ink: { DEFAULT: v('ink'), 2: v('ink-2'), 3: v('ink-3') },
        line: { DEFAULT: v('line'), strong: v('line-strong') },
        accent: { DEFAULT: v('accent'), soft: v('accent-soft'), ink: v('accent-ink') },
        invite: { DEFAULT: v('invite'), soft: v('invite-soft'), ink: v('invite-ink') },
        'brand-red': v('brand-red'),
        ok: { DEFAULT: v('ok'), soft: v('ok-soft') },
        warn: { DEFAULT: v('warn'), soft: v('warn-soft') },
        medal: { DEFAULT: v('medal'), soft: v('medal-soft') },
        navy: v('ink'),
        // Legacy names used by older markup; they now resolve to the same tokens.
        surface: { 0: v('paper'), 1: v('panel'), 2: v('sunken'), 3: v('line') },
        text: { primary: v('ink'), secondary: v('ink-2'), muted: v('ink-3') },
        border: { DEFAULT: v('line'), strong: v('line-strong') },
        brand: { DEFAULT: v('accent'), dim: v('accent-soft'), bright: v('accent') },
        fsp: {
          navy: v('ink'), blue: '#1B3FA0', red: '#D42330', gold: '#C98A00', light: '#E8EDF8',
          electric: v('accent'), violet: v('accent'), 'violet-dark': '#0A1F5C', dark: '#0A1F5C',
          silver: '#A0AEBF', gray: '#6B7280', 'light-bg': '#F4F7FE',
        },
        score: { high: v('accent'), medium: v('medal'), low: v('invite') },
      },
      fontFamily: {
        sans: ['"Golos Text Variable"', 'system-ui', 'sans-serif'],
        // JetBrains Mono is the Federation's brand typeface (brandbook); Golos Text carries long Russian body copy.
        display: ['"JetBrains Mono Variable"', 'ui-monospace', 'monospace'],
        heading: ['"JetBrains Mono Variable"', 'ui-monospace', 'monospace'],
        mono: ['"JetBrains Mono Variable"', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
        xs: ['0.8125rem', { lineHeight: '1.25rem' }],
        sm: ['0.875rem', { lineHeight: '1.375rem' }],
        base: ['1rem', { lineHeight: '1.6rem' }],
        lg: ['1.125rem', { lineHeight: '1.65rem' }],
        xl: ['1.3125rem', { lineHeight: '1.75rem' }],
        '2xl': ['1.625rem', { lineHeight: '2.1rem' }],
        '3xl': ['2.125rem', { lineHeight: '2.5rem' }],
        '4xl': ['2.75rem', { lineHeight: '3.1rem' }],
        '5xl': ['3.5rem', { lineHeight: '3.8rem' }],
      },
      borderRadius: { sm: '4px', DEFAULT: '6px', md: '6px', lg: '10px', xl: '12px', '2xl': '14px', '3xl': '18px' },
      boxShadow: {
        card: '0 1px 0 rgb(var(--line) / 1)',
        'card-hover': '0 6px 24px -12px rgb(27 28 33 / 0.22)',
        pop: '0 18px 48px -16px rgb(27 28 33 / 0.28)',
        'glow-brand': 'none', 'glow-red': 'none', 'glow-gold': 'none', 'glow-score': 'none', nav: 'none',
      },
      maxWidth: { page: '1200px', prose: '68ch' },
      keyframes: {
        rise: { from: { opacity: '0', transform: 'translateY(6px)' }, to: { opacity: '1', transform: 'none' } },
        fill: { from: { transform: 'scaleX(0)' }, to: { transform: 'scaleX(1)' } },
        shimmer: { '0%': { backgroundPosition: '-200% 0' }, '100%': { backgroundPosition: '200% 0' } },
      },
      animation: {
        rise: 'rise .35s cubic-bezier(.2,.7,.2,1) both',
        fill: 'fill .7s cubic-bezier(.2,.7,.2,1) both',
        shimmer: 'shimmer 1.6s infinite',
        'fade-up': 'rise .35s cubic-bezier(.2,.7,.2,1) both',
        'fade-in': 'rise .2s ease both',
      },
    },
  },
  plugins: [],
} satisfies Config
