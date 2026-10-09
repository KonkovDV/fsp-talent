import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { installSessionRenew } from './api/client'
import './index.css'

installSessionRenew()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
