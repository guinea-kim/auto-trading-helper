import React from 'react';
import { createRoot } from 'react-dom/client';
import AssetCalendarApp from './AssetCalendarApp';
import CrontabManager from './CrontabManager';

// Existing App
const container = document.getElementById('react-root');
if (container) {
    const params = new URLSearchParams(window.location.search);
    const market = params.get('market');
    const currency = (market === 'kr') ? 'KRW' : 'USD';

    const root = createRoot(container);
    root.render(<AssetCalendarApp initialCurrency={currency} />);
}

// New Crontab Dashboard
const crontabContainer = document.getElementById('crontab-root');
if (crontabContainer) {
    const root = createRoot(crontabContainer);
    root.render(<CrontabManager />);
}
