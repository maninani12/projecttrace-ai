import {defineConfig} from '@playwright/test'
export default defineConfig({testDir:'./e2e',timeout:60000,use:{baseURL:'http://127.0.0.1:5173',headless:true,channel:process.env.CI?undefined:'msedge',trace:'retain-on-failure'},reporter:[['list'],['html',{open:'never'}]],workers:1})
