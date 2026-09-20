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
                },
                ink: '#081512',
                forest: '#0f2b24',
                emerald: '#167665',
                jade: '#2c9b82',
                gold: '#c6a15b',
                champagne: '#ead9b5',
                porcelain: '#f3f6f4',
                mist: '#64716d',
                line: '#d8e1dd',
            },
            fontFamily: {
                sans: ['"Noto Sans SC"', '"Source Han Sans SC"', '"PingFang SC"', '"Microsoft YaHei"', 'sans-serif'],
                display: ['"Source Han Serif SC"', '"Songti SC"', 'STSong', 'serif'],
            },
            boxShadow: {
                luxe: '0 20px 60px rgba(8, 21, 18, 0.20)',
                panel: '0 10px 30px rgba(8, 21, 18, 0.10)',
            },
        },
    },
    plugins: [],
}
