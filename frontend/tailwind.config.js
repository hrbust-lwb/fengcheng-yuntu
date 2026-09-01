/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{vue,js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                brand: {
                    50: '#f0fdfa',
                    500: '#0d9488',
                    600: '#0f766e',
                    700: '#115e59',
                }
            }
        },
    },
    plugins: [],
}