/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  "#fdf6ee",
          100: "#faebd7",
          500: "#c8813a",
          700: "#8b4e1e",
          900: "#4a2510",
        },
      },
    },
  },
  plugins: [],
};
