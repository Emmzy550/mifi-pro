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
            }
        },
    },
    plugins: [],
}
