import { defineConfig } from 'vite'
export default defineConfig({resolve:{dedupe:['react','react-dom']},test:{server:{deps:{inline:[/@radix-ui/,/@tanstack/]}}},base:'/research/',build:{outDir:'../static',emptyOutDir:true},server:{proxy:{'/research/api':'http://127.0.0.1:47900','/api':'http://127.0.0.1:8008'}}})
