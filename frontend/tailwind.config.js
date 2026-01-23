/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                primary: "#1e40af", // deeply blue for trustworthy fintech feel
                secondary: "#10b981", // green for success/growth
            },
            animation: {
                'fluid-flow': 'fluid-flow 2s infinite linear',
            },
            keyframes: {
                'fluid-flow': {
                    '0%': { transform: 'translateX(-100%)' },
                    '100%': { transform: 'translateX(100%)' }
                }
            }
        },
    },
    plugins: [],
}
