import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import 'antd/dist/reset.css';

console.log('Main entry point loaded');

try {
    const root = ReactDOM.createRoot(document.getElementById('root'));
    root.render(
        <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
            <App />
        </BrowserRouter>
    );
    console.log('React root rendered');
} catch (e) {
    console.error('React render failed:', e);
}
