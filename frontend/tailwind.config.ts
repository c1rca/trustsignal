import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        canvas: '#f7f8fa',
        panel: '#ffffff',
        ink: '#111827',
        muted: '#6b7280',
        border: '#e5e7eb',
        accent: '#1d4ed8'
      },
      boxShadow: {
        soft: '0 6px 24px rgba(15, 23, 42, 0.06)'
      }
    }
  },
  plugins: []
} satisfies Config
