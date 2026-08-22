import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        sidebar: { bg: '#1E293B', text: '#F1F5F9' },
        accent: '#2563EB',
        page: '#F8F9FA',
      },
    },
  },
  plugins: [],
}

export default config
